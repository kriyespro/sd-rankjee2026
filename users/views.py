from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
from .forms import CustomUserCreationForm
from .gamification import on_streak_login, on_referral_signup
from assessment.models import UserAttempt
from core.models import UserTaskSubmission


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
        user.add_wallet(1)
        from .gamification import send_notification
        send_notification(user, '🪙 +₹1 daily login reward added to your wallet!')
        on_streak_login(user)


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.add_wallet(50)  # Give new user ₹50 free credit on signup
            
            # Handle referral code
            ref_code = request.POST.get('referral_code', '').strip().upper()
            if ref_code:
                from .models import CustomUser
                try:
                    referrer = CustomUser.objects.get(referral_code=ref_code)
                    if referrer != user:
                        user.referred_by = referrer
                        user.save(update_fields=['referred_by'])
                        on_referral_signup(user, referrer)
                except CustomUser.DoesNotExist:
                    pass
            login(request, user)
            _update_streak(user)
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
    attempts = UserAttempt.objects.filter(user=request.user).order_by('-attempt_date')
    total_earned = UserTaskSubmission.objects.filter(
        user=request.user, status='APPROVED'
    ).aggregate(total=Sum('task__reward_amount'))['total'] or 0
    user_badges = request.user.badges.select_related('badge').order_by('-awarded_at')
    return render(request, 'users/profile.jinja', {
        'attempts': attempts,
        'total_earned': total_earned,
        'user': request.user,
        'user_badges': user_badges,
    })

@login_required
def regenerate_referral(request):
    if request.method == 'POST':
        import uuid
        request.user.referral_code = uuid.uuid4().hex[:8].upper()
        request.user.save(update_fields=['referral_code'])
    return redirect('dashboard:index')
