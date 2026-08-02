"""Superadmin dashboard aggregation logic.

Backs the main superadmin Command Center at /admin/ (dashboard.views.index, `_staff_only`
branch — rendering templates/dashboard/admin_dashboard_v2.jinja). The original stats/template
(templates/dashboard/admin_dashboard.jinja) are left on disk untouched as a rollback reference
only. Every number here is a real, directly-queried fact — no invented percentages or
decorative trend lines.
"""

from __future__ import annotations

import functools

from decimal import Decimal
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

ZERO = Decimal('0.00')


def cached_stat(ttl: int = 90):
    """Cache a dashboard aggregate for `ttl` seconds (keyed on function name + args).

    Numbers on the Command Center may lag reality by up to `ttl` — acceptable for
    KPI/queue counts; the inline review tables in the view stay live-queried.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = 'dashstat:%s:%s:%s' % (fn.__name__, args, sorted(kwargs.items()))
            sentinel = object()
            value = cache.get(key, sentinel)
            if value is sentinel:
                value = fn(*args, **kwargs)
                cache.set(key, value, ttl)
            return value
        return wrapper
    return decorator


def _window_total(queryset, amount_field: str, since) -> Decimal:
    total = queryset.filter(created_at__gte=since).aggregate(total=Sum(amount_field))['total']
    return total or ZERO


def _pct_change(old, new):
    """None means 'not enough history to compare' (old == 0) — never fabricate a % from nothing."""
    old = float(old or 0)
    new = float(new or 0)
    if old == 0:
        return None
    return round(((new - old) / old) * 100, 1)


def _all_success_revenue_qs():
    """(queryset, amount_field) pairs for every SUCCESS payment source — used by both the
    headline totals and the daily trend chart so they can never drift apart."""
    from core.models import CourseOrder
    from payments.models import PaymentOrder
    from hometutor_payments.models import MarketplaceOrder
    from server_buy.models import StudentServerOrder

    return (
        (CourseOrder.objects.filter(status='SUCCESS'), 'total_inr'),
        (PaymentOrder.objects.filter(status='SUCCESS'), 'amount'),
        (MarketplaceOrder.objects.filter(status='SUCCESS'), 'amount_gross'),
        (StudentServerOrder.objects.filter(status='SUCCESS'), 'total_inr'),
    )


@cached_stat()
def revenue_summary() -> dict:
    """Real money collected (SUCCESS-only) across every payment surface on the platform.

    These are gross amounts actually charged, not net platform profit — e.g. the hometutor
    figure includes the tutor's share (see TutorPayoutRequest for what's still owed to tutors).
    """
    from core.models import CourseOrder
    from payments.models import PaymentOrder
    from hometutor_payments.models import MarketplaceOrder
    from server_buy.models import StudentServerOrder

    now = timezone.now()
    windows = {
        'today': now - timedelta(hours=24),
        'week': now - timedelta(days=7),
        'month': now - timedelta(days=30),
    }

    sources = (
        ('courses', 'Course sales', CourseOrder.objects.filter(status='SUCCESS'), 'total_inr'),
        ('exam_pro', 'Exam Pro subscriptions', PaymentOrder.objects.filter(status='SUCCESS'), 'amount'),
        ('hometutor', 'Hometutor engagements', MarketplaceOrder.objects.filter(status='SUCCESS'), 'amount_gross'),
        ('server_buy', 'Server buy', StudentServerOrder.objects.filter(status='SUCCESS'), 'total_inr'),
    )

    totals = {key: ZERO for key in windows}
    by_source = []
    for key, label, qs, field in sources:
        row = {'key': key, 'label': label}
        for window_key, since in windows.items():
            amount = _window_total(qs, field, since)
            row[window_key] = amount
            totals[window_key] += amount
        by_source.append(row)

    # Hometutor's amount_gross includes the tutor's own cut (paid out via TutorPayoutRequest) —
    # platform_fee_amount is what RankJee actually keeps. Surfaced separately, not folded into
    # `totals`, so "Total revenue collected" stays an honest sum of cash that hit the gateway.
    hometutor_success = MarketplaceOrder.objects.filter(status='SUCCESS')
    platform_fee = {
        window_key: _window_total(hometutor_success, 'platform_fee_amount', since)
        for window_key, since in windows.items()
    }

    return {'totals': totals, 'by_source': by_source, 'hometutor_platform_fee': platform_fee}


@cached_stat()
def week_over_week() -> dict:
    """Real this-week-vs-last-week % change for revenue and signups — replaces the old
    dashboard's fabricated '+12% vs last month' with an honestly computed number. `None` = not
    enough history in the prior window to compare (never shown as a fake 0%/100%)."""
    from django.contrib.auth import get_user_model

    now = timezone.now()
    this_week_start = now - timedelta(days=7)
    last_week_start = now - timedelta(days=14)

    this_week_revenue = ZERO
    last_week_revenue = ZERO
    for qs, field in _all_success_revenue_qs():
        this_week_revenue += _window_total(qs, field, this_week_start)
        last_week_revenue += (
            qs.filter(created_at__gte=last_week_start, created_at__lt=this_week_start).aggregate(
                total=Sum(field)
            )['total']
            or ZERO
        )

    user_model = get_user_model()
    this_week_signups = user_model.objects.filter(date_joined__gte=this_week_start).count()
    last_week_signups = user_model.objects.filter(
        date_joined__gte=last_week_start, date_joined__lt=this_week_start
    ).count()

    return {
        'revenue_this_week': this_week_revenue,
        'revenue_last_week': last_week_revenue,
        'revenue_pct_change': _pct_change(last_week_revenue, this_week_revenue),
        'signups_this_week': this_week_signups,
        'signups_last_week': last_week_signups,
        'signups_pct_change': _pct_change(last_week_signups, this_week_signups),
    }


@cached_stat()
def revenue_trend(days: int = 14) -> list[dict]:
    """Total revenue per day (all sources combined) for the last N days — real bars, no
    interpolation/smoothing."""
    since = timezone.now() - timedelta(days=days - 1)
    by_date: dict = {}
    for qs, field in _all_success_revenue_qs():
        rows = (
            qs.filter(created_at__gte=since)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(total=Sum(field))
        )
        for row in rows:
            by_date[row['day']] = by_date.get(row['day'], ZERO) + (row['total'] or ZERO)

    today = timezone.localdate()
    return [
        {'date': today - timedelta(days=offset), 'amount': by_date.get(today - timedelta(days=offset), ZERO)}
        for offset in range(days - 1, -1, -1)
    ]


@cached_stat()
def signup_trend(days: int = 14) -> list[dict]:
    """New user signups per day for the last N days — real bars."""
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    since = timezone.now() - timedelta(days=days - 1)
    rows = (
        user_model.objects.filter(date_joined__gte=since)
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(count=Count('id'))
    )
    by_date = {row['day']: row['count'] for row in rows}
    today = timezone.localdate()
    return [
        {'date': today - timedelta(days=offset), 'count': by_date.get(today - timedelta(days=offset), 0)}
        for offset in range(days - 1, -1, -1)
    ]


@cached_stat()
def balance_sheet_summary() -> dict:
    """Money the platform currently holds/owes — a founder-level snapshot, not a queue."""
    from django.contrib.auth import get_user_model
    from payments.models import UserSubscription
    from users.models import WithdrawalRequest
    from hometutor_payments.models import TutorPayoutRequest

    user_model = get_user_model()
    wallet_liability = user_model.objects.aggregate(total=Sum('wallet_balance'))['total'] or ZERO
    active_subscriptions = UserSubscription.objects.filter(
        is_active=True, end_date__gte=timezone.now()
    ).count()
    pending_withdrawals = (
        WithdrawalRequest.objects.filter(status='PENDING').aggregate(total=Sum('amount'))['total'] or ZERO
    )
    pending_payouts = (
        TutorPayoutRequest.objects.filter(status='PENDING').aggregate(total=Sum('amount'))['total'] or ZERO
    )
    return {
        'wallet_liability': wallet_liability,
        'active_subscriptions': active_subscriptions,
        'pending_withdrawals': pending_withdrawals,
        'pending_payouts': pending_payouts,
        'total_owed': wallet_liability + pending_withdrawals + pending_payouts,
    }


@cached_stat()
def hurdle_skills(limit: int = 5) -> list:
    """Real weakest-performing tests (lowest avg score, attempted at least once) — a genuine
    content-quality signal, not decoration. Restored from the old dashboard's `difficult_skills`."""
    from assessment.models import Skill

    return list(
        Skill.objects.filter(is_active=True)
        .annotate(total_attempts=Count('userattempt'), avg_score=Avg('userattempt__score'))
        .filter(total_attempts__gt=0)
        .order_by('avg_score')[:limit]
    )


