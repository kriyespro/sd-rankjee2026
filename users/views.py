import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from assessment.models import UserAttempt
from core.models import UserTaskSubmission
from core.hometutor_data import PILOT_CITY
from hometutor.models import TutorProfile
from .forms import (
    CustomUserCreationForm,
    RoleSelectionForm,
    StudentParentOnboardingForm,
    TutorOnboardingForm,
)
from .gamification import on_streak_login, send_notification
from .models import CompanyInquiry, CustomUser, PublicProfile
from .referrals import process_referral_signup
from .subscription import try_apply_signup_pro_trial
from core.services_referral_dashboard import log_referral_click
from .tasks import send_welcome_email

from .onboarding import (
    PUBLIC_SELF_ASSIGNABLE_ROLES,
    ROLE_PICKER_ROWS,
    SESSION_NEEDS_ROLE_PICKER,
    begin_email_signup_onboarding,
    complete_role_selection,
    post_auth_redirect_target,
    signup_role_from_request,
    store_pending_google_signup_role,
    user_needs_role_picker,
)

logger = logging.getLogger("rankjee.signup")


def _auth_redirect(request, *, from_email_signup=False):
    return redirect(post_auth_redirect_target(request, from_email_signup=from_email_signup))


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
        return _auth_redirect(request)

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
            begin_email_signup_onboarding(request, user)
            user.add_wallet(50, transaction_type='CREDIT_SIGNUP')  # Give new user ₹50 free credit on signup
            try_apply_signup_pro_trial(user)

            # Handle referral code (email signup path); also stored in session for social signup path.
            ref_code = request.POST.get('referral_code', '').strip().upper()
            if ref_code:
                process_referral_signup(user, ref_code)
            request.session.pop("pending_referral_code", None)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            _update_streak(user)
            # After DB commit, queue welcome email (Redis/Celery failures must not 500 signup)
            transaction.on_commit(lambda uid=user.id: _enqueue_welcome_email(uid))
            return _auth_redirect(request, from_email_signup=True)
    else:
        role_initial = signup_role_from_request(request)
        form = CustomUserCreationForm(initial={"role": role_initial})
    ref_code = (request.GET.get("ref") or request.POST.get("referral_code") or "").strip().upper()
    if request.method != "POST" and ref_code:
        request.session["pending_referral_code"] = ref_code
        log_referral_click(request, ref_code)
    selected = (
        request.POST.get("role")
        if request.method == "POST"
        else signup_role_from_request(request)
    )
    return render(
        request,
        "users/signup.jinja",
        {
            "form": form,
            "ref_code": ref_code,
            "selected_role": selected or CustomUser.Role.STUDENT,
            "role_rows": ROLE_PICKER_ROWS,
        },
    )


def google_signup_start(request):
    """Store role from signup page, then start Google OAuth (avoids duplicate role screen)."""
    store_pending_google_signup_role(request)
    return redirect("/accounts/google/login/?process=signup")


def login_view(request):
    if request.user.is_authenticated:
        return _auth_redirect(request)

    next_url = request.POST.get('next') or request.GET.get('next') or ''
    role_hint = (request.GET.get('role') or '').strip().upper()
    if request.method == 'POST':
        # Let people log in with the email they signed up with — resolve it to the
        # username before AuthenticationForm/Axes see it. Ambiguous (duplicate) emails
        # fall through untouched and fail normal validation.
        post_data = request.POST
        identifier = (post_data.get('username') or '').strip()
        if '@' in identifier:
            matches = list(
                CustomUser.objects.filter(email__iexact=identifier).values_list('username', flat=True)[:2]
            )
            if len(matches) == 1:
                post_data = post_data.copy()
                post_data['username'] = matches[0]
        form = AuthenticationForm(request, data=post_data)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            _update_streak(user)
            return _auth_redirect(request)
    else:
        form = AuthenticationForm()
    form.fields['username'].label = 'Username or email'
    return render(
        request,
        'users/login.jinja',
        {'form': form, 'next_url': next_url, 'role_hint': role_hint},
    )


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

    attempts = UserAttempt.objects.filter(user=request.user).select_related("skill").order_by('-attempt_date')[:50]
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


@login_required
def family_hub(request):
    """Parent <-> Student linking (fix-rankjee.md Phase 2).

    Parents request a link by username/email; Students approve/reject; either side can
    revoke later. Approved parents get a read-only progress snapshot per linked student.
    """
    from . import services as family_services
    from .forms import ParentLinkRequestForm
    from .models import CustomUser

    role = getattr(request.user, 'role', None)
    request_form = ParentLinkRequestForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'request_link' and role == CustomUser.Role.PARENT:
            request_form = ParentLinkRequestForm(request.POST)
            if request_form.is_valid():
                try:
                    family_services.request_parent_link(
                        request.user, request_form.cleaned_data['identifier']
                    )
                    messages.success(request, 'Request sent — the student needs to approve it.')
                    return redirect('users:family_hub')
                except ValidationError as exc:
                    request_form.add_error('identifier', exc.messages[0] if hasattr(exc, 'messages') else str(exc))
        elif action == 'approve':
            try:
                family_services.approve_parent_link(request.user, request.POST.get('link_id'))
                messages.success(request, 'Link approved.')
            except ValidationError as exc:
                messages.error(request, str(exc))
            return redirect('users:family_hub')
        elif action == 'remove':
            if family_services.remove_parent_link(request.user, request.POST.get('link_id')):
                messages.success(request, 'Link removed.')
            return redirect('users:family_hub')

    context = {
        'user_role': role,
        'request_form': request_form,
    }
    if role == CustomUser.Role.PARENT:
        links = list(family_services.linked_students_for_parent(request.user, verified_only=False))
        context['my_links'] = links
        context['student_summaries'] = {
            link.student_id: family_services.student_progress_summary(link.student)
            for link in links
            if link.is_verified
        }
    elif role == CustomUser.Role.STUDENT:
        context['my_parent_links'] = list(family_services.links_for_student(request.user))
    return render(request, 'users/family.jinja', context)


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


