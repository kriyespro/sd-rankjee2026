import logging
import ipaddress
import calendar

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.core.exceptions import PermissionDenied
from django.core.cache import cache
from django.db.models import Sum, Q, Count, Avg, Case, When, IntegerField, Max, OuterRef, Subquery
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta, date
from assessment.models import UserAttempt, Question, Skill, UserSetAttempt
from assessment.models import SkillPath
from core.models import TutorLeadRequest, UserTaskSubmission
from core.models import EarningTask
from learning.models import ConceptVideo
from users.models import Notification, WithdrawalRequest
from django.db import transaction
import csv
import io
import os
import requests
from urllib.parse import urlencode

from blog.blog_niche import NICHE_REQUIREMENT_USER_MESSAGE
from blog.models import BlogCategory, BlogPost

from .forms import (
    EarningTaskForm,
    ConceptVideoForm,
    QuestionForm,
    SkillForm,
    SkillPathForm,
    StudentDailyClassLogForm,
    VideoQuestionImportForm,
    VipBlogPostForm,
    VipManualUserForm,
)
try:
    from .models import SeoTarget
except ImportError:
    SeoTarget = None
from .backup_utils import create_backups, delete_backup_artifact, notify_superusers_for_backups
from .models import BackupArtifact, StudentDailyClassLog
try:
    from axes.models import AccessLog
except ImportError:
    AccessLog = None

User = get_user_model()
logger = logging.getLogger("rankjee.dashboard")


def _calendar_view_context(logs_qs, month_raw):
    today = timezone.localdate()
    month_value = (month_raw or "").strip()
    try:
        year_str, month_str = month_value.split("-", 1)
        year = int(year_str)
        month = int(month_str)
        current_month_date = date(year, month, 1)
    except Exception:
        current_month_date = date(today.year, today.month, 1)
        month_value = current_month_date.strftime("%Y-%m")

    month_logs = list(
        logs_qs.filter(
            log_date__year=current_month_date.year,
            log_date__month=current_month_date.month,
        ).order_by("log_date", "id")
    )
    logs_by_date = {}
    for row in month_logs:
        logs_by_date.setdefault(row.log_date, []).append(row)

    cal = calendar.Calendar(firstweekday=0)
    calendar_weeks = []
    for week in cal.monthdatescalendar(current_month_date.year, current_month_date.month):
        calendar_weeks.append(
            [
                {
                    "date": day,
                    "in_month": day.month == current_month_date.month,
                    "logs": logs_by_date.get(day, []),
                }
                for day in week
            ]
        )

    prev_month = date(
        current_month_date.year - 1 if current_month_date.month == 1 else current_month_date.year,
        12 if current_month_date.month == 1 else current_month_date.month - 1,
        1,
    )
    next_month = date(
        current_month_date.year + 1 if current_month_date.month == 12 else current_month_date.year,
        1 if current_month_date.month == 12 else current_month_date.month + 1,
        1,
    )

    return {
        "calendar_weeks": calendar_weeks,
        "calendar_month_label": current_month_date.strftime("%B %Y"),
        "calendar_month_value": month_value,
        "calendar_prev_month": prev_month.strftime("%Y-%m"),
        "calendar_next_month": next_month.strftime("%Y-%m"),
        "calendar_total_logs": len(month_logs),
    }


def _location_from_ip(ip_address):
    if not ip_address:
        return ""
    try:
        ip_obj = ipaddress.ip_address(ip_address)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
            return "Private/Local IP"
    except ValueError:
        return ""

    cache_key = f"geoip:ip:{ip_address}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    location = ""
    try:
        resp = requests.get(
            "https://ipwho.is/" + ip_address,
            timeout=1.5,
        )
        data = resp.json() if resp.ok else {}
        if data.get("success"):
            city = (data.get("city") or "").strip()
            region = (data.get("region") or "").strip()
            country = (data.get("country") or "").strip()
            location = ", ".join([p for p in [city, region, country] if p])
    except Exception:
        location = ""

    cache.set(cache_key, location, 60 * 60 * 24)
    return location