@cached_stat()
def growth_summary() -> dict:
    """Real signup/activity counts — no fake trend arrows."""
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    now = timezone.now()
    today_start = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    week_ago_date = timezone.localdate() - timedelta(days=7)

    return {
        'total_users': user_model.objects.count(),
        'new_today': user_model.objects.filter(date_joined__gte=today_start).count(),
        'new_week': user_model.objects.filter(date_joined__gte=week_ago).count(),
        'new_month': user_model.objects.filter(date_joined__gte=month_ago).count(),
        'active_week': user_model.objects.filter(last_active_date__gte=week_ago_date).count(),
    }


@cached_stat()
def action_center() -> list[dict]:
    """Every queue a superadmin might genuinely need to act on today, one row each.

    `amount` is None for non-money queues. `url` links straight to the filtered /sd/ admin
    list (or an in-page anchor for items reviewed inline further down the dashboard).
    """
    from core.models import CourseReferral, TutorLeadRequest, UserTaskSubmission
    from users.models import WithdrawalRequest
    from hometutor.models import DemoRequest, EngagementChatMessage, EngagementDispute, TutorDocument, TutorProfile
    from hometutor_payments.models import TutorPayoutRequest
    from lms import services as lms_services

    withdrawals = WithdrawalRequest.objects.filter(status='PENDING')
    payouts = TutorPayoutRequest.objects.filter(status='PENDING')

    from lms.models import LmsSubmission

    lms_pending_grading = LmsSubmission.objects.filter(status='SUBMITTED').count()

    return [
        # ── CRITICAL (disputes, flagged chats) ─────────────────────────────
        {
            'label': 'Open hometutor disputes',
            'count': EngagementDispute.objects.filter(
                status__in=[EngagementDispute.Status.OPEN, EngagementDispute.Status.IN_REVIEW]
            ).count(),
            'amount': None,
            'url': '/sd/hometutor/engagementdispute/?status__exact=OPEN',
            'icon': '⚡',
            'priority': 'critical',
        },
        {
            'label': 'Chat messages flagged for support',
            'count': EngagementChatMessage.objects.filter(support_flag=True).count(),
            'amount': None,
            'url': '/sd/hometutor/engagementchatmessage/?support_flag__exact=1',
            'icon': '💬',
            'priority': 'critical',
        },
        # ── MONEY (real ₹ moving) ────────────────────────────────────────────
        {
            'label': 'UPI withdrawal requests pending',
            'count': withdrawals.count(),
            'amount': withdrawals.aggregate(total=Sum('amount'))['total'] or ZERO,
            'url': '/sd/users/withdrawalrequest/?status__exact=PENDING',
            'icon': '💸',
            'priority': 'warning',
        },
        {
            'label': 'Tutor payout requests pending',
            'count': payouts.count(),
            'amount': payouts.aggregate(total=Sum('amount'))['total'] or ZERO,
            'url': '/sd/hometutor_payments/tutorpayoutrequest/?status__exact=PENDING',
            'icon': '💸',
            'priority': 'warning',
        },
        {
            'label': 'Course referral commissions awaiting review',
            'count': CourseReferral.objects.filter(status=CourseReferral.Status.PENDING).count(),
            'amount': CourseReferral.objects.filter(status=CourseReferral.Status.PENDING).aggregate(
                total=Sum('commission_amount')
            )['total'] or ZERO,
            'url': '/sd/core/coursereferral/?status__exact=PENDING',
            'icon': '💰',
            'priority': 'warning',
        },
        # ── VERIFICATION (new tutor onboarding) ──────────────────────────────
        {
            'label': 'New tutor listings awaiting verification',
            'count': TutorProfile.objects.filter(verification_status='PENDING').count(),
            'amount': None,
            'url': '/sd/hometutor/tutorprofile/?verification_status__exact=PENDING',
            'icon': '🪪',
            'priority': 'warning',
        },
        {
            'label': 'Tutor KYC documents awaiting review',
            'count': TutorDocument.objects.filter(status=TutorDocument.DocStatus.PENDING).count(),
            'amount': None,
            'url': '/sd/hometutor/tutordocument/?status__exact=PENDING',
            'icon': '📄',
            'priority': 'warning',
        },
        # ── REVIEW QUEUES ────────────────────────────────────────────────────
        {
            'label': 'Freelance task submissions to review',
            'count': UserTaskSubmission.objects.filter(status='PENDING').count(),
            'amount': None,
            'anchor': '#task-review',
            'icon': '📋',
            'priority': 'info',
        },
        {
            'label': 'Demo requests pending',
            'count': DemoRequest.objects.filter(status=DemoRequest.Status.PENDING).count(),
            'amount': None,
            'anchor': '#demo-requests',
            'icon': '📅',
            'priority': 'info',
        },
        {
            'label': 'New tutor requirement leads',
            'count': TutorLeadRequest.objects.filter(status=TutorLeadRequest.Status.NEW).count(),
            'amount': None,
            'anchor': '#tutor-leads',
            'icon': '🎯',
            'priority': 'info',
        },
        # ── LMS ──────────────────────────────────────────────────────────────
        {
            'label': 'LMS submissions awaiting faculty grading',
            'count': lms_pending_grading,
            'amount': None,
            'url': '/admin/lms/',
            'icon': '📚',
            'priority': 'info',
        },
        {
            'label': 'Course purchases without an LMS batch assigned',
            'count': len(lms_services.purchases_missing_lms_enrollment()),
            'amount': None,
            'url': '/admin/lms/courses/',
            'icon': '🎓',
            'priority': 'warning',
        },
    ]


