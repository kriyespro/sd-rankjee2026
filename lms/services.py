"""LMS business logic — visibility, submit, react, comment, review."""

from __future__ import annotations

import logging

from django.db.models import Count, Prefetch, Q, QuerySet
from django.urls import reverse
from django.utils import timezone

from .models import (
    LmsAssignment,
    LmsComment,
    LmsCourse,
    LmsCourseEnrollment,
    LmsReaction,
    LmsSubmission,
    LmsSubmissionUrl,
    LmsTopic,
)

GENERAL_TOPIC_SLUG = 'general'


def crumb(label: str, url: str | None = None) -> dict:
    return {'label': label, 'url': url}


def lms_crumbs(*parts: dict) -> list[dict]:
    """Breadcrumb list starting with LMS home, then additional segments."""
    return [crumb('LMS', reverse('lms:home')), *parts]


def ensure_general_topic() -> LmsTopic:
    topic, _ = LmsTopic.objects.get_or_create(
        slug=GENERAL_TOPIC_SLUG,
        defaults={
            'title': 'General',
            'description': 'Default topic for assignments without a specific category.',
        },
    )
    return topic


def attach_orphan_assignments_to_general() -> int:
    topic = ensure_general_topic()
    return LmsAssignment.objects.filter(topic__isnull=True).update(topic=topic)


logger = logging.getLogger('rankjee.lms')


def is_lms_admin(user) -> bool:
    """Platform admin — sees and manages every faculty's courses/students."""
    return bool(user and user.is_authenticated and user.is_superuser)


