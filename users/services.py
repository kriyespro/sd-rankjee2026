"""Parent <-> Student linking business logic (fix-rankjee.md Phase 2).

Kept intentionally small and additive — this must not touch any existing user flow.
A Parent requests a link by username/email; the Student must approve before the parent
gets any read-only visibility into their progress.
"""

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import CustomUser, ParentStudentLink

logger = logging.getLogger('rankjee.users')


def request_parent_link(parent: CustomUser, identifier: str) -> ParentStudentLink:
    """Parent requests to link to a student by username or email.

    Creates (or returns the existing) link in a PENDING state — the student must approve
    it before the parent gets any read-only access. Raises ValidationError on bad input.
    """
    identifier = (identifier or '').strip()
    if not identifier:
        raise ValidationError("Enter the student's username or email.")
    if getattr(parent, 'role', None) != CustomUser.Role.PARENT:
        raise ValidationError('Only Parent accounts can request a student link.')

    student = (
        CustomUser.objects.filter(username__iexact=identifier).first()
        or CustomUser.objects.filter(email__iexact=identifier).first()
    )
    if not student:
        raise ValidationError('No account found with that username/email.')
    if student.role != CustomUser.Role.STUDENT:
        raise ValidationError('That account is not a Student.')
    if student.id == parent.id:
        raise ValidationError('You cannot link to yourself.')

    existing = ParentStudentLink.objects.filter(parent=parent, student=student).first()
    if existing:
        return existing

    try:
        link = ParentStudentLink.objects.create(parent=parent, student=student)
    except IntegrityError:
        # Race: created concurrently between the .first() check and .create() above.
        return ParentStudentLink.objects.get(parent=parent, student=student)

    from .gamification import send_notification

    send_notification(
        student,
        f"{parent.get_username()} wants to link as your parent to view your progress. "
        "Approve or ignore from your profile.",
        link='/users/family/',
    )
    return link


def approve_parent_link(student: CustomUser, link_id: int) -> ParentStudentLink:
    link = ParentStudentLink.objects.filter(pk=link_id, student=student).first()
    if not link:
        raise ValidationError('Link request not found.')
    if not link.is_verified:
        link.is_verified = True
        link.verified_at = timezone.now()
        link.save(update_fields=['is_verified', 'verified_at'])

        from .gamification import send_notification

        send_notification(
            link.parent,
            f'{student.get_username()} approved your parent link request.',
            link='/users/family/',
        )
    return link


def remove_parent_link(user: CustomUser, link_id: int) -> bool:
    """Either side (parent or student) can reject a pending request or revoke an
    approved one at any time. Returns True if a link was found and removed."""
    link = ParentStudentLink.objects.filter(pk=link_id).filter(Q(parent=user) | Q(student=user)).first()
    if not link:
        return False
    link.delete()
    return True


def linked_students_for_parent(parent: CustomUser, verified_only: bool = True) -> QuerySet[ParentStudentLink]:
    qs = ParentStudentLink.objects.filter(parent=parent).select_related('student')
    if verified_only:
        qs = qs.filter(is_verified=True)
    return qs


def links_for_student(student: CustomUser) -> QuerySet[ParentStudentLink]:
    return ParentStudentLink.objects.filter(student=student).select_related('parent')


def can_parent_view_student(parent: CustomUser, student: CustomUser) -> bool:
    if not parent or not parent.is_authenticated:
        return False
    return ParentStudentLink.objects.filter(parent=parent, student=student, is_verified=True).exists()


def student_progress_summary(student: CustomUser) -> dict:
    """Lightweight read-only snapshot for a linked parent.

    Deliberately mirrors data the student can already see about themselves (own attempts,
    own enrollments) — a linked parent never sees anything the student couldn't see.
    """
    from assessment.models import UserAttempt
    from dashboard.models import StudentDailyClassLog
    from lms.models import LmsCourseEnrollment

    attempts = UserAttempt.objects.filter(user=student).select_related('skill').order_by('-attempt_date')
    enrollments = LmsCourseEnrollment.objects.filter(user=student).select_related('course', 'course__owner')
    attendance_logs = StudentDailyClassLog.objects.filter(user=student).order_by('-log_date', '-id')

    recent_attendance = list(attendance_logs[:14])
    return {
        'recent_attempts': list(attempts[:5]),
        'total_attempts': attempts.count(),
        'passed_attempts': attempts.filter(passed=True).count(),
        'lms_enrollments': list(enrollments[:10]),
        'xp_points': student.xp_points,
        'streak_days': student.streak_days,
        'wallet_balance': student.wallet_balance,
        'recent_attendance': recent_attendance,
        'attendance_present_count': sum(
            1 for log in recent_attendance if log.attendance == StudentDailyClassLog.Attendance.PRESENT
        ),
        'attendance_total_count': len(recent_attendance),
    }