def _role_dashboard_context(request):
    """Build focused, role-wise context for non-student dashboards."""
    from hometutor.models import DemoRequest, TutorProfile, TutorEngagement, EngagementDispute, SessionAttendance
    from hometutor_payments.models import MarketplaceOrder, TutorLedgerEntry, TutorPayoutRequest

    role = getattr(request.user, 'role', 'STUDENT')
    user = request.user
    now = timezone.now()

    if role == 'TUTOR':
        tutor_profile = TutorProfile.objects.filter(user=user).first()
        tutor_preview_mode = False
        if not tutor_profile:
            tutor_profile = (
                TutorProfile.objects.filter(
                    verification_status=TutorProfile.VerificationStatus.APPROVED
                )
                .order_by('-reviews_count', '-rating_display')
                .first()
            )
            tutor_preview_mode = bool(tutor_profile)
        pending_incoming = (
            DemoRequest.objects.filter(
                tutor=tutor_profile,
                status=DemoRequest.Status.PENDING,
            ).count()
            if tutor_profile
            else 0
        )
        accepted_demos = (
            DemoRequest.objects.filter(
                tutor=tutor_profile,
                status=DemoRequest.Status.ACCEPTED,
            ).count()
            if tutor_profile
            else 0
        )
        active_engagements = (
            TutorEngagement.objects.filter(
                tutor_profile=tutor_profile,
                status=TutorEngagement.Status.ACTIVE,
            ).count()
            if tutor_profile
            else 0
        )
        open_disputes = (
            EngagementDispute.objects.filter(
                engagement__tutor_profile=tutor_profile,
                status__in=[EngagementDispute.Status.OPEN, EngagementDispute.Status.IN_REVIEW],
            ).count()
            if tutor_profile
            else 0
        )
        total_demos = (
            DemoRequest.objects.filter(tutor=tutor_profile).count()
            if tutor_profile
            else 0
        )
        latest_pending_demos = (
            DemoRequest.objects.filter(
                tutor=tutor_profile,
                status=DemoRequest.Status.PENDING,
            )
            .select_related('requester')
            .order_by('-created_at')[:5]
            if tutor_profile
            else []
        )
        latest_active_engagements = (
            TutorEngagement.objects.filter(
                tutor_profile=tutor_profile,
                status=TutorEngagement.Status.ACTIVE,
            )
            .select_related('student')
            .order_by('-updated_at')[:5]
            if tutor_profile
            else []
        )
        tutor_paid_orders = (
            MarketplaceOrder.objects.filter(
                engagement__tutor_profile=tutor_profile,
                status=MarketplaceOrder.Status.SUCCESS,
            )
            if tutor_profile
            else MarketplaceOrder.objects.none()
        )
        tutor_paid_count = tutor_paid_orders.count()
        tutor_total_credits = tutor_paid_orders.aggregate(total=Sum('tutor_credit_amount'))['total'] or 0
        tutor_month_credits = tutor_paid_orders.filter(
            paid_at__gte=now - timedelta(days=30)
        ).aggregate(total=Sum('tutor_credit_amount'))['total'] or 0
        tutor_pending_payout = (
            TutorPayoutRequest.objects.filter(
                tutor_profile=tutor_profile,
                status=TutorPayoutRequest.Status.PENDING,
            ).aggregate(total=Sum('amount'))['total'] or 0
            if tutor_profile
            else 0
        )
        latest_ledger = (
            TutorLedgerEntry.objects.filter(tutor_profile=tutor_profile).order_by('-id').first()
            if tutor_profile
            else None
        )
        tutor_current_balance = latest_ledger.balance_after if latest_ledger else 0
        tutor_recent_ledger = (
            TutorLedgerEntry.objects.filter(tutor_profile=tutor_profile).order_by('-created_at')[:5]
            if tutor_profile
            else []
        )
        upcoming_sessions_count = (
            SessionAttendance.objects.filter(
                engagement__tutor_profile=tutor_profile,
                scheduled_for__gte=now,
            ).count()
            if tutor_profile
            else 0
        )
        stale_active_engagement_count = (
            TutorEngagement.objects.filter(
                tutor_profile=tutor_profile,
                status=TutorEngagement.Status.ACTIVE,
                updated_at__lt=now - timedelta(days=7),
            ).count()
            if tutor_profile
            else 0
        )
        accepted_rate = round((accepted_demos / total_demos) * 100, 1) if total_demos else 0
        active_rate = round((active_engagements / accepted_demos) * 100, 1) if accepted_demos else 0
        paid_rate = round((tutor_paid_count / active_engagements) * 100, 1) if active_engagements else 0
        tutor_demo_sla_risk_ids = [
            d.pk for d in latest_pending_demos if (now - d.created_at).total_seconds() > (24 * 3600)
        ]
        activity_timeline = []
        for d in latest_pending_demos[:4]:
            activity_timeline.append(
                {
                    'title': f'New demo request from {d.requester.get_username()}',
                    'meta': d.created_at,
                }
            )
        for e in latest_active_engagements[:4]:
            activity_timeline.append(
                {
                    'title': f'Engagement active with {e.student.get_username()}',
                    'meta': e.updated_at,
                }
            )
        activity_timeline = sorted(activity_timeline, key=lambda x: x['meta'], reverse=True)[:8]
        return {
            'kpi_cards': [
                {'label': 'Incoming demos', 'value': pending_incoming},
                {'label': 'Accepted demos', 'value': accepted_demos},
                {'label': 'Active students', 'value': active_engagements},
                {'label': 'Open disputes', 'value': open_disputes},
            ],
            'tutor_profile': tutor_profile,
            'tutor_preview_mode': tutor_preview_mode,
            'pending_incoming': pending_incoming,
            'accepted_demos': accepted_demos,
            'active_engagements': active_engagements,
            'open_disputes': open_disputes,
            'latest_pending_demos': latest_pending_demos,
            'latest_active_engagements': latest_active_engagements,
            'tutor_total_credits': tutor_total_credits,
            'tutor_month_credits': tutor_month_credits,
            'tutor_pending_payout': tutor_pending_payout,
            'tutor_current_balance': tutor_current_balance,
            'tutor_recent_ledger': tutor_recent_ledger,
            'upcoming_sessions_count': upcoming_sessions_count,
            'stale_active_engagement_count': stale_active_engagement_count,
            'total_demos': total_demos,
            'accepted_rate': accepted_rate,
            'active_rate': active_rate,
            'paid_rate': paid_rate,
            'tutor_paid_count': tutor_paid_count,
            'tutor_demo_sla_risk_ids': tutor_demo_sla_risk_ids,
            'tutor_demo_sla_risk_count': len(tutor_demo_sla_risk_ids),
            'activity_timeline': activity_timeline,
            'template_name': 'dashboard/role_tutor.jinja',
        }

    if role == 'PARENT':
        pending_sent = DemoRequest.objects.filter(
            requester=user,
            status=DemoRequest.Status.PENDING,
        ).count()
        accepted_sent = DemoRequest.objects.filter(
            requester=user,
            status=DemoRequest.Status.ACCEPTED,
        ).count()
        active_learning = TutorEngagement.objects.filter(
            student=user,
            status=TutorEngagement.Status.ACTIVE,
        ).count()
        support_cases = EngagementDispute.objects.filter(
            raised_by=user,
            status__in=[EngagementDispute.Status.OPEN, EngagementDispute.Status.IN_REVIEW],
        ).count()
        latest_demo_requests = (
            DemoRequest.objects.filter(requester=user)
            .select_related('tutor')
            .order_by('-created_at')[:6]
        )
        latest_learning_engagements = (
            TutorEngagement.objects.filter(student=user)
            .select_related('tutor_profile')
            .order_by('-updated_at')[:6]
        )
        parent_paid_orders = MarketplaceOrder.objects.filter(
            payer=user,
            status=MarketplaceOrder.Status.SUCCESS,
        )
        parent_monthly_spend = parent_paid_orders.filter(
            paid_at__gte=now - timedelta(days=30)
        ).aggregate(total=Sum('amount_gross'))['total'] or 0
        parent_total_spend = parent_paid_orders.aggregate(total=Sum('amount_gross'))['total'] or 0
        parent_pending_payment_count = TutorEngagement.objects.filter(
            student=user,
            status=TutorEngagement.Status.ACTIVE,
        ).exclude(
            marketplace_order__status=MarketplaceOrder.Status.SUCCESS,
        ).count()
        parent_sessions_total = SessionAttendance.objects.filter(engagement__student=user).count()
        parent_sessions_present = SessionAttendance.objects.filter(
            engagement__student=user,
            status=SessionAttendance.AttendanceStatus.PRESENT,
        ).count()
        parent_attendance_rate = (
            round((parent_sessions_present / parent_sessions_total) * 100, 1)
            if parent_sessions_total
            else 0
        )
        parent_demo_sla_risk_ids = [
            d.pk
            for d in latest_demo_requests
            if d.status == DemoRequest.Status.PENDING and (now - d.created_at).total_seconds() > (24 * 3600)
        ]
        parent_next_actions = []
        if parent_demo_sla_risk_ids:
            parent_next_actions.append('Follow up on pending demo requests older than 24h.')
        if parent_pending_payment_count > 0:
            parent_next_actions.append('Complete pending engagement payments to avoid class disruption.')
        if parent_attendance_rate and parent_attendance_rate < 80:
            parent_next_actions.append('Improve attendance rhythm; target at least 80% consistency.')
        if not parent_next_actions:
            parent_next_actions.append('All key metrics are healthy. Continue weekly review cadence.')
        activity_timeline = []
        for d in latest_demo_requests[:5]:
            activity_timeline.append(
                {
                    'title': f'Demo request {d.get_status_display()} with {d.tutor.display_name}',
                    'meta': d.updated_at,
                }
            )
        for e in latest_learning_engagements[:5]:
            activity_timeline.append(
                {
                    'title': f'Learning engagement {e.get_status_display()} with {e.tutor_profile.display_name}',
                    'meta': e.updated_at,
                }
            )
        activity_timeline = sorted(activity_timeline, key=lambda x: x['meta'], reverse=True)[:8]
        return {
            'kpi_cards': [
                {'label': 'Pending approvals', 'value': pending_sent},
                {'label': 'Tutor demos booked', 'value': accepted_sent},
                {'label': 'Active engagements', 'value': active_learning},
                {'label': 'Open support cases', 'value': support_cases},
            ],
            'pending_sent': pending_sent,
            'accepted_sent': accepted_sent,
            'active_learning': active_learning,
            'support_cases': support_cases,
            'latest_demo_requests': latest_demo_requests,
            'latest_learning_engagements': latest_learning_engagements,
            'parent_monthly_spend': parent_monthly_spend,
            'parent_total_spend': parent_total_spend,
            'parent_pending_payment_count': parent_pending_payment_count,
            'parent_attendance_rate': parent_attendance_rate,
            'parent_next_actions': parent_next_actions,
            'parent_demo_sla_risk_ids': parent_demo_sla_risk_ids,
            'parent_demo_sla_risk_count': len(parent_demo_sla_risk_ids),
            'activity_timeline': activity_timeline,
            'template_name': 'dashboard/role_parent.jinja',
        }

    if role == 'CITY_ADMIN':
        scoped_users = User.objects.filter(state=user.state) if user.state else User.objects.none()
        city_tutor_qs = (
            TutorProfile.objects.filter(user__state=user.state)
            if user.state
            else TutorProfile.objects.none()
        )
        city_tutors = city_tutor_qs.count()
        pending_verification = city_tutor_qs.filter(
            verification_status=TutorProfile.VerificationStatus.PENDING
        ).count()
        pending_disputes_qs = (
            EngagementDispute.objects.filter(
                status__in=[EngagementDispute.Status.OPEN, EngagementDispute.Status.IN_REVIEW],
                engagement__student__state=user.state,
            )
            if user.state
            else EngagementDispute.objects.none()
        )
        pending_disputes = pending_disputes_qs.count()
        pending_withdrawals = (
            WithdrawalRequest.objects.filter(status='PENDING', user__state=user.state).count()
            if user.state
            else 0
        )
        city_demo_qs = (
            DemoRequest.objects.filter(requester__state=user.state)
            if user.state
            else DemoRequest.objects.all()
        )
        city_total_demos = city_demo_qs.count()
        city_accepted_demos = city_demo_qs.filter(status=DemoRequest.Status.ACCEPTED).count()
        city_active_engagements = (
            TutorEngagement.objects.filter(student__state=user.state, status=TutorEngagement.Status.ACTIVE).count()
            if user.state
            else TutorEngagement.objects.filter(status=TutorEngagement.Status.ACTIVE).count()
        )
        city_paid_orders = (
            MarketplaceOrder.objects.filter(engagement__student__state=user.state, status=MarketplaceOrder.Status.SUCCESS)
            if user.state
            else MarketplaceOrder.objects.filter(status=MarketplaceOrder.Status.SUCCESS)
        )
        city_gmv_30d = city_paid_orders.filter(paid_at__gte=now - timedelta(days=30)).aggregate(total=Sum('amount_gross'))['total'] or 0
        city_accepted_rate = round((city_accepted_demos / city_total_demos) * 100, 1) if city_total_demos else 0
        city_active_rate = round((city_active_engagements / city_accepted_demos) * 100, 1) if city_accepted_demos else 0
        city_paid_rate = round((city_paid_orders.count() / city_active_engagements) * 100, 1) if city_active_engagements else 0
        latest_pending_tutors = city_tutor_qs.filter(
            verification_status=TutorProfile.VerificationStatus.PENDING
        ).order_by('-updated_at')[:8]
        latest_disputes = pending_disputes_qs.select_related(
            'engagement__student', 'engagement__tutor_profile'
        ).order_by('-updated_at')[:8]
        city_verification_sla_risk_ids = [
            t.pk for t in latest_pending_tutors if (now - t.updated_at).total_seconds() > (48 * 3600)
        ]
        city_dispute_sla_risk_ids = [
            d.pk for d in latest_disputes if (now - d.updated_at).total_seconds() > (24 * 3600)
        ]
        city_next_actions = []
        if city_verification_sla_risk_ids:
            city_next_actions.append('Clear aged tutor verification queue to protect onboarding SLA.')
        if city_dispute_sla_risk_ids:
            city_next_actions.append('Resolve stale disputes first to reduce trust risk in city operations.')
        if city_paid_rate < 50 and city_total_demos >= 5:
            city_next_actions.append('Investigate low paid-rate: review engagement follow-through and payment friction.')
        if not city_next_actions:
            city_next_actions.append('City health looks stable. Continue daily queue hygiene and weekly funnel audits.')
        activity_timeline = []
        for t in latest_pending_tutors[:5]:
            activity_timeline.append(
                {
                    'title': f'Verification pending: {t.display_name}',
                    'meta': t.updated_at,
                }
            )
        for d in latest_disputes[:5]:
            activity_timeline.append(
                {
                    'title': f'Dispute {d.get_status_display()} for {d.engagement.tutor_profile.display_name}',
                    'meta': d.updated_at,
                }
            )
        activity_timeline = sorted(activity_timeline, key=lambda x: x['meta'], reverse=True)[:8]
        return {
            'kpi_cards': [
                {'label': 'Users in scope', 'value': scoped_users.count()},
                {'label': 'Tutor verifications pending', 'value': pending_verification},
                {'label': 'Live dispute queue', 'value': pending_disputes},
                {'label': 'Pending withdrawals', 'value': pending_withdrawals},
            ],
            'scoped_users_count': scoped_users.count(),
            'city_tutors_count': city_tutors,
            'pending_verification': pending_verification,
            'pending_disputes': pending_disputes,
            'pending_withdrawals': pending_withdrawals,
            'city_total_demos': city_total_demos,
            'city_accepted_demos': city_accepted_demos,
            'city_active_engagements': city_active_engagements,
            'city_paid_count': city_paid_orders.count(),
            'city_gmv_30d': city_gmv_30d,
            'city_accepted_rate': city_accepted_rate,
            'city_active_rate': city_active_rate,
            'city_paid_rate': city_paid_rate,
            'city_next_actions': city_next_actions,
            'latest_pending_tutors': latest_pending_tutors,
            'latest_disputes': latest_disputes,
            'city_verification_sla_risk_ids': city_verification_sla_risk_ids,
            'city_dispute_sla_risk_ids': city_dispute_sla_risk_ids,
            'city_sla_risk_count': len(city_verification_sla_risk_ids) + len(city_dispute_sla_risk_ids),
            'activity_timeline': activity_timeline,
            'template_name': 'dashboard/role_city_admin.jinja',
        }

    if role == 'GLOBAL_ADMIN':
        total_users = User.objects.count()
        total_tutors = TutorProfile.objects.count()
        pending_verification = TutorProfile.objects.filter(
            verification_status=TutorProfile.VerificationStatus.PENDING
        ).count()
        live_disputes = EngagementDispute.objects.filter(
            status__in=[EngagementDispute.Status.OPEN, EngagementDispute.Status.IN_REVIEW]
        ).count()
        open_withdrawals = WithdrawalRequest.objects.filter(status='PENDING').count()
        global_total_demos = DemoRequest.objects.count()
        global_accepted_demos = DemoRequest.objects.filter(status=DemoRequest.Status.ACCEPTED).count()
        global_active_engagements = TutorEngagement.objects.filter(status=TutorEngagement.Status.ACTIVE).count()
        global_paid_orders_qs = MarketplaceOrder.objects.filter(status=MarketplaceOrder.Status.SUCCESS)
        global_paid_count = global_paid_orders_qs.count()
        global_gmv_30d = global_paid_orders_qs.filter(paid_at__gte=now - timedelta(days=30)).aggregate(total=Sum('amount_gross'))['total'] or 0
        global_platform_rev_30d = global_paid_orders_qs.filter(paid_at__gte=now - timedelta(days=30)).aggregate(total=Sum('platform_fee_amount'))['total'] or 0
        global_accepted_rate = round((global_accepted_demos / global_total_demos) * 100, 1) if global_total_demos else 0
        global_active_rate = round((global_active_engagements / global_accepted_demos) * 100, 1) if global_accepted_demos else 0
        global_paid_rate = round((global_paid_count / global_active_engagements) * 100, 1) if global_active_engagements else 0
        latest_pending_tutors = TutorProfile.objects.filter(
            verification_status=TutorProfile.VerificationStatus.PENDING
        ).order_by('-updated_at')[:10]
        latest_disputes = EngagementDispute.objects.filter(
            status__in=[EngagementDispute.Status.OPEN, EngagementDispute.Status.IN_REVIEW]
        ).select_related('engagement__student', 'engagement__tutor_profile').order_by('-updated_at')[:10]
        latest_withdrawals = WithdrawalRequest.objects.filter(status='PENDING').select_related('user').order_by('-requested_at')[:10]
        recent_failed_attempts = (
            UserAttempt.objects.filter(passed=False)
            .select_related("user", "skill")
            .order_by("-attempt_date")[:12]
        )
        global_verification_sla_risk_ids = [
            t.pk for t in latest_pending_tutors if (now - t.updated_at).total_seconds() > (48 * 3600)
        ]
        global_dispute_sla_risk_ids = [
            d.pk for d in latest_disputes if (now - d.updated_at).total_seconds() > (24 * 3600)
        ]
        global_withdrawal_sla_risk_ids = [
            w.pk for w in latest_withdrawals if (now - w.requested_at).total_seconds() > (24 * 3600)
        ]
        global_next_actions = []
        if global_accepted_rate < 40 and global_total_demos >= 10:
            global_next_actions.append('Improve top-of-funnel acceptance by reviewing tutor response speed and profile quality.')
        if global_paid_rate < 50 and global_active_engagements >= 10:
            global_next_actions.append('Prioritize payment conversion improvements for active engagements.')
        if global_sla_risk_ids := (
            len(global_verification_sla_risk_ids)
            + len(global_dispute_sla_risk_ids)
            + len(global_withdrawal_sla_risk_ids)
        ):
            global_next_actions.append(f'Address {global_sla_risk_ids} SLA-risk governance items immediately.')
        if not global_next_actions:
            global_next_actions.append('Global metrics are stable. Continue monitoring weekly cohort and revenue trends.')
        activity_timeline = []
        for t in latest_pending_tutors[:5]:
            activity_timeline.append(
                {
                    'title': f'Pending verification: {t.display_name} ({t.city})',
                    'meta': t.updated_at,
                }
            )
        for d in latest_disputes[:5]:
            activity_timeline.append(
                {
                    'title': f'Dispute {d.get_status_display()} in engagement {d.engagement_id}',
                    'meta': d.updated_at,
                }
            )
        for w in latest_withdrawals[:5]:
            activity_timeline.append(
                {
                    'title': f'Withdrawal pending for {w.user.get_username()} (₹{w.amount})',
                    'meta': w.requested_at,
                }
            )
        activity_timeline = sorted(activity_timeline, key=lambda x: x['meta'], reverse=True)[:10]
        return {
            'kpi_cards': [
                {'label': 'Total users', 'value': total_users},
                {'label': 'Tutor supply', 'value': total_tutors},
                {'label': 'Pending verification', 'value': pending_verification},
                {'label': 'Live disputes', 'value': live_disputes},
            ],
            'total_users_count': total_users,
            'total_tutors_count': total_tutors,
            'pending_verification': pending_verification,
            'live_disputes': live_disputes,
            'open_withdrawals': open_withdrawals,
            'global_total_demos': global_total_demos,
            'global_accepted_demos': global_accepted_demos,
            'global_active_engagements': global_active_engagements,
            'global_paid_count': global_paid_count,
            'global_gmv_30d': global_gmv_30d,
            'global_platform_rev_30d': global_platform_rev_30d,
            'global_accepted_rate': global_accepted_rate,
            'global_active_rate': global_active_rate,
            'global_paid_rate': global_paid_rate,
            'global_next_actions': global_next_actions,
            'latest_pending_tutors': latest_pending_tutors,
            'latest_disputes': latest_disputes,
            'latest_withdrawals': latest_withdrawals,
            'global_verification_sla_risk_ids': global_verification_sla_risk_ids,
            'global_dispute_sla_risk_ids': global_dispute_sla_risk_ids,
            'global_withdrawal_sla_risk_ids': global_withdrawal_sla_risk_ids,
            'global_sla_risk_count': (
                len(global_verification_sla_risk_ids)
                + len(global_dispute_sla_risk_ids)
                + len(global_withdrawal_sla_risk_ids)
            ),
            'recent_failed_attempts': recent_failed_attempts,
            'activity_timeline': activity_timeline,
            'template_name': 'dashboard/role_global_admin.jinja',
        }

    return {'template_name': 'dashboard/index.jinja'}


