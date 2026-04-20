import logging

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.cache import cache
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from assessment.models import UserAttempt
from core.models import UserTaskSubmission
from .forms import CustomUserCreationForm
from .gamification import on_referral_signup, on_streak_login, send_notification
from .models import CompanyInquiry, CustomUser, PublicProfile
from .tasks import send_welcome_email

logger = logging.getLogger("rankjee.signup")


def _enqueue_welcome_email(user_id):
    """Never fail the HTTP response if Celery/Redis is down."""
    try:
        # Ignore task result to avoid result-backend (Redis) dependency in web requests.
        send_welcome_email.apply_async(args=[user_id], ignore_result=True)
    except Exception as exc:
        logger.warning(
            "Welcome email task not queued (user_id=%s): %s",
            user_id,
            exc,
        )


def _update_streak(user):
    today = timezone.now().date()
    if user.last_active_date is None:
        user.streak_days = 1
        reward_daily = True
    elif user.last_active_date == today:
        reward_daily = False
        pass  # already counted today
    elif (today - user.last_active_date).days == 1:
        user.streak_days += 1
        reward_daily = True
    else:
        user.streak_days = 1  # reset streak
        reward_daily = True

    user.last_active_date = today
    user.save(update_fields=['streak_days', 'last_active_date'])
    
    if reward_daily:
        try:
            user.add_wallet(1, transaction_type='EARN_DAILY')
            from .gamification import send_notification
            send_notification(user, '🪙 +₹1 daily login reward added to your wallet!')
            on_streak_login(user)
        except Exception as exc:
            # Signup/login must succeed even if optional reward side-effects fail.
            logger.warning("Streak reward side-effects failed for user_id=%s: %s", user.id, exc, exc_info=True)


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    
    if request.method == 'POST':
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        try:
            if not cache.add(f"rl:signup:{ip}", 1, 30):
                messages.error(request, "Please wait a few seconds and try again.")
                return redirect('users:signup')
        except Exception as exc:
            # Fail open if Redis/cache is temporarily unavailable.
            logger.warning("Signup rate-limit cache unavailable for ip=%s: %s", ip, exc, exc_info=True)
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.add_wallet(50, transaction_type='CREDIT_SIGNUP')  # Give new user ₹50 free credit on signup
            
            # Handle referral code
            ref_code = request.POST.get('referral_code', '').strip().upper()
            if ref_code:
                try:
                    referrer = CustomUser.objects.get(referral_code=ref_code)
                    if referrer != user:
                        user.referred_by = referrer
                        user.save(update_fields=['referred_by'])
                        on_referral_signup(user, referrer)
                        if settings.REFERRAL_PREMIUM_ENABLED:
                            # Temporary Pro unlock for referral onboarding/testing.
                            from payments.models import SubscriptionPlan, UserSubscription

                            trial_plan = (
                                SubscriptionPlan.objects.filter(is_active=True).order_by("price").first()
                            )
                            if not trial_plan:
                                # Safety fallback for fresh/live DBs with no active plans yet.
                                trial_plan = (
                                    SubscriptionPlan.objects.filter(name="Referral Test Pro").order_by("-id").first()
                                )
                            if not trial_plan:
                                trial_plan = SubscriptionPlan.objects.create(
                                    name="Referral Test Pro",
                                    description="Auto-created zero-price plan for referral testing unlocks.",
                                    price=0,
                                    duration_days=max(1, int(settings.REFERRAL_PREMIUM_DAYS)),
                                    is_active=False,
                                    features=["Referral test premium access"],
                                )
                            if trial_plan:
                                sub, created = UserSubscription.objects.get_or_create(
                                    user=user,
                                    defaults={
                                        "plan": trial_plan,
                                        "end_date": timezone.now() + timedelta(days=settings.REFERRAL_PREMIUM_DAYS),
                                        "is_active": True,
                                    },
                                )
                                if not created:
                                    base = sub.end_date if sub.end_date and sub.end_date > timezone.now() else timezone.now()
                                    sub.plan = trial_plan
                                    sub.end_date = base + timedelta(days=settings.REFERRAL_PREMIUM_DAYS)
                                    sub.is_active = True
                                    sub.save(update_fields=["plan", "end_date", "is_active"])
                except CustomUser.DoesNotExist:
                    pass
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            _update_streak(user)
            # After DB commit, queue welcome email (Redis/Celery failures must not 500 signup)
            transaction.on_commit(lambda uid=user.id: _enqueue_welcome_email(uid))
            return redirect('dashboard:index')
    else:
        form = CustomUserCreationForm()
    ref_code = request.GET.get('ref', '')
    return render(request, 'users/signup.jinja', {'form': form, 'ref_code': ref_code})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            _update_streak(user)
            return redirect('dashboard:index')
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.jinja', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('core:home')