@cached_stat()
def lms_health_summary() -> dict:
    """Quick stats for the Faculty & Course quick-setup panel header."""
    from django.db.models import Count as _Count
    from lms.models import LmsCourse, LmsCourseEnrollment, LmsSubmission

    active = LmsCourse.objects.filter(is_active=True)
    total_courses = active.count()
    courses_no_faculty = active.filter(owner__isnull=True).count()
    courses_no_students = active.annotate(_ec=_Count('enrollments')).filter(_ec=0).count()
    courses_no_assignments = active.annotate(_ac=_Count('assignments')).filter(_ac=0).count()
    total_students = LmsCourseEnrollment.objects.values('user').distinct().count()
    pending_grading = LmsSubmission.objects.filter(status='SUBMITTED').count()
    return {
        'total_courses': total_courses,
        'courses_no_faculty': courses_no_faculty,
        'courses_no_students': courses_no_students,
        'courses_no_assignments': courses_no_assignments,
        'total_students': total_students,
        'pending_grading': pending_grading,
        'needs_attention': courses_no_faculty + courses_no_students + courses_no_assignments,
    }


@cached_stat()
def backup_health() -> dict:
    """Is the most recent backup recent enough to trust? No status field exists on
    BackupArtifact (rows are only ever written on success), so staleness is the only signal."""
    from .models import BackupArtifact

    latest = BackupArtifact.objects.order_by('-created_at').first()
    if not latest:
        return {'latest': None, 'is_stale': True, 'days_old': None}
    days_old = (timezone.now() - latest.created_at).days
    return {'latest': latest, 'is_stale': days_old > 7, 'days_old': days_old}