def _staff_only(request):
    return request.user.is_staff or request.user.is_superuser


def _blog_topic_gate_applies(request):
    """Student/VIP authors must match blog niche phrases; staff and city/global admins skip."""
    if _staff_only(request):
        return False
    role = getattr(request.user, "role", None)
    if role in (User.Role.GLOBAL_ADMIN, User.Role.CITY_ADMIN):
        return False
    return True


def _vip_coordinator(request):
    return getattr(request.user, "role", None) == User.Role.VIP_USER


def _student_user(request):
    return getattr(request.user, "role", None) == User.Role.STUDENT


def _can_create_blog_post(request):
    return _staff_only(request) or _vip_coordinator(request) or _student_user(request)


def _dashboard_blog_redirect_after_save(request, post, *, niche_gate_active: bool):
    """Topic gate leaves pending drafts (`published_at` empty); privileged roles publish freely."""
    if post.published_at:
        messages.success(request, f"Published: {post.title}")
        return redirect("blog:detail", slug=post.slug)

    messages.warning(request, NICHE_REQUIREMENT_USER_MESSAGE)
    if niche_gate_active:
        edit_path = reverse("dashboard:blog_post_edit", kwargs={"slug": post.slug})
        Notification.objects.create(
            user=request.user,
            message="Blog saved pending publish — add an approved topic phrase (home tutors, exams, courses, SEO/ads, etc.).",
            link=edit_path[:200],
        )
    return redirect("dashboard:blog_post_edit", slug=post.slug)


def _staff_or_vip_coordinator(request):
    return _staff_only(request) or _vip_coordinator(request)


@login_required
def vip_smart_dashboard(request):
    """Coordinator cockpit: metrics + deep links (VIP_USER role only)."""
    if not _vip_coordinator(request):
        messages.error(request, "VIP coordinator access only.")
        return redirect("dashboard:index")

    from hometutor.models import TutorProfile

    last_7 = timezone.now() - timedelta(days=7)
    recent_attempts = (
        UserAttempt.objects.select_related("user", "skill")
        .order_by("-attempt_date")[:14]
    )
    ctx = {
        "seo_title": "VIP Smart Dashboard — RankJee",
        "seo_description": "Coordinator overview for students, tutors, exams, and study content.",
        "total_users": User.objects.count(),
        "count_students": User.objects.filter(role=User.Role.STUDENT).count(),
        "count_parents": User.objects.filter(role=User.Role.PARENT).count(),
        "count_tutors_role": User.objects.filter(role=User.Role.TUTOR).count(),
        "count_tutor_profiles": TutorProfile.objects.count(),
        "attempts_7d": UserAttempt.objects.filter(attempt_date__gte=last_7).count(),
        "blog_posts_live": BlogPost.objects.filter(
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        ).count(),
        "referrals_linked": User.objects.exclude(referred_by__isnull=True).count(),
        "recent_users": User.objects.order_by("-date_joined")[:14],
        "recent_attempts": recent_attempts,
    }
    return render(request, "dashboard/vip_smart.jinja", ctx)


@login_required
def vip_create_user(request):
    if not _vip_coordinator(request):
        messages.error(request, "VIP coordinator access only.")
        return redirect("dashboard:index")

    from users.models import CustomUser as CU

    if request.method == "POST":
        form = VipManualUserForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"].strip()
            email = (form.cleaned_data.get("email") or "").strip().lower()
            pwd = form.cleaned_data["password1"]
            role = form.cleaned_data["role"]
            attach = form.cleaned_data.get("attach_my_referral")
            new_user = User.objects.create_user(
                username=username,
                email=email or "",
                password=pwd,
            )
            new_user.role = role
            if attach:
                new_user.referred_by = request.user
            new_user.save()
            label = "student" if role == CU.Role.STUDENT else "tutor"
            messages.success(
                request,
                f"Created {label} @{new_user.username}. "
                + (
                    "Ask them to complete tutor listing at Home tutor profile."
                    if role == CU.Role.TUTOR
                    else "They can log in with the password you set."
                ),
            )
            return redirect("dashboard:vip_create_user")
    else:
        form = VipManualUserForm()

    return render(
        request,
        "dashboard/vip_create_user.jinja",
        {"form": form, "seo_title": "Add student or tutor — VIP"},
    )


@login_required
def blog_post_create(request):
    if not _can_create_blog_post(request):
        messages.error(request, "Only VIP, staff, or student users can publish posts.")
        return redirect("dashboard:index")

    if request.method == "POST":
        form = VipBlogPostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            topic_gate = _blog_topic_gate_applies(request)
            # Author defaulting:
            # - For staff/superuser publishing ops, default author to user id=1 if it exists.
            # - Otherwise use the logged-in user.
            if request.user.is_staff or request.user.is_superuser:
                default_author = User.objects.filter(pk=1).first()
                post.author = default_author or request.user
            else:
                post.author = request.user
            post.save(apply_blog_niche_gate=topic_gate)
            return _dashboard_blog_redirect_after_save(request, post, niche_gate_active=topic_gate)
    else:
        form = VipBlogPostForm()

    return render(
        request,
        "dashboard/vip_blog_post.jinja",
        {
            "form": form,
            "seo_title": "New blog post",
            "page_title": "Publish blog post",
            "page_hint": (
                "Posts go live only when content clearly matches RankJee topics (home tutors/tutoring, online exams or mock tests, "
                "courses, digital marketing, SEO/local SEO, Meta/Google ads, email marketing, or closely related wording). "
                "Otherwise your draft is saved pending — edit and add a phrase, or ask staff to publish from Django admin. "
                "Leave slug blank to auto-generate."
            ),
            "submit_label": "Publish",
        },
    )


@login_required
def blog_post_edit(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)
    if not (_staff_only(request) or (post.author_id and post.author_id == request.user.id)):
        raise PermissionDenied

    if request.method == "POST":
        form = VipBlogPostForm(request.POST, instance=post)
        if form.is_valid():
            obj = form.save(commit=False)
            topic_gate = _blog_topic_gate_applies(request)
            # Preserve authorship; only owner/staff can reach here anyway.
            if not obj.author_id:
                obj.author = request.user
            obj.save(apply_blog_niche_gate=topic_gate)
            return _dashboard_blog_redirect_after_save(request, obj, niche_gate_active=topic_gate)
    else:
        form = VipBlogPostForm(instance=post)

    return render(
        request,
        "dashboard/vip_blog_post.jinja",
        {
            "form": form,
            "seo_title": f"Edit blog post — {post.title}",
            "page_title": "Edit blog post",
            "page_hint": (
                "Only you (the author) or staff can edit this post. "
                "If the post is pending, add an approved topic phrase (home tutors, exams, courses, SEO/ads, …) anywhere in title, excerpt, body, or SEO fields to publish."
            ),
            "submit_label": "Save changes",
        },
    )