def is_lms_faculty(user) -> bool:
    """Faculty — scoped to their own courses only.

    Home Tutor and Faculty are the SAME role for LMS purposes (fix: a marketplace Tutor
    shouldn't need an admin to pre-create a course and hand them ownership before they can
    touch the LMS at all — they can self-serve create their own first course). Backed by
    three independent signals, any one is sufficient:
    - `role` is TUTOR or FACULTY — grants self-serve LMS access (create a course, teach it)
      with zero admin setup required.
    - `is_lms_faculty` flag (also set automatically the moment a user is given an LmsCourse
      to own, e.g. by an admin assigning ownership directly).
    - Legacy: `is_staff` (non-superuser) — kept for existing ops-created staff accounts.
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_lms_faculty', False):
        return True
    from users.models import CustomUser

    if getattr(user, 'role', None) in (CustomUser.Role.TUTOR, CustomUser.Role.FACULTY):
        return True
    # Fix: office (CITY_ADMIN/GLOBAL_ADMIN) accounts are also `is_staff=True`, so the legacy
    # branch below used to also count them as "faculty" — an accidental overlap that made
    # is_lms_staff() true for office everywhere, even in call sites that only meant to ask
    # "is this a teacher" (e.g. attaching a grading form). Office has its own explicit role
    # (is_lms_office) and never gets teaching rights, so it must never match here too.
    if is_lms_office(user):
        return False
    return bool(user.is_staff and not user.is_superuser)


def is_lms_staff(user) -> bool:
    """Any staff-like LMS access (admin or faculty) — i.e. can *manage* something."""
    return is_lms_admin(user) or is_lms_faculty(user)


def is_lms_office(user) -> bool:
    """Office / ops (CITY_ADMIN, GLOBAL_ADMIN) — platform-wide oversight + setup for support &
    QA (fix-rankjee.md §4.2). Office is the "sets up who teaches what" role: they may create
    courses, assign a faculty/tutor as owner, and manage enrollment (see can_manage_topics,
    LmsCourseForm, courses()). They never get *teaching* rights — creating/editing/grading
    assignments stays gated by is_lms_admin/is_lms_faculty via can_manage_course/
    can_manage_assignment.
    """
    if not user or not user.is_authenticated:
        return False
    from users.models import CustomUser

    return getattr(user, 'role', None) in (CustomUser.Role.CITY_ADMIN, CustomUser.Role.GLOBAL_ADMIN)


def can_manage_topics(user) -> bool:
    """Topics (curriculum categories) are managed centrally by Admin/Office, not by individual
    faculty — a faculty creating an ad-hoc topic per course would fragment the same subject
    into duplicates across every batch. Faculty still pick from existing topics when creating
    an assignment; they just can't mint new ones.
    """
    return is_lms_admin(user) or is_lms_office(user)


def is_lms_student(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return getattr(user, 'role', None) == 'STUDENT' or is_lms_staff(user)


def user_course_ids(user) -> set[int]:
    if not user or not user.is_authenticated:
        return set()
    return set(
        LmsCourseEnrollment.objects.filter(user=user, course__is_active=True).values_list(
            'course_id', flat=True
        )
    )


def assignments_for_user(user) -> QuerySet[LmsAssignment]:
    qs = LmsAssignment.objects.select_related('topic', 'course', 'course__owner', 'created_by')
    if is_lms_admin(user) or is_lms_office(user):
        return qs.all()
    if is_lms_faculty(user):
        # Strictly the courses admin/office assigned to them — never another faculty's course,
        # and no longer platform-wide/unbatched content either (fix: "in LMS show only that
        # course's topic" — a faculty's whole world is exactly the courses they were assigned,
        # nothing broader). Platform-wide broadcasts are admin/office-only content now; students
        # still see them (below) regardless of which course, if any, they're enrolled in.
        return qs.filter(course__owner_id=user.id)
    # Students: published + (platform-wide OR enrolled in the course)
    course_ids = user_course_ids(user)
    return qs.filter(is_published=True).filter(Q(course__isnull=True) | Q(course_id__in=course_ids))


def can_view_assignment(user, assignment: LmsAssignment) -> bool:
    if is_lms_admin(user) or is_lms_office(user):
        return True
    if is_lms_faculty(user):
        # Matches assignments_for_user — a faculty can only ever view assignments in a course
        # they own; platform-wide (course=None) assignments are admin/office territory now.
        return bool(assignment.course_id) and assignment.course.owner_id == user.id
    if not assignment.is_published:
        return False
    if assignment.course_id is None:
        return is_lms_student(user)
    if assignment.course_id in user_course_ids(user):
        return True
    # Fix: a student unenrolled from the course (or whose course got deactivated) used to lose
    # access to their OWN already-graded submission/feedback outright (404) — they keep read
    # access to their own past work even after leaving; can_edit_submission still blocks them
    # from editing/resubmitting it once they're no longer part of the course.
    return LmsSubmission.objects.filter(assignment_id=assignment.pk, student_id=user.id).exists()


def can_manage_assignment(user, assignment: LmsAssignment) -> bool:
    """Edit / review rights — narrower than can_view_assignment for faculty."""
    if is_lms_admin(user):
        return True
    if is_lms_faculty(user):
        if assignment.course_id:
            return assignment.course.owner_id == user.id
        return assignment.created_by_id == user.id
    return False


def can_manage_course(user, course: LmsCourse) -> bool:
    if is_lms_admin(user):
        return True
    if is_lms_faculty(user):
        return course.owner_id == user.id
    return False


def own_student_ids(user) -> set[int]:
    """Every student enrolled in ANY course this faculty owns — their actual roster."""
    if not user or not user.is_authenticated:
        return set()
    return set(
        LmsCourseEnrollment.objects.filter(course__owner_id=user.id).values_list('user_id', flat=True)
    )


def faculty_student_scope(user) -> Q | None:
    """Q() that scopes an `LmsSubmission` queryset to a faculty's own students.

    `assignments_for_user` now excludes platform-wide content from faculty entirely (they only
    ever see their own courses), so in practice every submission this scopes is already a
    faculty's own student by construction — this is a second line of defense against any future
    change re-introducing shared/platform-wide assignments into a faculty's queryset, and against
    the edge case where a student was unenrolled after already submitting (still shows, via the
    `assignment__course__owner_id` arm). Returns None for admin/office — full platform
    visibility is correct for them by design.
    """
    if is_lms_admin(user) or is_lms_office(user):
        return None
    if is_lms_faculty(user):
        return Q(student_id__in=own_student_ids(user)) | Q(assignment__course__owner_id=user.id)
    return None


def can_edit_submission(user, submission: LmsSubmission) -> bool:
    if not user or not user.is_authenticated:
        return False
    if submission.student_id != user.id:
        return False
    due = submission.assignment.due_at
    if due and timezone.now() > due:
        return False
    course_id = submission.assignment.course_id
    if course_id and course_id not in user_course_ids(user):
        # Pairs with can_view_assignment's read-only fallback above: still visible to a
        # removed/deactivated-course student, but no longer editable/resubmittable.
        return False
    return True


def can_submit_assignment(user, assignment: LmsAssignment) -> bool:
    if not can_view_assignment(user, assignment):
        return False
    if is_lms_staff(user) and getattr(user, 'role', None) != 'STUDENT':
        # Staff preview only unless they are also STUDENT role
        return False
    due = assignment.due_at
    if due and timezone.now() > due:
        # Still allow if they already have a submission (edit) — checked separately
        return LmsSubmission.objects.filter(assignment=assignment, student=user).exists()
    return getattr(user, 'role', None) == 'STUDENT'


def topics_for_user(user) -> list[dict]:
    general = ensure_general_topic()
    assignments = list(assignments_for_user(user))
    grouped: dict[int, dict] = {}
    for assignment in assignments:
        topic = assignment.topic or general
        if topic.pk not in grouped:
            grouped[topic.pk] = {
                'topic': topic,
                'title': topic.title,
                'description': topic.description,
                'assignments': [],
            }
        grouped[topic.pk]['assignments'].append(assignment)

    # Fix: "add topic per course, need to show in LMS sidebar" — a topic explicitly scoped to a
    # course this user can access should appear right away, even before any assignment exists
    # under it (lets admin/office pre-build a course's topic structure ahead of assignments).
    if is_lms_admin(user) or is_lms_office(user):
        course_scoped_topics = LmsTopic.objects.filter(course__isnull=False)
    elif is_lms_faculty(user):
        course_scoped_topics = LmsTopic.objects.filter(course__owner_id=user.id)
    else:
        course_scoped_topics = LmsTopic.objects.filter(course_id__in=user_course_ids(user))
    for topic in course_scoped_topics.select_related('course'):
        if topic.pk not in grouped:
            grouped[topic.pk] = {
                'topic': topic,
                'title': topic.title,
                'description': topic.description,
                'assignments': [],
            }

    return sorted(grouped.values(), key=lambda item: item['title'].lower())


def student_assignment_ticker(user, limit: int = 10) -> list[dict]:
    """Compact news-ticker rows: pending own work + latest classroom assignments."""
    from django.urls import reverse

    assignments = list(
        assignments_for_user(user).select_related('topic').order_by('-created_at')[:40]
    )
    if not assignments:
        return []

    my_subs = {
        s.assignment_id: s
        for s in LmsSubmission.objects.filter(
            student=user,
            assignment_id__in=[a.pk for a in assignments],
        ).only('assignment_id', 'status')
    }

    items: list[dict] = []
    seen: set[int] = set()

    def add(kind: str, badge: str, assignment: LmsAssignment):
        if assignment.pk in seen or len(items) >= limit:
            return
        seen.add(assignment.pk)
        items.append(
            {
                'kind': kind,
                'badge': badge,
                'label': assignment.title,
                'url': reverse('lms:assignment_detail', kwargs={'pk': assignment.pk}),
            }
        )

    # 1) Not submitted yet → pending for the student
    for a in assignments:
        if a.pk not in my_subs:
            add('pending', 'Pending', a)

    # 2) Submitted, awaiting faculty review
    for a in assignments:
        sub = my_subs.get(a.pk)
        if sub and sub.status == LmsSubmission.Status.SUBMITTED:
            add('review', 'In review', a)

    # 3) Latest published assignments (news)
    for a in assignments[:8]:
        add('latest', 'New', a)

    return items

def submissions_feed(assignment: LmsAssignment) -> QuerySet[LmsSubmission]:
    return (
        LmsSubmission.objects.filter(assignment=assignment)
        .select_related('student', 'assignment')
        .annotate(
            like_count=Count('reactions', filter=Q(reactions__value=LmsReaction.Value.LIKE)),
            dislike_count=Count('reactions', filter=Q(reactions__value=LmsReaction.Value.DISLIKE)),
            comment_count=Count('comments'),
        )
        .prefetch_related(
            Prefetch(
                'comments',
                queryset=LmsComment.objects.select_related('user').order_by('created_at'),
            ),
            'reactions',
            'urls',
        )
        .order_by('-is_pinned', '-updated_at')
    )


def home_sidebar_data(user, limit: int = 5) -> dict:
    """Top scores, most-liked submissions, and latest comments for LMS home."""
    assignment_ids = list(assignments_for_user(user).values_list('pk', flat=True)[:80]) or [0]
    base = LmsSubmission.objects.filter(assignment_id__in=assignment_ids)
    scope = faculty_student_scope(user)
    if scope is not None:
        base = base.filter(scope)

    top_scores = list(
        base.filter(marks__isnull=False)
        .select_related('student', 'assignment')
        .order_by('-marks', '-updated_at')[:limit]
    )
    best_likes = list(
        base.annotate(
            like_count=Count('reactions', filter=Q(reactions__value=LmsReaction.Value.LIKE)),
        )
        .filter(like_count__gt=0)
        .select_related('student', 'assignment')
        .order_by('-like_count', '-updated_at')[:limit]
    )
    latest_comments = list(
        LmsComment.objects.filter(submission_id__in=base.values('pk'))
        .select_related('user', 'submission', 'submission__assignment', 'submission__student')
        .order_by('-created_at')[:limit]
    )
    return {
        'top_scores': top_scores,
        'best_likes': best_likes,
        'latest_comments': latest_comments,
    }


def admin_home_stats(user) -> dict:
    """Staff LMS overview counts for the home header badges.

    Admin (superuser) sees platform-wide counts; faculty see only their own assigned courses
    (assignments_for_user excludes platform-wide content from faculty entirely).
    """
    assignment_ids = list(assignments_for_user(user).values_list('pk', flat=True)) or [0]
    assignment_qs = LmsAssignment.objects.filter(pk__in=assignment_ids)

    total_assignments = assignment_qs.count()
    topics_covered = LmsTopic.objects.filter(assignments__in=assignment_ids).distinct().count()

    # Student-level data (who submitted, pending review) — see faculty_student_scope() docstring
    # for why this is now mostly a defense-in-depth no-op for faculty.
    submissions_qs = LmsSubmission.objects.filter(assignment_id__in=assignment_ids)
    scope = faculty_student_scope(user)
    if scope is not None:
        submissions_qs = submissions_qs.filter(scope)

    students_submitted = submissions_qs.values('student_id').distinct().count()
    pending_qs = submissions_qs.filter(status=LmsSubmission.Status.SUBMITTED)
    pending = pending_qs.count()
    pending_assignment_ids = list(pending_qs.values_list('assignment_id', flat=True).distinct())
    pending_topic_titles = list(
        LmsTopic.objects.filter(assignments__id__in=pending_assignment_ids)
        .distinct()
        .order_by('title')
        .values_list('title', flat=True)[:8]
    )
    # Also count pending on assignments with no topic (shouldn't happen after General migrate)
    orphan_pending = pending_qs.filter(assignment__topic__isnull=True).exists()
    if orphan_pending and 'General' not in pending_topic_titles:
        pending_topic_titles = ['General', *pending_topic_titles][:8]

    return {
        'students_submitted': students_submitted,
        'pending': pending,
        'total_assignments': total_assignments,
        'topics_covered': topics_covered,
        'pending_topics': pending_topic_titles,
        'pending_topics_label': ', '.join(pending_topic_titles) if pending_topic_titles else 'None',
    }


def set_reaction(submission: LmsSubmission, user, value: str) -> LmsReaction | None:
    """Toggle: same value removes; opposite updates; new creates."""
    existing = LmsReaction.objects.filter(submission=submission, user=user).first()
    if existing:
        if existing.value == value:
            existing.delete()
            return None
        existing.value = value
        existing.save(update_fields=['value'])
        reaction = existing
    else:
        reaction = LmsReaction.objects.create(submission=submission, user=user, value=value)

    if (
        reaction.value == LmsReaction.Value.LIKE
        and reaction.user_id != submission.student_id
    ):
        _notify_like(submission, user, reaction)
    return reaction


def add_comment(submission: LmsSubmission, user, body: str) -> LmsComment:
    body = (body or '').strip()
    if not body:
        raise ValueError('Comment cannot be empty.')
    comment = LmsComment.objects.create(submission=submission, user=user, body=body[:1000])
    if user.pk != submission.student_id:
        _notify_comment(submission, user, comment)
    return comment


def review_submission(
    submission: LmsSubmission,
    *,
    marks=None,
    remark: str | None = None,
    status: str | None = None,
    is_pinned: bool | None = None,
) -> LmsSubmission:
    old_marks = submission.marks
    old_remark = submission.remark
    old_status = submission.status

    update_fields = ['updated_at']
    marks_changed = False
    remark_changed = False
    status_changed = False

    if marks is not None and marks != '':
        new_marks = int(marks)
        marks_changed = new_marks != old_marks
        submission.marks = new_marks
        update_fields.append('marks')
    if remark is not None:
        remark_changed = remark != old_remark
        submission.remark = remark
        update_fields.append('remark')
    if status and status in LmsSubmission.Status.values:
        status_changed = status != old_status
        submission.status = status
        update_fields.append('status')
    if is_pinned is not None:
        submission.is_pinned = bool(is_pinned)
        update_fields.append('is_pinned')

    submission.save(update_fields=update_fields)

    if marks_changed and remark_changed:
        _notify_review(submission)
    elif marks_changed:
        _notify_marks(submission)
    elif remark_changed:
        _notify_remark(submission)
    elif status_changed:
        _notify_status(submission, old_status=old_status)

    return submission


def notify_new_assignment(assignment: LmsAssignment) -> None:
    from django.contrib.auth import get_user_model

    from users.models import Notification

    User = get_user_model()
    link = reverse('lms:assignment_detail', kwargs={'pk': assignment.pk})
    title = assignment.title
    msg = _lms_message('assignment', assignment.pk, f'New assignment: {title}')
    if assignment.course_id:
        user_ids = LmsCourseEnrollment.objects.filter(course_id=assignment.course_id).values_list(
            'user_id', flat=True
        )
        students = User.objects.filter(id__in=user_ids, is_active=True)
    else:
        students = User.objects.filter(role='STUDENT', is_active=True)
    student_ids = students.values_list('id', flat=True)[:200]
    try:
        Notification.objects.bulk_create(
            [
                Notification(user_id=uid, message=msg, link=link[:200])
                for uid in student_ids
            ]
        )
    except Exception as exc:
        logger.warning('LMS assignment notify failed: %s', exc)


def lms_notifications_for_user(user, limit: int = 20) -> dict:
    """Student LMS feed: own-work activity + new assignments, grouped and typed."""
    from users.models import Notification

    items: list[dict] = []
    seen_refs: set[str] = set()

    for note in Notification.objects.filter(user=user, link__contains='/lms/').order_by('-created_at')[: limit * 3]:
        parsed = _parse_lms_message(note.message)
        ref_key = f"{parsed['kind']}:{parsed.get('ref_id') or note.pk}"
        seen_refs.add(ref_key)
        meta = _kind_meta(parsed['kind'])
        items.append({
            'kind': parsed['kind'],
            'icon': meta['icon'],
            'title': meta['title'],
            'body': parsed['body'],
            'link': note.link,
            'created_at': note.created_at,
            'is_read': note.is_read,
            'notification_id': note.pk,
            'group': meta['group'],
        })

    if is_lms_student(user) and not is_lms_staff(user):
        items.extend(_synthetic_own_content_notifications(user, seen_refs))

    items.sort(key=lambda row: row['created_at'], reverse=True)
    items = items[:limit]

    unread_count = Notification.objects.filter(
        user=user,
        link__contains='/lms/',
        is_read=False,
    ).count()

    own_work = [row for row in items if row['group'] == 'own_work']
    classroom = [row for row in items if row['group'] == 'classroom']

    return {
        'notifications': items,
        'own_work': own_work,
        'classroom': classroom,
        'unread_count': unread_count,
    }


def _lms_message(kind: str, ref_id: int | None, body: str) -> str:
    tag = f'[lms:{kind}:{ref_id}]' if ref_id is not None else f'[lms:{kind}]'
    return f'{tag} {body}'[:300]


def _parse_lms_message(raw: str) -> dict:
    if raw.startswith('[lms:') and '] ' in raw:
        header, body = raw.split('] ', 1)
        header = header[5:]  # strip "[lms:"
        if ':' in header:
            kind, ref_s = header.split(':', 1)
            ref_id = int(ref_s) if ref_s.isdigit() else None
        else:
            kind, ref_id = header, None
        return {'kind': kind, 'ref_id': ref_id, 'body': body}

    kind = _guess_kind_from_message(raw)
    return {'kind': kind, 'ref_id': None, 'body': _clean_legacy_body(raw, kind)}


def _clean_legacy_body(message: str, kind: str) -> str:
    lower = message.lower()
    if kind == 'assignment':
        for prefix in ('new lms assignment:', 'new assignment:'):
            if lower.startswith(prefix):
                return message[len(prefix):].strip()
    return message


def _guess_kind_from_message(message: str) -> str:
    lower = message.lower()
    if 'new lms assignment' in lower or 'new assignment' in lower:
        return 'assignment'
    if 'liked your work' in lower:
        return 'like'
    if 'commented on' in lower:
        return 'comment'
    if 'faculty reviewed' in lower:
        return 'review'
    if 'marks updated' in lower:
        return 'marks'
    if 'faculty left a remark' in lower or 'faculty remark' in lower:
        return 'remark'
    if 'approved' in lower or 'changes requested' in lower:
        return 'status'
    return 'update'


def _kind_meta(kind: str) -> dict:
    table = {
        'assignment': {'icon': '📋', 'title': 'New assignment', 'group': 'classroom'},
        'marks': {'icon': '📊', 'title': 'Marks updated', 'group': 'own_work'},
        'remark': {'icon': '💬', 'title': 'Faculty remark', 'group': 'own_work'},
        'review': {'icon': '✅', 'title': 'Faculty review', 'group': 'own_work'},
        'comment': {'icon': '🗨️', 'title': 'Comment on your work', 'group': 'own_work'},
        'like': {'icon': '👍', 'title': 'Someone liked your work', 'group': 'own_work'},
        'status': {'icon': '📝', 'title': 'Submission status', 'group': 'own_work'},
        'update': {'icon': '🔔', 'title': 'LMS update', 'group': 'own_work'},
    }
    return table.get(kind, table['update'])


def _synthetic_own_content_notifications(user, seen_refs: set[str]) -> list[dict]:
    """Backfill comments/likes on the student's submissions when no stored notification exists."""
    from datetime import timedelta

    from users.models import Notification

    cutoff = timezone.now() - timedelta(days=90)
    items: list[dict] = []
    sub_ids = list(
        LmsSubmission.objects.filter(student=user).values_list('pk', flat=True)
    )
    if not sub_ids:
        return items

    for comment in (
        LmsComment.objects.filter(submission_id__in=sub_ids, created_at__gte=cutoff)
        .exclude(user=user)
        .select_related('user', 'submission', 'submission__assignment')
        .order_by('-created_at')[:20]
    ):
        ref_key = f'comment:{comment.pk}'
        if ref_key in seen_refs:
            continue
        if Notification.objects.filter(
            user=user,
            message__startswith=f'[lms:comment:{comment.pk}]',
        ).exists():
            continue
        title = comment.submission.assignment.title
        preview = comment.body[:80] + ('…' if len(comment.body) > 80 else '')
        items.append({
            'kind': 'comment',
            'icon': '🗨️',
            'title': 'Comment on your work',
            'body': f'{_display_name(comment.user)} on “{title}”: {preview}',
            'link': _submission_link(comment.submission),
            'created_at': comment.created_at,
            'is_read': True,
            'notification_id': None,
            'group': 'own_work',
        })
        seen_refs.add(ref_key)

    for reaction in (
        LmsReaction.objects.filter(
            submission_id__in=sub_ids,
            value=LmsReaction.Value.LIKE,
            created_at__gte=cutoff,
        )
        .exclude(user=user)
        .select_related('user', 'submission', 'submission__assignment')
        .order_by('-created_at')[:20]
    ):
        ref_key = f'like:{reaction.pk}'
        if ref_key in seen_refs:
            continue
        if Notification.objects.filter(
            user=user,
            message__startswith=f'[lms:like:{reaction.pk}]',
        ).exists():
            continue
        title = reaction.submission.assignment.title
        items.append({
            'kind': 'like',
            'icon': '👍',
            'title': 'Someone liked your work',
            'body': f'{_display_name(reaction.user)} liked your work on “{title}”',
            'link': _submission_link(reaction.submission),
            'created_at': reaction.created_at,
            'is_read': True,
            'notification_id': None,
            'group': 'own_work',
        })
        seen_refs.add(ref_key)

    return items