@login_required
def onboarding_role(request):
    if request.user.onboarding_completed:
        return redirect('dashboard:index')

    if not user_needs_role_picker(request):
        return redirect('users:onboarding_profile')

    if request.method == 'POST':
        form = RoleSelectionForm(request.POST)
        if form.is_valid():
            complete_role_selection(request, request.user, form.cleaned_data['role'])
            return redirect('users:onboarding_profile')
    else:
        form = RoleSelectionForm(initial={'role': request.user.role})
    return render(
        request,
        'users/onboarding_role.jinja',
        {'form': form, 'role_rows': ROLE_PICKER_ROWS},
    )


@login_required
def onboarding_profile(request):
    # ?edit=1 lets a completed user reopen this form to update contact/academic info
    # (e.g. the student dashboard's "Set your class to personalize" link).
    _editing = request.GET.get('edit') == '1'
    if request.user.onboarding_completed and not _editing:
        return redirect('dashboard:index')
    if user_needs_role_picker(request):
        return redirect('users:onboarding_role')

    role = request.user.role
    if role not in PUBLIC_SELF_ASSIGNABLE_ROLES:
        # Roles like FACULTY/CITY_ADMIN/GLOBAL_ADMIN/VIP_USER are admin/office-provisioned, never
        # chosen via this wizard (RoleSelectionForm only offers Student/Parent/Tutor), so bouncing
        # back to onboarding_role would just bounce right back here forever — onboarding_role only
        # renders the picker when `user_needs_role_picker` is set, which it isn't in this branch.
        # Fix: nothing for this account to configure here, so mark onboarding done and move on.
        request.user.onboarding_completed = True
        request.user.save(update_fields=['onboarding_completed'])
        return redirect('dashboard:index')

    if role == CustomUser.Role.TUTOR:
        profile = TutorProfile.objects.filter(user=request.user).first()
        tutor_initial = {}
        if not profile:
            tutor_initial = {
                'display_name': (request.user.get_full_name() or request.user.username).strip(),
                'city': request.user.city or PILOT_CITY,
                'phone': request.user.phone,
                'subjects': '',
                'teaching_mode': TutorProfile.TeachingMode.HYBRID,
                'teaches_from': 6,
                'teaches_to': 12,
            }
        if request.method == 'POST':
            form = TutorOnboardingForm(request.POST, instance=profile)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.user = request.user
                obj.verification_status = TutorProfile.VerificationStatus.PENDING
                obj.save()
                # Contact info is mandatory platform-wide — keep the canonical copy on the user.
                request.user.phone = form.cleaned_data['phone']
                request.user.city = obj.city
                request.user.onboarding_completed = True
                request.user.save(update_fields=['phone', 'city', 'onboarding_completed'])
                messages.success(request, 'Tutor onboarding complete. Finish your listing to start receiving demos.')
                return redirect('hometutor:my_profile')
        else:
            form = TutorOnboardingForm(instance=profile, initial=tutor_initial if not profile else None)
        return render(
            request,
            'users/onboarding_profile.jinja',
            {
                'form': form,
                'role': role,
                'role_label': 'Tutor',
                'quick_fields': TutorOnboardingForm.QUICK_FIELDS,
                'optional_fields': TutorOnboardingForm.OPTIONAL_FIELDS,
            },
        )

    _is_student = role == CustomUser.Role.STUDENT
    if request.method == 'POST':
        # "Skip" only skips the optional fields (name/state) — contact info is mandatory,
        # and a student's class+subjects are too (they drive dashboard personalization).
        _skip_ok = request.user.phone and request.user.city and (
            not _is_student or (request.user.level_id and request.user.subjects)
        )
        if request.POST.get('action') == 'skip' and _skip_ok:
            request.user.onboarding_completed = True
            request.user.save(update_fields=['onboarding_completed'])
            messages.info(request, 'You can finish your profile anytime from settings.')
            return redirect('dashboard:index')
        form = StudentParentOnboardingForm(request.POST, instance=request.user, student=_is_student)
        if form.is_valid():
            form.save()
            request.user.onboarding_completed = True
            request.user.save(update_fields=['onboarding_completed'])
            messages.success(request, 'Welcome! Your account is ready.')
            return redirect('dashboard:index')
    else:
        form = StudentParentOnboardingForm(instance=request.user, student=_is_student)

    return render(
        request,
        'users/onboarding_profile.jinja',
        {
            'form': form,
            'role': role,
            'subject_suggestions': StudentParentOnboardingForm.SUBJECT_SUGGESTIONS,
            'role_label': 'Student' if role == CustomUser.Role.STUDENT else 'Parent',
        },
    )