@login_required
def backup_center(request):
    if not _staff_only(request):
        messages.error(request, "Only staff users can access backups.")
        return redirect("dashboard:index")

    backups = BackupArtifact.objects.select_related("created_by").order_by("-created_at")[:100]
    return render(
        request,
        "dashboard/backups.jinja",
        {
            "backups": backups,
            "seo_title": "Backups — Admin",
            "backup_keep_full": getattr(settings, "BACKUP_KEEP_FULL_COUNT", 14),
            "backup_keep_db": getattr(settings, "BACKUP_KEEP_DB_COUNT", 30),
        },
    )


@login_required
def backup_create_now(request):
    if request.method != "POST":
        return redirect("dashboard:backup_center")
    if not _staff_only(request):
        messages.error(request, "Only staff users can create backups.")
        return redirect("dashboard:index")

    backups = create_backups(include_full=True, include_db=True, created_by=request.user)
    notify_superusers_for_backups(backups)
    messages.success(request, f"Backup completed: {len(backups)} artifact(s) created.")
    return redirect("dashboard:backup_center")


@login_required
def backup_download(request, backup_id):
    if not _staff_only(request):
        messages.error(request, "Only staff users can download backups.")
        return redirect("dashboard:index")

    item = get_object_or_404(BackupArtifact, pk=backup_id)
    path = item.file_path
    if not path or not os.path.exists(path):
        raise Http404("Backup file not found.")

    return FileResponse(
        open(path, "rb"),
        as_attachment=True,
        filename=item.file_name,
        content_type="application/octet-stream",
    )


@login_required
def backup_delete(request, backup_id):
    if request.method != "POST":
        return redirect("dashboard:backup_center")
    if not _staff_only(request):
        messages.error(request, "Only staff users can delete backups.")
        return redirect("dashboard:index")

    item = get_object_or_404(BackupArtifact, pk=backup_id)
    name = item.file_name
    delete_backup_artifact(item)
    messages.success(request, f"Deleted backup: {name}")
    return redirect("dashboard:backup_center")


def _superuser_only(request):
    return request.user.is_superuser


def _study_urls_for_dashboard_role(role):
    from tutor_study.views import STUDY_URLS_DASHBOARD, STUDY_URLS_STANDALONE

    if role in (User.Role.STUDENT, User.Role.PARENT, User.Role.VIP_USER):
        return STUDY_URLS_DASHBOARD
    return STUDY_URLS_STANDALONE


@login_required
def dashboard_study(request):
    """Student/parent study hub inside `/admin/study/` (dashboard chrome)."""
    from tutor_study.views import STUDY_URLS_DASHBOARD, student_hub as ts_student_hub

    role = getattr(request.user, 'role', None)
    if role == User.Role.TUTOR:
        return redirect('study:tutor_dashboard')
    if role not in (User.Role.STUDENT, User.Role.PARENT, User.Role.VIP_USER):
        return redirect('study:student_hub')
    return ts_student_hub(request, study_urls=STUDY_URLS_DASHBOARD)


@login_required
def dashboard_study_topic_general(request):
    from tutor_study.views import STUDY_URLS_DASHBOARD, student_topic_workspace_general as ts_topic_general

    role = getattr(request.user, 'role', None)
    if role == User.Role.TUTOR:
        return redirect('study:tutor_dashboard')
    if role not in (User.Role.STUDENT, User.Role.PARENT, User.Role.VIP_USER):
        return redirect('study:student_topic_general')
    return ts_topic_general(request, study_urls=STUDY_URLS_DASHBOARD)


@login_required
def dashboard_study_topic(request, topic_pk):
    from tutor_study.views import STUDY_URLS_DASHBOARD, student_topic_workspace as ts_topic

    role = getattr(request.user, 'role', None)
    if role == User.Role.TUTOR:
        return redirect('study:tutor_dashboard')
    if role not in (User.Role.STUDENT, User.Role.PARENT, User.Role.VIP_USER):
        return redirect('study:student_topic', topic_pk=topic_pk)
    return ts_topic(request, topic_pk, study_urls=STUDY_URLS_DASHBOARD)


@login_required
def dashboard_study_material(request, pk):
    from tutor_study.views import student_material_detail as ts_student_material_detail

    role = getattr(request.user, 'role', None)
    if role == User.Role.TUTOR:
        return redirect('study:tutor_dashboard')
    return ts_student_material_detail(request, pk, study_urls=_study_urls_for_dashboard_role(role))


@login_required
def dashboard_study_assignment(request, pk):
    from tutor_study.views import student_assignment_detail as ts_student_assignment_detail

    role = getattr(request.user, 'role', None)
    if role == User.Role.TUTOR:
        return redirect('study:tutor_dashboard')
    return ts_student_assignment_detail(request, pk, study_urls=_study_urls_for_dashboard_role(role))


@login_required
def update_tutor_request_status(request, request_id):
    if request.method != "POST" or not _staff_only(request):
        return redirect("dashboard:index")

    item = TutorLeadRequest.objects.filter(pk=request_id).first()
    if not item:
        messages.error(request, "Tutor request not found.")
        return redirect("dashboard:index")

    new_status = (request.POST.get("status") or "").strip().upper()
    allowed = {choice[0] for choice in TutorLeadRequest.Status.choices}
    if new_status not in allowed:
        messages.error(request, "Invalid tutor request status.")
        return redirect("dashboard:index")

    item.status = new_status
    item.save(update_fields=["status"])
    messages.success(request, f"Updated tutor request status: {item.full_name} -> {item.get_status_display()}")
    return redirect("dashboard:index")


def _seed_default_seo_targets():
    if SeoTarget.objects.exists():
        return
    defaults = [
        ("Phase 1: Technical Foundation", "Verify domain in Google Search Console", "HIGH", 10),
        ("Phase 1: Technical Foundation", "Submit /sitemap.xml and validate robots.txt", "HIGH", 20),
        ("Phase 1: Technical Foundation", "Add unique dynamic title + meta description", "HIGH", 30),
        ("Phase 1: Technical Foundation", "Ship canonical tags on all indexable pages", "HIGH", 40),
        ("Phase 2: Keyword Mapping", "Finalize keyword-to-URL map for tutor/mock/course", "HIGH", 50),
        ("Phase 2: Keyword Mapping", "Pick top 10 cities + 10 exams + 10 monetizable courses", "HIGH", 60),
        ("Phase 3: Programmatic SEO", "Launch first 50 city tutor pages", "MEDIUM", 70),
        ("Phase 3: Programmatic SEO", "Launch first 20 exam mock pages", "MEDIUM", 80),
        ("Phase 3: Programmatic SEO", "Launch first 20 course-city pages", "MEDIUM", 90),
        ("Phase 4: Content Engine", "Publish 3 long-tail SEO blogs per week", "MEDIUM", 100),
        ("Phase 5: Authority", "Build internal hub linking for city/exam/course pages", "MEDIUM", 110),
        ("Phase 6: Revenue Layer", "Add strong CTA + lead forms on all money pages", "HIGH", 120),
        ("Phase 7: Governance", "Run weekly SEO review and monthly SEO audit", "MEDIUM", 130),
    ]
    SeoTarget.objects.bulk_create(
        [
            SeoTarget(phase=phase, title=title, priority=priority, sort_order=order)
            for phase, title, priority, order in defaults
        ]
    )


@login_required
def seo_smart_view(request):
    if not _superuser_only(request):
        messages.error(request, "Only superusers can access SEO Smart View.")
        return redirect("dashboard:index")
    if SeoTarget is None:
        messages.error(request, "SEO module unavailable on this deploy. Please sync dashboard models.")
        return redirect("dashboard:index")

    _seed_default_seo_targets()

    if request.method == "POST":
        target_id = request.POST.get("target_id")
        new_status = request.POST.get("status")
        allowed_statuses = {choice[0] for choice in SeoTarget.Status.choices}
        if target_id and new_status in allowed_statuses:
            target = SeoTarget.objects.filter(pk=target_id).first()
            if target:
                target.status = new_status
                target.save(update_fields=["status", "updated_at"])
                messages.success(request, f"Updated target: {target.title}")
        return redirect("dashboard:seo_smart_view")

    status_filter = (request.GET.get("status") or "").strip()
    phase_filter = (request.GET.get("phase") or "").strip()
    q = (request.GET.get("q") or "").strip()

    targets = SeoTarget.objects.all()
    if status_filter:
        targets = targets.filter(status=status_filter)
    if phase_filter:
        targets = targets.filter(phase=phase_filter)
    if q:
        targets = targets.filter(Q(title__icontains=q) | Q(notes__icontains=q))

    total_targets = targets.count()
    done_count = targets.filter(status=SeoTarget.Status.DONE).count()
    in_progress_count = targets.filter(status=SeoTarget.Status.IN_PROGRESS).count()
    blocked_count = targets.filter(status=SeoTarget.Status.BLOCKED).count()
    todo_count = targets.filter(status=SeoTarget.Status.TODO).count()
    progress_percent = int((done_count / total_targets) * 100) if total_targets else 0
    phases = SeoTarget.objects.values_list("phase", flat=True).distinct().order_by("phase")

    return render(
        request,
        "dashboard/seo_smart_view.jinja",
        {
            "targets": targets,
            "total_targets": total_targets,
            "done_count": done_count,
            "in_progress_count": in_progress_count,
            "blocked_count": blocked_count,
            "todo_count": todo_count,
            "progress_percent": progress_percent,
            "status_filter": status_filter,
            "phase_filter": phase_filter,
            "search_query": q,
            "phases": phases,
            "status_choices": SeoTarget.Status.choices,
        },
    )