def _submission_link(submission: LmsSubmission) -> str:
    base = reverse('lms:assignment_detail', kwargs={'pk': submission.assignment_id})
    return f'{base}#sub-{submission.pk}'


def _display_name(user) -> str:
    return (user.get_full_name() or user.username or 'Someone').strip()


def _lms_send(user, kind: str, body: str, link: str, ref_id: int | None = None) -> None:
    from users.gamification import send_notification

    try:
        send_notification(user, _lms_message(kind, ref_id, body), link[:200])
    except Exception as exc:
        logger.warning('LMS notify %s failed: %s', kind, exc)


def _notify_like(submission: LmsSubmission, reactor, reaction: LmsReaction) -> None:
    title = submission.assignment.title
    body = f'{_display_name(reactor)} liked your work on “{title}”'
    _lms_send(submission.student, 'like', body, _submission_link(submission), ref_id=reaction.pk)


def _notify_comment(submission: LmsSubmission, commenter, comment: LmsComment) -> None:
    preview = comment.body[:80] + ('…' if len(comment.body) > 80 else '')
    title = submission.assignment.title
    body = f'{_display_name(commenter)} on “{title}”: {preview}'
    _lms_send(submission.student, 'comment', body, _submission_link(submission), ref_id=comment.pk)


def _notify_marks(submission: LmsSubmission) -> None:
    title = submission.assignment.title
    body = f'You received {submission.marks}/100 on “{title}”'
    _lms_send(submission.student, 'marks', body, _submission_link(submission), ref_id=submission.pk)


