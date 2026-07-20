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


def set_reaction(submission: LmsSubmission, user, value: str) -> LmsReaction | None:
    """Toggle: same value removes; opposite updates; new creates."""
    existing = LmsReaction.objects.filter(submission=submission, user=user).first()
    if existing:
        if existing.value == value:
            existing.delete()
            return None
        existing.value = value
        existing.save(update_fields=['value'])
        return existing
    return LmsReaction.objects.create(submission=submission, user=user, value=value)


def add_comment(submission: LmsSubmission, user, body: str) -> LmsComment:
    body = (body or '').strip()
    if not body:
        raise ValueError('Comment cannot be empty.')
    return LmsComment.objects.create(submission=submission, user=user, body=body[:1000])


def review_submission(
    submission: LmsSubmission,
    *,
    marks=None,
    remark: str = '',
    status: str | None = None,
    is_pinned: bool | None = None,
) -> LmsSubmission:
    update_fields = ['updated_at']
    if marks is not None and marks != '':
        submission.marks = int(marks)
        update_fields.append('marks')
    if remark is not None:
        submission.remark = remark
        update_fields.append('remark')
    if status and status in LmsSubmission.Status.values:
        submission.status = status
        update_fields.append('status')
    if is_pinned is not None:
        submission.is_pinned = bool(is_pinned)
        update_fields.append('is_pinned')
    submission.save(update_fields=update_fields)
    _notify_feedback(submission)
    return submission


def notify_new_assignment(assignment: LmsAssignment) -> None:
    from django.contrib.auth import get_user_model

    from users.models import Notification

    User = get_user_model()
    link = reverse('lms:assignment_detail', kwargs={'pk': assignment.pk})
    msg = f'New LMS assignment: {assignment.title}'[:300]
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


def _notify_feedback(submission: LmsSubmission) -> None:
    from users.gamification import send_notification

    link = reverse('lms:assignment_detail', kwargs={'pk': submission.assignment_id})
    bits = []
    if submission.marks is not None:
        bits.append(f'{submission.marks}/100')
    if submission.remark:
        bits.append('remark updated')
    msg = f'Feedback on “{submission.assignment.title}”' + (f': {", ".join(bits)}' if bits else '')
    try:
        send_notification(submission.student, msg[:300], link)
    except Exception as exc:
        logger.warning('LMS feedback notify failed: %s', exc)


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