@login_required
def students_score_table(request):
    if not _staff_or_vip_coordinator(request):
        return redirect("dashboard:index")

    q = (request.GET.get("q") or "").strip()
    user_qs = User.objects.all()
    if q:
        user_qs = user_qs.filter(Q(username__icontains=q) | Q(email__icontains=q))

    qs = (
        user_qs.annotate(
            attempts_count=Count("userattempt", distinct=True),
            avg_score=Avg("userattempt__score"),
            best_score=Max("userattempt__score"),
            pass_count=Count("userattempt", filter=Q(userattempt__passed=True), distinct=True),
            last_attempt_at=Max("userattempt__attempt_date"),
        )
        .order_by("-last_attempt_at", "-attempts_count", "-xp_points", "-date_joined")
    )
    paginator = Paginator(qs, 30)
    students_page = paginator.get_page(request.GET.get("page", 1))

    # Build weak-topic hint from latest attempt for each visible student.
    page_user_ids = [u.id for u in students_page.object_list]
    latest_attempts = (
        UserAttempt.objects.filter(user_id__in=page_user_ids)
        .select_related("skill")
        .order_by("user_id", "-attempt_date")
    )
    latest_by_user = {}
    for item in latest_attempts:
        if item.user_id not in latest_by_user:
            latest_by_user[item.user_id] = item

    rows = []
    for u in students_page.object_list:
        attempts = int(getattr(u, "attempts_count", 0) or 0)
        pass_count = int(getattr(u, "pass_count", 0) or 0)
        pass_rate = round((pass_count / attempts) * 100, 1) if attempts else 0
        avg_score = float(getattr(u, "avg_score", 0) or 0)
        best_score = int(getattr(u, "best_score", 0) or 0)
        latest_attempt = latest_by_user.get(u.id)
        weak_preview = ""
        latest_skill_name = ""
        latest_score = None
        if latest_attempt:
            latest_skill_name = latest_attempt.skill.name if latest_attempt.skill else ""
            latest_score = latest_attempt.score
            weak_preview = ", ".join((latest_attempt.weak_concepts or [])[:3])
        rows.append(
            {
                "student": u,
                "attempts": attempts,
                "pass_count": pass_count,
                "pass_rate": pass_rate,
                "avg_score": round(avg_score, 1),
                "best_score": best_score,
                "last_attempt_at": getattr(u, "last_attempt_at", None),
                "latest_skill_name": latest_skill_name,
                "latest_score": latest_score,
                "weak_preview": weak_preview,
                "latest_attempt_id": latest_attempt.id if latest_attempt else None,
            }
        )

    return render(
        request,
        "dashboard/students_score_table.jinja",
        {
            "rows": rows,
            "students_page": students_page,
            "search_query": q,
        },
    )