def _notify_remark(submission: LmsSubmission) -> None:
    title = submission.assignment.title
    preview = submission.remark[:100] + ('…' if len(submission.remark) > 100 else '')
    body = f'Faculty remark on “{title}”: {preview}'
    _lms_send(submission.student, 'remark', body, _submission_link(submission), ref_id=submission.pk)


def _notify_review(submission: LmsSubmission) -> None:
    title = submission.assignment.title
    preview = submission.remark[:80] + ('…' if len(submission.remark) > 80 else '') if submission.remark else ''
    body = f'Faculty reviewed “{title}”: {submission.marks}/100'
    if preview:
        body = f'{body} — {preview}'
    _lms_send(submission.student, 'review', body, _submission_link(submission), ref_id=submission.pk)


def _notify_status(submission: LmsSubmission, *, old_status: str) -> None:
    title = submission.assignment.title
    if submission.status == LmsSubmission.Status.APPROVED:
        body = f'Your work on “{title}” was approved'
    elif submission.status == LmsSubmission.Status.CHANGES_REQUESTED:
        body = f'Changes requested on “{title}” — check faculty remark'
    else:
        body = f'Status updated on “{title}”'
    _lms_send(submission.student, 'status', body, _submission_link(submission), ref_id=submission.pk)


def student_directory_options(limit: int = 300, *, include_email: bool = True) -> list[dict]:
    """Username (+ optional email) for the "Assign student" typeahead on /admin/lms/courses/
    (fix: make assigning a student to a faculty simple — no more hunting down an exact username
    by memory). Capped and STUDENT-role-only to keep the page light; if the platform grows past
    this, swap for an HTMX live-search endpoint like hometutor.quick_tutor_search.

    `include_email=False` (used for faculty/tutor callers) strips email from every row so a
    faculty browsing the suggestion list never sees another student's email address — only
    admin/office, who actually need it to disambiguate same-username-ish students, get it.
    """
    from users.models import CustomUser

    rows = list(
        CustomUser.objects.filter(role=CustomUser.Role.STUDENT)
        .order_by('username')
        .values('username', 'email')[:limit]
    )
    if not include_email:
        for row in rows:
            row['email'] = ''
    return rows


