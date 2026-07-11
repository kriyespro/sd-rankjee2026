"""
Gamification helper: Award XP, Wallet, Badges and Notifications.
Import and call these helpers from views after key actions.
"""
from django.utils import timezone
from .models import Badge, UserBadge, Notification


# ── XP constants ──────────────────────────────────────────────────────────────
XP_FIRST_TEST = 10
XP_PASS_TEST = 25
XP_TASK_APPROVED = 15
XP_REFERRAL = 20
XP_STREAK_LOGIN = 5


def _try_award_badge(user, badge_type):
    """Award badge if user doesn't already possess it. Returns badge or None."""
    try:
        badge = Badge.objects.get(badge_type=badge_type)
        _, created = UserBadge.objects.get_or_create(user=user, badge=badge)
        if created:
            Notification.objects.create(
                user=user,
                message=f"🎉 You earned the '{badge.title}' badge!",
                link='/admin/',
            )
            return badge
    except Badge.DoesNotExist:
        pass
    return None


def send_notification(user, message, link=''):
    Notification.objects.create(
        user=user,
        message=(message or '')[:300],
        link=(link or '')[:200],
    )


def on_test_submitted(user, passed, skill=None):
    """Call after every assessment submission."""
    from assessment.models import UserAttempt
    attempt_count = UserAttempt.objects.filter(user=user).count()

    # First test badge
    if attempt_count == 1:
        user.add_xp(XP_FIRST_TEST)
        _try_award_badge(user, 'FIRST_TEST')
        send_notification(user, f'🎯 +{XP_FIRST_TEST} XP for your first test!')

    if passed:
        user.add_xp(XP_PASS_TEST)
        _try_award_badge(user, 'FIRST_PASS')
        send_notification(user, f'🏆 +{XP_PASS_TEST} XP – Test passed! Keep going!')
        
        if skill:
            from core.models import EarningTask
            unlocked_tasks = EarningTask.objects.filter(required_skill=skill, is_active=True).count()
            if unlocked_tasks > 0:
                send_notification(user, f'🔓 You unlocked {unlocked_tasks} new earning task(s) for mastering {skill.name}!', link='/earnings/')


def on_task_approved(user, task):
    """Call when a task submission is auto-approved or manually approved."""
    from users.models import WalletTransaction

    if WalletTransaction.objects.filter(
        user=user, transaction_type='EARN_TASK', reference_id=str(task.id)
    ).exists():
        return

    from core.models import UserTaskSubmission
    user.add_xp(XP_TASK_APPROVED)
    user.add_wallet(task.reward_amount, transaction_type='EARN_TASK', reference_id=str(task.id))

    approved_count = UserTaskSubmission.objects.filter(user=user, status='APPROVED').count()
    if approved_count == 1:
        _try_award_badge(user, 'FIRST_EARN')

    send_notification(
        user,
        f'💰 Task "{task.title}" approved! +₹{task.reward_amount} and +{XP_TASK_APPROVED} XP added.',
        link='/earn/',
    )


def on_referral_signup(new_user, referrer):
    """Call from signup when a referral_code is used."""
    referrer.add_xp(XP_REFERRAL)
    referrer.add_wallet(50, transaction_type='EARN_REFERRAL', reference_id=str(new_user.id))  # ₹50 referral bonus
    _try_award_badge(referrer, 'REFERRAL')
    send_notification(
        referrer,
        f'🤝 {new_user.username} joined using your referral code! +₹50 and +{XP_REFERRAL} XP!',
    )


def on_streak_login(user):
    """Call after streak days are updated."""
    if user.streak_days >= 30:
        _try_award_badge(user, 'STREAK_30')
        send_notification(user, '⚡ 30-day streak! You are unstoppable!')
    elif user.streak_days >= 7:
        _try_award_badge(user, 'STREAK_7')
        send_notification(user, '🔥 7-day streak! You earned the Streak badge!')

    user.add_xp(XP_STREAK_LOGIN)