@login_required
def users_referral_table(request):
    if not (_superuser_only(request) or _vip_coordinator(request)):
        messages.error(request, "Only superadmin or VIP coordinators can access the referral table.")
        return redirect("dashboard:index")

    q = (request.GET.get("q") or "").strip()
    user_qs = User.objects.select_related("referred_by")
    if q:
        user_qs = user_qs.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(referral_code__icontains=q)
            | Q(referred_by__username__icontains=q)
            | Q(referred_by__email__icontains=q)
        )

    referral_qs = user_qs.annotate(referrals_count=Count("referrals", distinct=True))
    if AccessLog is not None:
        latest_ip_subquery = (
            AccessLog.objects.filter(username=OuterRef("username"))
            .order_by("-attempt_time")
            .values("ip_address")[:1]
        )
        referral_qs = referral_qs.annotate(last_login_ip=Subquery(latest_ip_subquery))
    referral_qs = referral_qs.order_by("-date_joined")

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="users_referrals.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Username",
                "Email",
                "Role",
                "Referral Code",
                "Referred By Username",
                "Referred By Email",
                "Total Referrals",
                "Last Login IP",
                "Location",
                "Joined At",
            ]
        )
        for u in referral_qs:
            ip_location = _location_from_ip(getattr(u, "last_login_ip", "") or "")
            writer.writerow(
                [
                    u.username,
                    u.email,
                    u.get_role_display(),
                    u.referral_code,
                    u.referred_by.username if u.referred_by else "",
                    u.referred_by.email if u.referred_by else "",
                    u.referrals_count,
                    getattr(u, "last_login_ip", "") or "",
                    ip_location or (u.get_state_display() if u.state else "Unknown"),
                    timezone.localtime(u.date_joined).strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )
        return response

    paginator = Paginator(referral_qs, 30)
    users_page = paginator.get_page(request.GET.get("page", 1))
    for user in users_page.object_list:
        user.ip_location = _location_from_ip(getattr(user, "last_login_ip", "") or "")

    return render(
        request,
        "dashboard/users_referral_table.jinja",
        {
            "users_page": users_page,
            "search_query": q,
        },
    )


@login_required
def student_attempt_review(request, attempt_id):
    if not _staff_only(request):
        return redirect("dashboard:index")

    attempt = get_object_or_404(
        UserAttempt.objects.select_related("skill", "attempted_video", "user"),
        pk=attempt_id,
    )
    if not attempt.skill:
        messages.warning(request, "Attempt details unavailable for this test.")
        return redirect("dashboard:students_score_table")

    questions_qs = Question.objects.filter(skill=attempt.skill)
    if attempt.attempted_video_id:
        questions_qs = questions_qs.filter(
            source_video_id=attempt.attempted_video_id,
            is_video_import=True,
        )

    weak_tags = [str(tag).strip() for tag in (attempt.weak_concepts or []) if str(tag).strip()]
    if weak_tags:
        concept_q = Q()
        for tag in weak_tags:
            concept_q |= Q(concept_tag__iexact=tag) | Q(concept_tag__icontains=tag)
        questions_qs = questions_qs.filter(concept_q)

    question_rows = []
    for q in questions_qs.order_by("id")[:40]:
        if q.correct_option == "A":
            correct_text = q.option_a
        elif q.correct_option == "B":
            correct_text = q.option_b
        elif q.correct_option == "C":
            correct_text = q.option_c
        else:
            correct_text = q.option_d
        question_rows.append(
            {
                "question": q,
                "correct_text": correct_text,
            }
        )

    return render(
        request,
        "dashboard/attempt_review.jinja",
        {
            "attempt": attempt,
            "question_rows": question_rows,
            "is_staff_review": True,
        },
    )


@login_required
def daily_class_log(request):
    role = getattr(request.user, "role", "STUDENT")
    if request.user.is_staff or request.user.is_superuser:
        return redirect("dashboard:admin_student_daily_logs")
    if role != "STUDENT":
        messages.info(request, "Daily class log is available for student accounts.")
        return redirect("dashboard:index")

    logs_qs = StudentDailyClassLog.objects.filter(user=request.user).order_by("-log_date", "-id")
    view_mode = request.GET.get("view", "list").strip().lower()
    if view_mode not in {"list", "calendar"}:
        view_mode = "list"
    month_value = request.GET.get("month", "").strip()
    paginator = Paginator(logs_qs, 20)
    logs_page = paginator.get_page(request.GET.get("page", 1))

    if request.method == "POST":
        form = StudentDailyClassLogForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            StudentDailyClassLog.objects.update_or_create(
                user=request.user,
                log_date=cd["log_date"],
                defaults={
                    "topic": cd["topic"],
                    "details": cd["details"],
                    "attendance": cd["attendance"],
                },
            )
            messages.success(request, "Class log saved for this date.")
            return redirect("dashboard:daily_class_log")
    else:
        form = StudentDailyClassLogForm(initial={"log_date": timezone.localdate()})

    return render(
        request,
        "dashboard/daily_class_log.jinja",
        {
            "form": form,
            "logs_page": logs_page,
            "view_mode": view_mode,
            **_calendar_view_context(logs_qs, month_value),
        },
    )


@login_required
def admin_student_daily_logs(request):
    if not _staff_only(request):
        messages.error(request, "You do not have access to this page.")
        return redirect("dashboard:index")

    role = getattr(request.user, "role", "STUDENT")
    is_city_admin = role == "CITY_ADMIN"

    logs_qs = StudentDailyClassLog.objects.select_related("user").order_by("-log_date", "-id")
    if is_city_admin and getattr(request.user, "state", None):
        logs_qs = logs_qs.filter(user__state=request.user.state)

    student_id_raw = request.GET.get("student_id", "").strip()
    if student_id_raw.isdigit():
        logs_qs = logs_qs.filter(user_id=int(student_id_raw))

    search_query = request.GET.get("q", "").strip()
    if search_query:
        logs_qs = logs_qs.filter(
            Q(user__username__icontains=search_query)
            | Q(user__email__icontains=search_query)
            | Q(topic__icontains=search_query)
        )

    paginator = Paginator(logs_qs, 25)
    logs_page = paginator.get_page(request.GET.get("page", 1))
    view_mode = request.GET.get("view", "list").strip().lower()
    if view_mode not in {"list", "calendar"}:
        view_mode = "list"
    month_value = request.GET.get("month", "").strip()

    student_options = User.objects.filter(role=User.Role.STUDENT).order_by("username")
    if is_city_admin and getattr(request.user, "state", None):
        student_options = student_options.filter(state=request.user.state)
    student_options = student_options[:500]

    student_filter_id = int(student_id_raw) if student_id_raw.isdigit() else None

    filter_params = {}
    if search_query:
        filter_params["q"] = search_query
    if student_filter_id:
        filter_params["student_id"] = student_filter_id
    if view_mode != "list":
        filter_params["view"] = view_mode
    if month_value:
        filter_params["month"] = month_value
    filter_querystring = f"&{urlencode(filter_params)}" if filter_params else ""

    return render(
        request,
        "dashboard/admin_student_daily_logs.jinja",
        {
            "logs_page": logs_page,
            "search_query": search_query,
            "student_filter_id": student_filter_id,
            "student_options": student_options,
            "filter_querystring": filter_querystring,
            "view_mode": view_mode,
            **_calendar_view_context(logs_qs, month_value),
        },
    )


@login_required
def index(request):
    if not getattr(request.user, 'onboarding_completed', True):
        return redirect('users:onboarding_role')
    role = getattr(request.user, 'role', 'STUDENT')
    if role == User.Role.VIP_USER:
        return vip_smart_dashboard(request)
    now = timezone.now()
    role_intro_map = {
        'TUTOR': "Manage your tutor listing, handle demo requests, and grow student enrollments.",
        'PARENT': "Find trusted tutors, track demos, and support your child with guided prep.",
        'STUDENT': "Build mastery with tests and videos, and connect with the right tutor when needed.",
        'CITY_ADMIN': "Track city-level tutor quality, disputes, and demand trends for operational excellence.",
        'GLOBAL_ADMIN': "Oversee platform-wide growth, trust, and monetization with cross-region visibility.",
    }
    role_marketplace_label_map = {
        'TUTOR': "Review incoming demos and keep your tutor profile optimized for conversions.",
        'PARENT': "Browse tutors and request demos to choose the best tutor for your child.",
        'STUDENT': "Explore tutors and request a demo to accelerate your preparation.",
        'CITY_ADMIN': "Review city tutor supply and conversion funnels from discovery to engagement.",
        'GLOBAL_ADMIN': "Monitor total supply-demand health and marketplace quality across all regions.",
    }

    if request.user.is_superuser or request.user.is_staff:
        is_city_admin = role == 'CITY_ADMIN'
        admin_scope_label = 'Global'
        scoped_users = User.objects.all()
        if is_city_admin and getattr(request.user, 'state', None):
            scoped_users = User.objects.filter(state=request.user.state)
            admin_scope_label = f"City/State: {request.user.get_state_display()}"
        elif is_city_admin:
            admin_scope_label = 'City/State: not set'

        # App-wide Admin Dashboard Stats
        total_users_count = scoped_users.count()
        total_questions = Question.objects.count()
        total_videos = ConceptVideo.objects.count()
        total_skills = Skill.objects.filter(is_active=True).count()
        
        # User Search & Pagination
        search_query = request.GET.get('q', '').strip()
        users_queryset = scoped_users.order_by('-date_joined')
        if search_query:
            users_queryset = users_queryset.filter(
                Q(username__icontains=search_query) | Q(email__icontains=search_query)
            )
        
        paginator = Paginator(users_queryset, 10) # 10 students per page
        page_number = request.GET.get('page', 1)
        students_page = paginator.get_page(page_number)
        
        # Performance Analytics
        # Get pass rates per skill (top 5 difficult vs top 5 easiest)
        skill_stats = Skill.objects.filter(is_active=True).annotate(
            total_attempts=Count('userattempt'),
            pass_count=Count('userattempt', filter=Q(userattempt__passed=True)),
            avg_score=Avg('userattempt__score')
        ).filter(total_attempts__gt=0)
        
        difficult_skills = skill_stats.order_by('avg_score')[:5]
        easiest_skills = skill_stats.order_by('-avg_score')[:5]
        
        # Platform Activity (Last 7 days)
        last_7_days = timezone.now() - timedelta(days=7)
        recent_attempts_count = UserAttempt.objects.filter(attempt_date__gte=last_7_days).count()
        recent_submissions_count = UserTaskSubmission.objects.filter(submitted_at__gte=last_7_days).count()
        recent_registrations_count = scoped_users.filter(date_joined__gte=last_7_days).count()
        
        # New analytics
        pending_submissions = UserTaskSubmission.objects.filter(status='PENDING').order_by('-submitted_at')
        pending_count = pending_submissions.count()
        
        total_payouts = UserTaskSubmission.objects.filter(status='APPROVED').aggregate(
            total=Sum('task__reward_amount')
        )['total'] or 0
        
        # Calculate total XP across platform to show engagement
        total_xp_platform = scoped_users.aggregate(Sum('xp_points'))['xp_points__sum'] or 0

        pending_withdrawals = WithdrawalRequest.objects.filter(status='PENDING').select_related(
            'user'
        ).order_by('-requested_at')[:10]
        pending_withdrawals_count = WithdrawalRequest.objects.filter(status='PENDING').count()
        latest_tutor_requests = TutorLeadRequest.objects.select_related('requester').order_by('-created_at')[:12]
        tutor_requests_count = TutorLeadRequest.objects.count()
        recent_failed_attempts = (
            UserAttempt.objects.filter(passed=False)
            .select_related("user", "skill")
            .order_by("-attempt_date")[:12]
        )

        recent_daily_class_logs_qs = StudentDailyClassLog.objects.select_related("user").order_by(
            "-log_date", "-id"
        )
        if is_city_admin and getattr(request.user, "state", None):
            recent_daily_class_logs_qs = recent_daily_class_logs_qs.filter(user__state=request.user.state)
        recent_daily_class_logs = list(recent_daily_class_logs_qs[:12])
        latest_backups = list(
            BackupArtifact.objects.select_related("created_by").order_by("-created_at")[:5]
        )

        return render(request, 'dashboard/admin_dashboard.jinja', {
            'admin_role': role,
            'admin_scope_label': admin_scope_label,
            'total_users': total_users_count,
            'total_questions': total_questions,
            'total_videos': total_videos,
            'total_skills': total_skills,
            'students_page': students_page,
            'search_query': search_query,
            'difficult_skills': difficult_skills,
            'easiest_skills': easiest_skills,
            'recent_attempts': recent_attempts_count,
            'recent_submissions': recent_submissions_count,
            'recent_registrations': recent_registrations_count,
            'total_xp_platform': total_xp_platform,
            'pending_submissions': pending_submissions[:5],
            'pending_count': pending_count,
            'total_payouts': total_payouts,
            'pending_withdrawals': pending_withdrawals,
            'pending_withdrawals_count': pending_withdrawals_count,
            'latest_tutor_requests': latest_tutor_requests,
            'tutor_requests_count': tutor_requests_count,
            'recent_failed_attempts': recent_failed_attempts,
            'recent_daily_class_logs': recent_daily_class_logs,
            'latest_backups': latest_backups,
        })

    # Role-dedicated dashboards for non-staff roles.
    if role in ['TUTOR', 'PARENT', 'CITY_ADMIN', 'GLOBAL_ADMIN']:
        try:
            role_ctx = _role_dashboard_context(request)
            return render(
                request,
                role_ctx['template_name'],
                {
                    'user': request.user,
                    'user_role': role,
                    **role_ctx,
                },
            )
        except Exception as exc:
            logger.exception(
                "Role dashboard context failed (user_id=%s role=%s): %s",
                request.user.id,
                role,
                exc,
            )
            messages.warning(
                request,
                "Your role dashboard is loading fallback mode while we sync live data.",
            )

    # Student dashboard (learning + marketplace)
    user_exam_attempts = (
        UserAttempt.objects.filter(user=request.user)
        .select_related("skill", "attempted_video")
        .order_by("-attempt_date")
    )
    latest_attempt = user_exam_attempts.first()
    my_exam_performance = list(user_exam_attempts[:10])

    my_exam_performance_rows = [
        {
            "attempt": attempt,
            "video_id": attempt.attempted_video_id,
            "video_title": attempt.attempted_video.title if attempt.attempted_video else "",
        }
        for attempt in my_exam_performance
    ]

    attempts_count = UserAttempt.objects.filter(user=request.user).count()
    passed_count = UserAttempt.objects.filter(user=request.user, passed=True).count()
    total_attempts = UserAttempt.objects.filter(user=request.user).count()
    progress = int((passed_count / total_attempts) * 100) if total_attempts > 0 else 0

    from assessment.models import SkillPath
    all_paths = SkillPath.objects.filter(is_active=True).order_by('level_order')
    selected_path_id = request.GET.get('path')
    
    if selected_path_id:
        selected_path = all_paths.filter(id=selected_path_id).first()
    else:
        selected_path = all_paths.first()

    total_earned = request.user.wallet_balance
    
    # Filter skills by the selected path
    skills = Skill.objects.filter(is_active=True, path=selected_path).order_by('order')
    passed_set_ids = UserSetAttempt.objects.filter(user=request.user, passed=True).values_list('question_set_id', flat=True).distinct()
    
    learning_path = []
    prev_passed = True # First skill in the path is always unlocked
    
    for s in skills:
        sets = s.sets.all().order_by('order')
        total_sets = sets.count()
        passed_sets_count = sets.filter(id__in=passed_set_ids).count()
        
        is_fully_passed = (passed_sets_count >= total_sets) if total_sets > 0 else False
        
        status = 'LOCKED'
        if prev_passed:
            status = 'PASSED' if is_fully_passed else 'UNLOCKED'
            
        learning_path.append({
            'skill': s,
            'status': status,
            'total_sets': total_sets,
            'passed_sets': passed_sets_count,
            'next_set': sets.exclude(id__in=passed_set_ids).first()
        })
        
        # Track for next skill unlock logic within this path
        prev_passed = is_fully_passed

    # Top 5 users for mini-leaderboard widget
    top_users = User.objects.order_by('-xp_points')[:5]

    passed_count = UserAttempt.objects.filter(user=request.user, passed=True).count()
    total_skills = Skill.objects.filter(is_active=True).count()
    progress = int((passed_count / total_skills) * 100) if total_skills > 0 else 0

    # QW-04: simple next-badge hint (streak-based + first test)
    if attempts_count < 1:
        next_badge_hint = "Take your first test to unlock the FIRST_TEST badge."
    elif request.user.streak_days < 7:
        next_badge_hint = f"Keep going: {7 - request.user.streak_days} more day(s) to unlock STREAK_7."
    elif request.user.streak_days < 30:
        next_badge_hint = f"Momentum: {30 - request.user.streak_days} more day(s) to unlock STREAK_30."
    else:
        next_badge_hint = "You’re on fire — keep collecting badges by passing new skills."

    latest_attempt = UserAttempt.objects.filter(user=request.user).order_by('-attempt_date').first()
    weak_areas = latest_attempt.weak_concepts if latest_attempt else []
    user_badges = request.user.badges.select_related('badge').order_by('-awarded_at')
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    recent_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:6]

    user_certificates = request.user.certificates.select_related('skill').order_by('-issued_at')

    xp_rank_india = User.objects.filter(xp_points__gt=request.user.xp_points).count() + 1

    from hometutor.models import DemoRequest, TutorProfile, TutorEngagement
    from hometutor.services import attach_demo_status_to_cards, public_tutor_queryset, tutor_to_card_dict
    from hometutor_payments.models import MarketplaceOrder
    from core.hometutor_data import PILOT_CITY

    hometutor_tutor_profile = TutorProfile.objects.filter(user=request.user).first()
    hometutor_pending_incoming = (
        DemoRequest.objects.filter(
            tutor=hometutor_tutor_profile,
            status=DemoRequest.Status.PENDING,
        ).count()
        if hometutor_tutor_profile
        else 0
    )
    hometutor_my_pending_sent = DemoRequest.objects.filter(
        requester=request.user,
        status=DemoRequest.Status.PENDING,
    ).count()
    parent_gate_param = request.GET.get('parent_gate')
    if parent_gate_param in {'0', '1'}:
        request.session['student_parent_gate_enabled'] = parent_gate_param == '1'
    parent_gate_enabled = bool(request.session.get('student_parent_gate_enabled', False))

    student_demo_qs = DemoRequest.objects.filter(requester=request.user).select_related('tutor').order_by('-created_at')
    student_recent_demos = student_demo_qs[:6]
    student_demo_pending = student_demo_qs.filter(status=DemoRequest.Status.PENDING).count()
    student_demo_accepted = student_demo_qs.filter(status=DemoRequest.Status.ACCEPTED).count()
    student_demo_declined = student_demo_qs.filter(status=DemoRequest.Status.DECLINED).count()

    student_engagements = TutorEngagement.objects.filter(student=request.user).select_related('tutor_profile').order_by('-updated_at')
    student_active_engagements = student_engagements.filter(status=TutorEngagement.Status.ACTIVE).count()
    student_recent_engagements = student_engagements[:5]
    student_paid_engagement_ids = set(
        MarketplaceOrder.objects.filter(
            payer=request.user,
            status=MarketplaceOrder.Status.SUCCESS,
            engagement__student=request.user,
        ).values_list('engagement_id', flat=True)
    )
    student_paid_count = len(student_paid_engagement_ids)
    student_parent_approval_pending = student_demo_pending + max(0, student_active_engagements - student_paid_count)

    student_pending_demo_sla_risk_count = DemoRequest.objects.filter(
        requester=request.user,
        status=DemoRequest.Status.PENDING,
        created_at__lt=now - timedelta(hours=24),
    ).count()
    student_preview_mode = False
    if student_demo_qs.count() == 0 and student_engagements.count() == 0:
        preview_user = User.objects.filter(username='demo_student').first()
        if preview_user:
            student_preview_mode = True
            student_demo_qs = DemoRequest.objects.filter(requester=preview_user).select_related('tutor').order_by('-created_at')
            student_recent_demos = student_demo_qs[:6]
            student_demo_pending = student_demo_qs.filter(status=DemoRequest.Status.PENDING).count()
            student_demo_accepted = student_demo_qs.filter(status=DemoRequest.Status.ACCEPTED).count()
            student_demo_declined = student_demo_qs.filter(status=DemoRequest.Status.DECLINED).count()
            student_engagements = TutorEngagement.objects.filter(student=preview_user).select_related('tutor_profile').order_by('-updated_at')
            student_active_engagements = student_engagements.filter(status=TutorEngagement.Status.ACTIVE).count()
            student_recent_engagements = student_engagements[:5]
            student_paid_engagement_ids = set(
                MarketplaceOrder.objects.filter(
                    payer=preview_user,
                    status=MarketplaceOrder.Status.SUCCESS,
                    engagement__student=preview_user,
                ).values_list('engagement_id', flat=True)
            )
            student_paid_count = len(student_paid_engagement_ids)
            student_parent_approval_pending = student_demo_pending + max(0, student_active_engagements - student_paid_count)
            student_pending_demo_sla_risk_count = DemoRequest.objects.filter(
                requester=preview_user,
                status=DemoRequest.Status.PENDING,
                created_at__lt=now - timedelta(hours=24),
            ).count()
    quick_tutor_cards = [tutor_to_card_dict(t, PILOT_CITY) for t in public_tutor_queryset({'city': PILOT_CITY})[:6]]
    quick_tutor_cards = attach_demo_status_to_cards(quick_tutor_cards, request.user)
    weak_topic_tutor_cards = []
    weak_terms = []
    if isinstance(weak_areas, list):
        weak_terms = [str(x).strip() for x in weak_areas if str(x).strip()][:3]
    elif isinstance(weak_areas, str) and weak_areas.strip():
        weak_terms = [weak_areas.strip()]
    for term in weak_terms:
        qs = TutorProfile.objects.filter(
            verification_status=TutorProfile.VerificationStatus.APPROVED,
            subjects__icontains=term,
        ).order_by('-rating_display', 'display_name')[:2]
        for t in qs:
            weak_topic_tutor_cards.append(tutor_to_card_dict(t, PILOT_CITY))
    # Deduplicate by slug and keep first 4 recommendations.
    dedup = {}
    for c in weak_topic_tutor_cards:
        if c['slug'] not in dedup:
            dedup[c['slug']] = c
    weak_topic_tutor_cards = attach_demo_status_to_cards(list(dedup.values())[:4], request.user)

    student_activity = []
    for note in recent_notifications:
        student_activity.append(
            {
                'title': note.message,
                'meta': note.created_at,
            }
        )
    if latest_attempt:
        student_activity.append(
            {
                'title': f'Latest test score: {latest_attempt.score}% in {latest_attempt.skill.name}',
                'meta': latest_attempt.attempt_date,
            }
        )
    student_activity = sorted(student_activity, key=lambda x: x['meta'], reverse=True)[:8]

    role_stat_cards = [
        {'label': 'Total Credits', 'value': f'₹{int(request.user.wallet_balance)}'},
        {'label': 'Mastery', 'value': f'{progress}%'},
        {'label': 'XP Rank (India)', 'value': f'#{xp_rank_india}'},
    ]
    if role == 'TUTOR':
        role_stat_cards.append({'label': 'Incoming Demo Requests', 'value': str(hometutor_pending_incoming)})
    elif role == 'PARENT':
        role_stat_cards.append({'label': 'My Pending Tutor Requests', 'value': str(hometutor_my_pending_sent)})
    else:
        role_stat_cards.append({'label': 'Free Test Uses', 'value': str(request.user.trial_tests_left)})

    server_buy_success = role == 'STUDENT' and request.GET.get('server_paid') == '1'
    server_buy_success_message = (
        "Your server payment was recorded. We will contact you about provisioning for the domain you entered."
    )
    if server_buy_success:
        try:
            from server_buy.models import ServerBuyMessageConfig

            msg_cfg = ServerBuyMessageConfig.objects.first()
            if msg_cfg and msg_cfg.success_message:
                server_buy_success_message = msg_cfg.success_message
        except Exception:
            logger.exception("Failed to load server-buy success message config")

    return render(request, 'dashboard/index.jinja', {
        'user': request.user,
        'user_role': role,
        'role_intro': role_intro_map.get(role, role_intro_map['STUDENT']),
        'role_marketplace_label': role_marketplace_label_map.get(role, role_marketplace_label_map['STUDENT']),
        'progress': progress,
        'nav_progress_percent': progress,
        'xp_rank_india': xp_rank_india,
        'hometutor_tutor_profile': hometutor_tutor_profile,
        'hometutor_pending_incoming': hometutor_pending_incoming,
        'hometutor_my_pending_sent': hometutor_my_pending_sent,
        'student_recent_demos': student_recent_demos,
        'student_demo_pending': student_demo_pending,
        'student_demo_accepted': student_demo_accepted,
        'student_demo_declined': student_demo_declined,
        'student_active_engagements': student_active_engagements,
        'student_recent_engagements': student_recent_engagements,
        'student_paid_engagement_ids': student_paid_engagement_ids,
        'student_paid_count': student_paid_count,
        'parent_gate_enabled': parent_gate_enabled,
        'student_preview_mode': student_preview_mode,
        'student_parent_approval_pending': student_parent_approval_pending,
        'student_pending_demo_sla_risk_count': student_pending_demo_sla_risk_count,
        'hometutor_pilot_city': PILOT_CITY,
        'quick_tutor_cards': quick_tutor_cards,
        'weak_terms': weak_terms,
        'weak_topic_tutor_cards': weak_topic_tutor_cards,
        'student_activity': student_activity,
        'role_stat_cards': role_stat_cards,
        'total_earned': total_earned,
        'weak_areas': weak_areas,
        'latest_attempt': latest_attempt,
        'my_exam_performance_rows': my_exam_performance_rows,
        'streak_days': request.user.streak_days,
        'user_badges': user_badges,
        'user_certificates': user_certificates, # Added
        'unread_notifications': unread_notifications,
        'learning_path': learning_path,
        'all_paths': all_paths,
        'selected_path': selected_path,
        'top_users': top_users,
        'next_badge_hint': next_badge_hint,
        'server_buy_success': server_buy_success,
        'server_buy_success_message': server_buy_success_message,
    })