@cached_stat()
def content_inventory() -> dict:
    """Low-priority reference counts — de-emphasized on the dashboard, not action items."""
    from assessment.models import Question, Skill
    from learning.models import ConceptVideo

    return {
        'total_questions': Question.objects.count(),
        'total_videos': ConceptVideo.objects.count(),
        'total_skills': Skill.objects.filter(is_active=True).count(),
    }


@cached_stat(ttl=60)
def recent_joins(limit: int = 15) -> list[dict]:
    """Newest public-role signups (student/parent/tutor/faculty) for the Command Center —
    entry info (role, contact, joined) + whether they've paid anything yet, across all 4
    payment surfaces. Answers "who just joined and are they converting?" at a glance."""
    from django.contrib.auth import get_user_model

    from core.models import CourseOrder
    from payments.models import PaymentOrder
    from hometutor_payments.models import MarketplaceOrder
    from server_buy.models import StudentServerOrder

    user_model = get_user_model()
    users = list(
        user_model.objects.filter(role__in=('STUDENT', 'PARENT', 'TUTOR', 'FACULTY'))
        .order_by('-date_joined')[:limit]
    )
    ids = [u.pk for u in users]

    paid_totals: dict[int, Decimal] = {}
    for qs, amount_field, user_field in (
        (CourseOrder.objects.filter(status='SUCCESS'), 'total_inr', 'user_id'),
        (PaymentOrder.objects.filter(status='SUCCESS'), 'amount', 'user_id'),
        (MarketplaceOrder.objects.filter(status='SUCCESS'), 'amount_gross', 'payer_id'),
        (StudentServerOrder.objects.filter(status='SUCCESS'), 'total_inr', 'user_id'),
    ):
        rows = (
            qs.filter(**{f'{user_field}__in': ids})
            .values(user_field)
            .annotate(total=Sum(amount_field))
        )
        for row in rows:
            uid = row[user_field]
            paid_totals[uid] = paid_totals.get(uid, ZERO) + (row['total'] or ZERO)

    return [
        {
            'id': u.pk,
            'username': u.get_username(),
            'role': u.role,
            'phone': u.phone,
            'city': u.city,
            'email': u.email,
            'joined': u.date_joined,
            'onboarded': u.onboarding_completed,
            'paid_total': paid_totals.get(u.pk, ZERO),
            'has_paid': paid_totals.get(u.pk, ZERO) > 0,
        }
        for u in users
    ]


