from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.conf import settings
from django.contrib.auth import get_user_model
from assessment.models import UserAttempt, Question, Skill, UserSetAttempt
from core.models import UserTaskSubmission
from learning.models import ConceptVideo
from users.models import Notification

User = get_user_model()


@login_required
def index(request):
    if request.user.is_superuser or request.user.is_staff:
        # App-wide Admin Dashboard Stats
        total_users = User.objects.count()
        total_questions = Question.objects.count()
        total_videos = ConceptVideo.objects.count()
        total_skills = Skill.objects.filter(is_active=True).count()
        recent_users = User.objects.order_by('-date_joined')[:5]
        recent_videos = ConceptVideo.objects.order_by('-id')[:5]
        
        # New analytics
        pending_submissions = UserTaskSubmission.objects.filter(status='PENDING').order_by('-submitted_at')
        pending_count = pending_submissions.count()
        
        total_payouts = UserTaskSubmission.objects.filter(status='APPROVED').aggregate(
            total=Sum('task__reward_amount')
        )['total'] or 0
        
        active_tasks_count = Skill.objects.filter(is_active=True).count() # Earning tasks linked to skills
        
        # Calculate total XP across platform to show engagement
        total_xp_platform = User.objects.aggregate(Sum('xp_points'))['xp_points__sum'] or 0

        return render(request, 'dashboard/admin_dashboard.jinja', {
            'total_users': total_users,
            'total_questions': total_questions,
            'total_videos': total_videos,
            'total_skills': total_skills,
            'recent_users': recent_users,
            'recent_videos': recent_videos,
            'total_xp_platform': total_xp_platform,
            'pending_submissions': pending_submissions[:10],
            'pending_count': pending_count,
            'total_payouts': total_payouts,
            'active_tasks_count': active_tasks_count,
        })

    # Normal User Dashboard
    latest_attempt = UserAttempt.objects.filter(
        user=request.user
    ).order_by('-attempt_date').first()

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

    latest_attempt = UserAttempt.objects.filter(user=request.user).order_by('-attempt_date').first()
    weak_areas = latest_attempt.weak_concepts if latest_attempt else []
    user_badges = request.user.badges.select_related('badge').order_by('-awarded_at')
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()

    return render(request, 'dashboard/index.jinja', {
        'user': request.user,
        'progress': progress,
        'total_earned': total_earned,
        'weak_areas': weak_areas,
        'latest_attempt': latest_attempt,
        'streak_days': request.user.streak_days,
        'user_badges': user_badges,
        'unread_notifications': unread_notifications,
        'learning_path': learning_path,
        'all_paths': all_paths,
        'selected_path': selected_path,
        'top_users': top_users,
    })


@login_required
def leaderboard(request):
    users = User.objects.order_by('-xp_points')[:20]
    user_rank = None
    for idx, u in enumerate(users, start=1):
        if u.pk == request.user.pk:
            user_rank = idx
            break
    return render(request, 'dashboard/leaderboard.jinja', {
        'users': users,
        'user_rank': user_rank,
    })


@login_required
def notifications(request):
    notes = Notification.objects.filter(user=request.user)
    # Mark all as read when viewed
    notes.filter(is_read=False).update(is_read=True)
    return render(request, 'dashboard/notifications.jinja', {'notifications': notes})


@login_required
def mark_notification_read(request, note_id):
    Notification.objects.filter(pk=note_id, user=request.user).update(is_read=True)
    return redirect('dashboard:notifications')


@login_required
def recharge_wallet(request):
    if request.method == 'POST':
        request.user.add_wallet(100)
        from users.gamification import send_notification
        send_notification(request.user, '⚡ Wallet successfully recharged with ₹100 test credits!')
    return redirect('dashboard:index')