@login_required
def leaderboard(request):
    filter_state = request.GET.get('filter')
    state_key = request.user.state if (filter_state == 'state' and request.user.state) else ''
    cache_key = f'lb:v1:{filter_state or "all"}:{state_key}'
    ids = cache.get(cache_key)
    if ids is None:
        if filter_state == 'state' and request.user.state:
            qs = User.objects.filter(state=request.user.state).order_by('-xp_points')
            title_suffix = f"({request.user.get_state_display()})"
        else:
            qs = User.objects.order_by('-xp_points')
            title_suffix = "(All India)"
        ids = list(qs.values_list('id', flat=True)[:20])
        cache.set(cache_key, ids, 300)
    else:
        if filter_state == 'state' and request.user.state:
            title_suffix = f"({request.user.get_state_display()})"
        else:
            title_suffix = "(All India)"

    if not ids:
        users = []
    else:
        preserved = Case(
            *[When(pk=_id, then=pos) for pos, _id in enumerate(ids)],
            output_field=IntegerField(),
        )
        users = list(User.objects.filter(pk__in=ids).order_by(preserved))
    user_rank = None
    # We enumerate the entire queryset efficiently using iterator if large, 
    # but since it's a small app, this is fine for now as per bootstrap plan.
    # A true rank query would use `filter(xp_points__gt=request.user.xp_points).count() + 1`
    
    # Calculate exact rank efficiently
    if filter_state == 'state' and request.user.state:
        user_rank = User.objects.filter(state=request.user.state, xp_points__gt=request.user.xp_points).count() + 1
    else:
        user_rank = User.objects.filter(xp_points__gt=request.user.xp_points).count() + 1

    return render(request, 'dashboard/leaderboard.jinja', {
        'users': users,
        'user_rank': user_rank,
        'filter_state': filter_state,
        'title_suffix': title_suffix,
    })


@login_required
def notifications(request):
    notes = Notification.objects.filter(user=request.user)
    # Mark all as read when viewed
    notes.filter(is_read=False).update(is_read=True)
    return render(request, 'dashboard/notifications.jinja', {'notifications': notes})


@login_required
def attempt_review(request, attempt_id):
    attempt = get_object_or_404(
        UserAttempt.objects.select_related("skill", "attempted_video"),
        pk=attempt_id,
        user=request.user,
    )
    if not attempt.skill:
        messages.warning(request, "Attempt details unavailable for this test.")
        return redirect("dashboard:index")

    questions_qs = Question.objects.filter(skill=attempt.skill)
    if attempt.attempted_video_id:
        questions_qs = questions_qs.filter(
            source_video_id=attempt.attempted_video_id,
            is_video_import=True,
        )

    weak_tags = [str(tag).strip() for tag in (attempt.weak_concepts or []) if str(tag).strip()]
    if weak_tags:
        concept_q = Q()
        for tag in weak_tags:
            concept_q |= Q(concept_tag__iexact=tag) | Q(concept_tag__icontains=tag)
        questions_qs = questions_qs.filter(concept_q)

    question_rows = []
    for q in questions_qs.order_by("id")[:40]:
        if q.correct_option == "A":
            correct_text = q.option_a
        elif q.correct_option == "B":
            correct_text = q.option_b
        elif q.correct_option == "C":
            correct_text = q.option_c
        else:
            correct_text = q.option_d
        question_rows.append(
            {
                "question": q,
                "correct_text": correct_text,
            }
        )

    return render(
        request,
        "dashboard/attempt_review.jinja",
        {
            "attempt": attempt,
            "question_rows": question_rows,
        },
    )


@login_required
def mark_notification_read(request, note_id):
    Notification.objects.filter(pk=note_id, user=request.user).update(is_read=True)
    return redirect('dashboard:notifications')


@login_required
def recharge_wallet(request):
    if request.method == 'POST':
        if not cache.add(f'recharge:{request.user.id}', 1, 15):
            messages.warning(request, 'Please wait a few seconds between test recharges.')
            return redirect('dashboard:index')
        request.user.add_wallet(100, transaction_type='CREDIT_ADMIN', reference_id='recharge')
        from users.gamification import send_notification
        send_notification(request.user, '⚡ Wallet successfully recharged with ₹100 test credits!')
    return redirect('dashboard:index')