@cached_stat(ttl=300)
def student_recommendations(class_level, subjects_csv: str, limit: int = 4) -> list[dict]:
    """Catalog courses matched to a student's academic profile (fab_student.md S3).

    Match order: structured Course.class_level == student's class, then "Class {n}"
    in the title, then subject keywords. Falls back to featured/top courses so the
    "For you" strip is never empty. Cached per (class, subjects) for 5 min.
    """
    from core.models import Course

    subjects = [s.strip() for s in (subjects_csv or '').split(',') if s.strip()]
    base = Course.objects.filter(is_active=True)
    matched: list = []
    seen: set[int] = set()

    def _take(qs):
        for course in qs:
            if course.pk not in seen and len(matched) < limit:
                seen.add(course.pk)
                matched.append(course)

    if class_level:
        _take(base.filter(class_level=class_level))
        _take(base.filter(title__icontains=f'Class {class_level}'))
    for subject in subjects[:3]:
        _take(base.filter(title__icontains=subject))
    if len(matched) < limit:
        _take(base.filter(is_featured=True))
    if len(matched) < limit:
        _take(base.order_by('-created_at'))

    return [
        {
            'id': c.pk,
            'title': c.title,
            'slug': c.slug,
            'price_inr': c.price_inr,
            'allow_monthly': c.allow_monthly,
            'monthly_price_inr': c.monthly_price_inr,
            'thumbnail_url': c.thumbnail_url,
            'level': c.level,
        }
        for c in matched
    ]
