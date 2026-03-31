from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, Count, Avg
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from assessment.models import UserAttempt, Question, Skill, UserSetAttempt
from core.models import UserTaskSubmission
from learning.models import ConceptVideo
from users.models import Notification

User = get_user_model()


@login_required
def index(request):
    if request.user.is_superuser or request.user.is_staff:
        # App-wide Admin Dashboard Stats
        total_users_count = User.objects.count()
        total_questions = Question.objects.count()
        total_videos = ConceptVideo.objects.count()
        total_skills = Skill.objects.filter(is_active=True).count()
        
        # User Search & Pagination
        search_query = request.GET.get('q', '').strip()
        users_queryset = User.objects.all().order_by('-date_joined')
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
        recent_registrations_count = User.objects.filter(date_joined__gte=last_7_days).count()
        
        # New analytics
        pending_submissions = UserTaskSubmission.objects.filter(status='PENDING').order_by('-submitted_at')
        pending_count = pending_submissions.count()
        
        total_payouts = UserTaskSubmission.objects.filter(status='APPROVED').aggregate(
            total=Sum('task__reward_amount')
        )['total'] or 0
        
        # Calculate total XP across platform to show engagement
        total_xp_platform = User.objects.aggregate(Sum('xp_points'))['xp_points__sum'] or 0

        return render(request, 'dashboard/admin_dashboard.jinja', {
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

    user_certificates = request.user.certificates.select_related('skill').order_by('-issued_at')

    return render(request, 'dashboard/index.jinja', {
        'user': request.user,
        'progress': progress,
        'total_earned': total_earned,
        'weak_areas': weak_areas,
        'latest_attempt': latest_attempt,
        'streak_days': request.user.streak_days,
        'user_badges': user_badges,
        'user_certificates': user_certificates, # Added
        'unread_notifications': unread_notifications,
        'learning_path': learning_path,
        'all_paths': all_paths,
        'selected_path': selected_path,
        'top_users': top_users,
    })


@login_required
def leaderboard(request):
    filter_state = request.GET.get('filter')
    if filter_state == 'state' and request.user.state:
        users_qs = User.objects.filter(state=request.user.state).order_by('-xp_points')
        title_suffix = f"({request.user.get_state_display()})"
    else:
        users_qs = User.objects.order_by('-xp_points')
        title_suffix = "(All India)"
        
    users = users_qs[:20]
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
def mark_notification_read(request, note_id):
    Notification.objects.filter(pk=note_id, user=request.user).update(is_read=True)
    return redirect('dashboard:notifications')


@login_required
def recharge_wallet(request):
    if request.method == 'POST':
        request.user.add_wallet(100, transaction_type='CREDIT_ADMIN', reference_id='recharge')
        from users.gamification import send_notification
        send_notification(request.user, '⚡ Wallet successfully recharged with ₹100 test credits!')
    return redirect('dashboard:index')
