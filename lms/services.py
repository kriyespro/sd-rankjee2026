"""LMS business logic — visibility, submit, react, comment, review."""

from __future__ import annotations

import logging

from django.db.models import Count, Prefetch, Q, QuerySet
from django.urls import reverse
from django.utils import timezone

from .models import (
    LmsAssignment,
    LmsBatch,
    LmsBatchMembership,
    LmsComment,
    LmsReaction,
    LmsSubmission,
    LmsSubmissionUrl,
    LmsTopic,
)

GENERAL_TOPIC_SLUG = 'general'


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


def is_lms_staff(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def is_lms_student(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return getattr(user, 'role', None) == 'STUDENT' or is_lms_staff(user)


def user_batch_ids(user) -> set[int]:
    if not user or not user.is_authenticated:
        return set()
    return set(
        LmsBatchMembership.objects.filter(user=user, batch__is_active=True).values_list(
            'batch_id', flat=True
        )
    )


def assignments_for_user(user) -> QuerySet[LmsAssignment]:
    qs = LmsAssignment.objects.select_related('topic', 'batch', 'created_by')
    if is_lms_staff(user):
        return qs.all()
    # Students: published + (no batch OR member of batch)
    batch_ids = user_batch_ids(user)
    return qs.filter(is_published=True).filter(Q(batch__isnull=True) | Q(batch_id__in=batch_ids))


def can_view_assignment(user, assignment: LmsAssignment) -> bool:
    if is_lms_staff(user):
        return True
    if not assignment.is_published:
        return False
    if assignment.batch_id is None:
        return is_lms_student(user)
    return assignment.batch_id in user_batch_ids(user)


def can_edit_submission(user, submission: LmsSubmission) -> bool:
    if not user or not user.is_authenticated:
        return False
    if submission.student_id != user.id:
        return False
    due = submission.assignment.due_at
    if due and timezone.now() > due:
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
    return sorted(grouped.values(), key=lambda item: item['title'].lower())


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
        LmsComment.objects.filter(submission__assignment_id__in=assignment_ids)
        .select_related('user', 'submission', 'submission__assignment', 'submission__student')
        .order_by('-created_at')[:limit]
    )
    return {
        'top_scores': top_scores,
        'best_likes': best_likes,
        'latest_comments': latest_comments,
    }


def admin_home_stats() -> dict:
    """Staff-only LMS overview counts for the home header badges."""
    total_assignments = LmsAssignment.objects.count()
    topics_covered = LmsTopic.objects.filter(assignments__isnull=False).distinct().count()
    students_submitted = (
        LmsSubmission.objects.values('student_id').distinct().count()
    )
    pending = LmsSubmission.objects.filter(status=LmsSubmission.Status.SUBMITTED).count()
    pending_topic_titles = list(
        LmsTopic.objects.filter(
            assignments__submissions__status=LmsSubmission.Status.SUBMITTED,
        )
        .distinct()
        .order_by('title')
        .values_list('title', flat=True)[:8]
    )
    # Also count pending on assignments with no topic (shouldn't happen after General migrate)
    orphan_pending = LmsSubmission.objects.filter(
        status=LmsSubmission.Status.SUBMITTED,
        assignment__topic__isnull=True,
    ).exists()
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
    if assignment.batch_id:
        user_ids = LmsBatchMembership.objects.filter(batch_id=assignment.batch_id).values_list(
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


def add_batch_member(batch: LmsBatch, user) -> LmsBatchMembership:
    obj, _ = LmsBatchMembership.objects.get_or_create(batch=batch, user=user)
    return obj


def remove_batch_member(batch: LmsBatch, user) -> int:
    deleted, _ = LmsBatchMembership.objects.filter(batch=batch, user=user).delete()
    return deleted


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