@login_required
def import_questions_csv(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect("dashboard:index")

    skills = Skill.objects.filter(is_active=True).order_by("name")
    errors = []
    imported = 0

    if request.method == "POST":
        skill_id = request.POST.get("skill_id")
        f = request.FILES.get("csv_file")
        skill = Skill.objects.filter(id=skill_id).first()
        if not skill:
            errors.append("Invalid skill selected.")
        if not f:
            errors.append("Please upload a CSV file.")
        if not errors and skill and f:
            try:
                content = f.read().decode("utf-8-sig")
                reader = csv.DictReader(io.StringIO(content))
                required = {
                    "text",
                    "option_a",
                    "option_b",
                    "option_c",
                    "option_d",
                    "correct_option",
                    "difficulty",
                    "concept_tag",
                    "explanation",
                }
                if not set(reader.fieldnames or []).issuperset(required):
                    missing = sorted(list(required - set(reader.fieldnames or [])))
                    errors.append("Missing columns: " + ", ".join(missing))
                else:
                    with transaction.atomic():
                        for idx, row in enumerate(reader, start=2):
                            co = (row.get("correct_option") or "").strip().upper()
                            if co not in ("A", "B", "C", "D"):
                                errors.append(f"Row {idx}: invalid correct_option")
                                continue
                            diff = (row.get("difficulty") or "EASY").strip().upper()
                            if diff not in ("EASY", "MEDIUM", "HARD"):
                                diff = "EASY"
                            Question.objects.create(
                                skill=skill,
                                text=(row.get("text") or "").strip(),
                                concept_tag=(row.get("concept_tag") or "").strip()[:50],
                                explanation=(row.get("explanation") or "").strip(),
                                difficulty=diff,
                                option_a=(row.get("option_a") or "").strip()[:200],
                                option_b=(row.get("option_b") or "").strip()[:200],
                                option_c=(row.get("option_c") or "").strip()[:200],
                                option_d=(row.get("option_d") or "").strip()[:200],
                                correct_option=co,
                            )
                            imported += 1
                    if imported:
                        skill.partition_questions()
            except Exception as e:
                errors.append(str(e))

    return render(
        request,
        "dashboard/import_questions.jinja",
        {
            "skills": skills,
            "errors": errors,
            "imported": imported,
        },
    )


@login_required
def ai_generate_mcqs(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect("dashboard:index")

    key_present = bool(os.environ.get("OPENAI_API_KEY"))
    return render(
        request,
        "dashboard/ai_generate_mcqs.jinja",
        {
            "key_present": key_present,
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Phase 4 CMS: minimal CRUD for core content (staff-only)
# ──────────────────────────────────────────────────────────────────────────────


@login_required
def cms_home(request):
    if not _staff_only(request):
        return redirect("dashboard:index")
    return render(request, "dashboard/cms_home.jinja")


@login_required
def cms_skillpaths(request):
    if not _staff_only(request):
        return redirect("dashboard:index")
    items = SkillPath.objects.order_by("level_order", "id")
    return render(request, "dashboard/cms_skillpaths.jinja", {"items": items})


@login_required
def cms_skillpath_edit(request, pk=None):
    if not _staff_only(request):
        return redirect("dashboard:index")
    obj = SkillPath.objects.filter(pk=pk).first() if pk else None
    if request.method == "POST":
        form = SkillPathForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved skill path.")
            return redirect("dashboard:cms_skillpaths")
    else:
        form = SkillPathForm(instance=obj)
    return render(request, "dashboard/cms_form.jinja", {"form": form, "title": "Skill Path"})


@login_required
def cms_skills(request):
    if not _staff_only(request):
        return redirect("dashboard:index")
    q = (request.GET.get("q") or "").strip()
    qs = Skill.objects.select_related("path").order_by("path__level_order", "order", "id")
    if q:
        qs = qs.filter(name__icontains=q)
    return render(request, "dashboard/cms_skills.jinja", {"items": qs[:200], "q": q})


@login_required
def cms_skill_edit(request, pk=None):
    if not _staff_only(request):
        return redirect("dashboard:index")
    obj = Skill.objects.filter(pk=pk).first() if pk else None
    if request.method == "POST":
        form = SkillForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved skill.")
            return redirect("dashboard:cms_skills")
    else:
        form = SkillForm(instance=obj)
    return render(request, "dashboard/cms_form.jinja", {"form": form, "title": "Skill"})


@login_required
def cms_questions(request):
    if not _staff_only(request):
        return redirect("dashboard:index")
    q = (request.GET.get("q") or "").strip()
    qs = Question.objects.select_related("skill", "question_set").order_by("-id")
    if q:
        qs = qs.filter(text__icontains=q)
    return render(request, "dashboard/cms_questions.jinja", {"items": qs[:200], "q": q})


@login_required
def cms_question_edit(request, pk=None):
    if not _staff_only(request):
        return redirect("dashboard:index")
    obj = Question.objects.filter(pk=pk).first() if pk else None
    if request.method == "POST":
        form = QuestionForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved question.")
            return redirect("dashboard:cms_questions")
    else:
        form = QuestionForm(instance=obj)
    return render(request, "dashboard/cms_form.jinja", {"form": form, "title": "Question"})


@login_required
def cms_videos(request):
    if not _staff_only(request):
        return redirect("dashboard:index")
    q = (request.GET.get("q") or "").strip()
    qs = ConceptVideo.objects.select_related("skill").order_by("-id")
    if q:
        qs = qs.filter(title__icontains=q)
    return render(request, "dashboard/cms_videos.jinja", {"items": qs[:200], "q": q})


@login_required
def cms_video_edit(request, pk=None):
    if not _staff_only(request):
        return redirect("dashboard:index")
    obj = ConceptVideo.objects.filter(pk=pk).first() if pk else None
    import_errors = []
    import_count = 0

    if request.method == "POST":
        action = request.POST.get("action", "save_video")
        if action == "import_questions":
            if not obj:
                messages.error(request, "Save the video first, then import questions.")
                return redirect("dashboard:cms_video_new")

            import_form = VideoQuestionImportForm(request.POST, request.FILES)
            form = ConceptVideoForm(instance=obj)
            if import_form.is_valid():
                default_skill = import_form.cleaned_data["skill"] or obj.skill
                concept_tag_fallback = (
                    (import_form.cleaned_data.get("concept_tag") or "").strip()
                    or (obj.concept_tag or "").strip()
                )
                f = import_form.cleaned_data.get("csv_file")
                csv_text = (import_form.cleaned_data.get("csv_text") or "").strip()
                try:
                    if f:
                        content = f.read().decode("utf-8-sig")
                    else:
                        content = csv_text
                    reader = csv.DictReader(io.StringIO(content))
                    required = {
                        "text",
                        "option_a",
                        "option_b",
                        "option_c",
                        "option_d",
                        "correct_option",
                        "difficulty",
                        "explanation",
                    }
                    if not set(reader.fieldnames or []).issuperset(required):
                        missing = sorted(list(required - set(reader.fieldnames or [])))
                        import_errors.append("Missing columns: " + ", ".join(missing))
                    else:
                        skill_name_present = "skill_name" in set(reader.fieldnames or [])
                        with transaction.atomic():
                            for idx, row in enumerate(reader, start=2):
                                co = (row.get("correct_option") or "").strip().upper()
                                if co not in ("A", "B", "C", "D"):
                                    import_errors.append(f"Row {idx}: invalid correct_option")
                                    continue
                                diff = (row.get("difficulty") or "EASY").strip().upper()
                                if diff not in ("EASY", "MEDIUM", "HARD"):
                                    diff = "EASY"

                                skill = default_skill
                                if skill_name_present:
                                    skill_name = (row.get("skill_name") or "").strip()
                                    if skill_name:
                                        skill = Skill.objects.filter(name__iexact=skill_name).first()
                                if not skill:
                                    import_errors.append(
                                        f"Row {idx}: skill missing. Set form skill or include valid skill_name."
                                    )
                                    continue

                                concept_tag = (
                                    (row.get("concept_tag") or "").strip()[:50]
                                    or concept_tag_fallback[:50]
                                )
                                if not concept_tag:
                                    import_errors.append(
                                        f"Row {idx}: concept_tag missing. Set form topic or include row concept_tag."
                                    )
                                    continue
                                question_text = (row.get("text") or "").strip()
                                defaults = {
                                    "source_video": obj,
                                    "is_video_import": True,
                                    "concept_tag": concept_tag,
                                    "explanation": (row.get("explanation") or "").strip(),
                                    "difficulty": diff,
                                    "option_a": (row.get("option_a") or "").strip()[:200],
                                    "option_b": (row.get("option_b") or "").strip()[:200],
                                    "option_c": (row.get("option_c") or "").strip()[:200],
                                    "option_d": (row.get("option_d") or "").strip()[:200],
                                    "correct_option": co,
                                }
                                Question.objects.update_or_create(
                                    skill=skill,
                                    text=question_text,
                                    defaults=defaults,
                                )
                                import_count += 1
                        if import_count:
                            if default_skill:
                                default_skill.partition_questions()
                            if skill_name_present:
                                for sname in {
                                    (row.get("skill_name") or "").strip()
                                    for row in csv.DictReader(io.StringIO(content))
                                    if (row.get("skill_name") or "").strip()
                                }:
                                    s = Skill.objects.filter(name__iexact=sname).first()
                                    if s:
                                        s.partition_questions()
                            messages.success(
                                request,
                                f"Imported {import_count} question(s) successfully.",
                            )
                except Exception as exc:
                    import_errors.append(str(exc))
            else:
                import_errors.extend(
                    [f"{k}: {', '.join(v)}" for k, v in import_form.errors.items()]
                )
                import_errors.extend(import_form.non_field_errors())
        else:
            form = ConceptVideoForm(request.POST, request.FILES, instance=obj)
            import_form = VideoQuestionImportForm(
                initial={
                    "skill": obj.skill if obj else None,
                    "concept_tag": obj.concept_tag if obj else "",
                }
            )
            if form.is_valid():
                form.save()
                messages.success(request, "Saved video.")
                return redirect("dashboard:cms_video_edit", pk=form.instance.pk)
    else:
        form = ConceptVideoForm(instance=obj)
        import_form = VideoQuestionImportForm(
            initial={
                "skill": obj.skill if obj else None,
                "concept_tag": obj.concept_tag if obj else "",
            }
        )
    return render(
        request,
        "dashboard/cms_video_form.jinja",
        {
            "form": form,
            "import_form": import_form,
            "title": "Video",
            "video_obj": obj,
            "import_errors": import_errors,
            "import_count": import_count,
        },
    )


@login_required
def cms_tasks(request):
    if not _staff_only(request):
        return redirect("dashboard:index")
    q = (request.GET.get("q") or "").strip()
    qs = EarningTask.objects.select_related("required_skill").order_by("-id")
    if q:
        qs = qs.filter(title__icontains=q)
    return render(request, "dashboard/cms_tasks.jinja", {"items": qs[:200], "q": q})


@login_required
def cms_task_edit(request, pk=None):
    if not _staff_only(request):
        return redirect("dashboard:index")
    obj = EarningTask.objects.filter(pk=pk).first() if pk else None
    if request.method == "POST":
        form = EarningTaskForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved task.")
            return redirect("dashboard:cms_tasks")
    else:
        form = EarningTaskForm(instance=obj)
    return render(request, "dashboard/cms_form.jinja", {"form": form, "title": "Earning Task"})