@login_required
def profile_view(request):
    default_slug = slugify(f'{request.user.username}-{request.user.pk}') or f'user-{request.user.pk}'
    pub, _ = PublicProfile.objects.get_or_create(
        user=request.user,
        defaults={'slug': default_slug, 'is_public': False},
    )
    if request.method == 'POST' and request.POST.get('form') == 'public_profile':
        pub.headline = (request.POST.get('headline') or '')[:200]
        raw_slug = slugify(request.POST.get('slug', '').strip() or request.user.username)
        if not raw_slug:
            raw_slug = default_slug
        candidate = raw_slug
        n = 1
        while PublicProfile.objects.filter(slug=candidate).exclude(pk=pub.pk).exists():
            candidate = f'{raw_slug}-{n}'
            n += 1
        pub.slug = candidate
        pub.is_public = request.POST.get('is_public') == 'on'
        pub.save()
        messages.success(request, 'Public hiring profile updated.')
        return redirect('users:profile')

    attempts = UserAttempt.objects.filter(user=request.user).order_by('-attempt_date')
    total_earned = UserTaskSubmission.objects.filter(
        user=request.user, status='APPROVED'
    ).aggregate(total=Sum('task__reward_amount'))['total'] or 0
    user_badges = request.user.badges.select_related('badge').order_by('-awarded_at')
    inquiries = CompanyInquiry.objects.filter(candidate=request.user).order_by('-created_at')[:10]
    public_url = request.build_absolute_uri(f'/users/u/{pub.slug}/')
    return render(
        request,
        'users/profile.jinja',
        {
            'attempts': attempts,
            'total_earned': total_earned,
            'user': request.user,
            'user_badges': user_badges,
            'public_profile': pub,
            'public_profile_url': public_url,
            'inquiries': inquiries,
        },
    )


def set_ui_lang(request, lang):
    if lang in ('hi', 'en'):
        request.session['ui_lang'] = lang
    nxt = request.GET.get('next') or '/'
    if not nxt.startswith('/') or nxt.startswith('//'):
        nxt = '/'
    return redirect(nxt)


def public_profile(request, slug):
    pub = get_object_or_404(
        PublicProfile.objects.select_related('user'),
        slug=slug,
        is_public=True,
    )
    user = pub.user
    badges = user.badges.select_related('badge').order_by('-awarded_at')[:12]
    attempts_total = UserAttempt.objects.filter(user=user).count()
    passed_total = UserAttempt.objects.filter(user=user, passed=True).count()
    return render(
        request,
        'users/public_profile.jinja',
        {
            'pub': pub,
            'badges': badges,
            'attempts_total': attempts_total,
            'passed_total': passed_total,
        },
    )


def company_inquiry_submit(request, slug):
    pub = get_object_or_404(PublicProfile, slug=slug, is_public=True)
    if request.method != 'POST':
        return redirect('users:public_profile', slug=slug)
    if request.POST.get('website', '').strip():
        return redirect('users:public_profile', slug=slug)
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    ck = f'hireinq:{ip}'
    try:
        n = int(cache.get(ck, 0))
    except (TypeError, ValueError):
        n = 0
    if n >= 5:
        messages.error(request, 'Too many submissions from this network. Try again later.')
        return redirect('users:public_profile', slug=slug)
    cache.set(ck, n + 1, 3600)
    company_name = (request.POST.get('company_name') or '').strip()[:200]
    contact_email = (request.POST.get('contact_email') or '').strip()[:320]
    body = (request.POST.get('message') or '').strip()[:2000]
    if not company_name or not contact_email or not body:
        messages.error(request, 'Please fill company name, email, and message.')
        return redirect('users:public_profile', slug=slug)
    CompanyInquiry.objects.create(
        candidate=pub.user,
        company_name=company_name,
        contact_email=contact_email,
        message=body,
    )
    send_notification(
        pub.user,
        f'📋 Hiring inquiry from {company_name}',
        link='/users/profile/',
    )
    messages.success(request, 'Thank you. The learner will be notified.')
    return redirect('users:public_profile', slug=slug)

@login_required
def regenerate_referral(request):
    if request.method == 'POST':
        if not cache.add(f"rl:refregen:{request.user.id}", 1, 10):
            messages.warning(request, "Please wait a few seconds before regenerating again.")
            return redirect('dashboard:index')
        import uuid
        request.user.referral_code = uuid.uuid4().hex[:8].upper()
        request.user.save(update_fields=['referral_code'])
    return redirect('dashboard:index')