def lms_owner_queryset():
    """Users eligible to own an `LmsCourse` — staff, explicitly-flagged LMS faculty, or a
    TUTOR/FACULTY role. Shared by `LmsCourseForm` (create) and the `reassign_owner` action /
    superadmin quick-assign panel (existing course), so the two paths never drift apart."""
    from django.db.models import Q as _Q

    from users.models import CustomUser

    return (
        CustomUser.objects.filter(_Q(is_staff=True) | _Q(is_lms_faculty=True) | _Q(role__in=['TUTOR', 'FACULTY']))
        .distinct()
        .order_by('username')
    )


def add_course_member(course: LmsCourse, user) -> LmsCourseEnrollment:
    obj, _ = LmsCourseEnrollment.objects.get_or_create(course=course, user=user)
    return obj


def remove_course_member(course: LmsCourse, user) -> int:
    deleted, _ = LmsCourseEnrollment.objects.filter(course=course, user=user).delete()
    return deleted


def courses_for_user(user) -> QuerySet[LmsCourse]:
    """Courses this user can see. Admin manages all; Office (read-only) also sees all for
    oversight; Faculty sees (and manages) only their own."""
    qs = (
        LmsCourse.objects.select_related('owner', 'catalog_course')
        .prefetch_related('enrollments__user')
        # "How set up is this course?" at a glance on the courses list — fix: previously the
        # only visible signal was student count, so an empty/half-built course looked identical
        # to one nobody had ever touched.
        .annotate(
            assignment_count=Count('assignments', distinct=True),
            topic_count=Count('topics', distinct=True),
        )
    )
    if is_lms_admin(user) or is_lms_office(user):
        return qs.order_by('name')
    return qs.filter(owner_id=user.id).order_by('name')


def default_lms_course_for_catalog(catalog_course_id: int) -> LmsCourse | None:
    """The delivery batch new buyers of a paid catalog course auto-enroll into.

    Prefers a batch explicitly flagged `is_default_for_catalog`; otherwise falls back to
    the oldest active batch linked to that catalog course.
    """
    return (
        LmsCourse.objects.filter(catalog_course_id=catalog_course_id, is_active=True)
        .order_by('-is_default_for_catalog', 'id')
        .first()
    )


def enroll_from_catalog_purchase(user, catalog_course) -> LmsCourseEnrollment | None:
    """Called right after a `core.CoursePurchase` is created. Auto-enrolls the buyer into
    whichever LmsCourse batch delivers that catalog course. Returns None (and logs a
    warning) if no faculty/tutor has been assigned to deliver it yet — admin needs to
    create an LmsCourse with `catalog_course` set and assign an owner.
    """
    course = default_lms_course_for_catalog(catalog_course.pk)
    if not course:
        logger.warning(
            'No LMS delivery batch assigned for catalog course id=%s (%r) — purchase by user id=%s '
            'has no classroom to join yet. Create an LmsCourse with catalog_course set.',
            catalog_course.pk,
            getattr(catalog_course, 'title', ''),
            user.id,
        )
        return None
    enrollment, _ = LmsCourseEnrollment.objects.get_or_create(course=course, user=user)
    return enrollment


def purchases_missing_lms_enrollment(limit: int = 50) -> list:
    """Recent catalog purchases whose buyer has no matching LmsCourse enrollment yet —
    surfaced to admins so they know which paid courses still need a tutor/batch assigned.
    """
    from core.models import CoursePurchase

    purchases = list(
        CoursePurchase.objects.select_related('user', 'course').order_by('-created_at')[:500]
    )
    if not purchases:
        return []
    catalog_ids = {p.course_id for p in purchases}
    enrolled_pairs = set(
        LmsCourseEnrollment.objects.filter(course__catalog_course_id__in=catalog_ids).values_list(
            'user_id', 'course__catalog_course_id'
        )
    )
    missing = [p for p in purchases if (p.user_id, p.course_id) not in enrolled_pairs]
    return missing[:limit]


def student_skill_attempt_for_assignment(user, assignment: LmsAssignment):
    """Best (most recent) attempt this student has made at the assignment's linked skill
    test, or None if no skill is linked / they haven't attempted it yet."""
    if not assignment.skill_id or not user or not user.is_authenticated:
        return None
    from assessment.models import UserAttempt

    return (
        UserAttempt.objects.filter(user=user, skill_id=assignment.skill_id)
        .order_by('-attempt_date')
        .first()
    )


def assignment_skill_roster(assignment: LmsAssignment) -> list[dict]:
    """For faculty/admin managing this assignment: each enrolled student's latest attempt
    at the linked skill test (or "not attempted" if none). Platform-wide assignments
    (no course) have no fixed roster, so this returns an empty list for those — use
    `assignments_for_user`/course enrollment as the source of truth for who's expected
    to take the test.
    """
    if not assignment.skill_id or not assignment.course_id:
        return []
    from assessment.models import UserAttempt

    enrollments = (
        LmsCourseEnrollment.objects.filter(course_id=assignment.course_id)
        .select_related('user')
        .order_by('user__username')
    )
    if not enrollments:
        return []
    student_ids = [e.user_id for e in enrollments]
    attempts_by_user = {}
    for attempt in (
        UserAttempt.objects.filter(user_id__in=student_ids, skill_id=assignment.skill_id)
        .order_by('user_id', '-attempt_date')
    ):
        attempts_by_user.setdefault(attempt.user_id, attempt)  # first hit per user = latest (ordered)

    roster = []
    for enrollment in enrollments:
        roster.append(
            {
                'student': enrollment.user,
                'attempt': attempts_by_user.get(enrollment.user_id),
            }
        )
    return roster


def save_submission_with_urls(
    submission: LmsSubmission,
    *,
    caption: str = '',
    url_items: list[dict],
) -> LmsSubmission:
    submission.caption = caption or ''
    submission.video_url = ''
    submission.website_url = ''
    submission.save()
    submission.urls.all().delete()
    for i, item in enumerate(url_items):
        LmsSubmissionUrl.objects.create(
            submission=submission,
            url=item['url'],
            kind=item['kind'],
            sort_order=i,
        )
    return submission


def submission_link_rows(submission: LmsSubmission) -> list[dict]:
    rows = [
        {'url': row.url, 'kind': row.kind, 'label': row.get_kind_display()}
        for row in submission.urls.all()
    ]
    if rows:
        return rows
    legacy = []
    if (submission.video_url or '').strip():
        legacy.append({
            'url': submission.video_url.strip(),
            'kind': LmsSubmissionUrl.Kind.DRIVE,
            'label': 'Google Drive',
        })
    if (submission.website_url or '').strip():
        legacy.append({
            'url': submission.website_url.strip(),
            'kind': LmsSubmissionUrl.Kind.WEBSITE,
            'label': 'Website',
        })
    return legacy
