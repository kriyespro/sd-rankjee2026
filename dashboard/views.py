from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Sum, Q, Count, Avg, Case, When, IntegerField
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from assessment.models import UserAttempt, Question, Skill, UserSetAttempt
from assessment.models import SkillPath
from core.models import UserTaskSubmission
from core.models import EarningTask
from learning.models import ConceptVideo
from users.models import Notification, WithdrawalRequest
from django.db import transaction
import csv
import io
import os

from .forms import (
    EarningTaskForm,
    ConceptVideoForm,
    QuestionForm,
    SkillForm,
    SkillPathForm,
)

User = get_user_model()


def _staff_only(request):
    return request.user.is_staff or request.user.is_superuser


@login_required
def index(request):
    role = getattr(request.user, 'role', 'STUDENT')
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
        })

    # Normal User Dashboard
    latest_attempt = UserAttempt.objects.filter(
        user=request.user
    ).order_by('-attempt_date').first()

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

    user_certificates = request.user.certificates.select_related('skill').order_by('-issued_at')

    xp_rank_india = User.objects.filter(xp_points__gt=request.user.xp_points).count() + 1

    from hometutor.models import DemoRequest, TutorProfile

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
        'role_stat_cards': role_stat_cards,
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
        'next_badge_hint': next_badge_hint,
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
    if request.method == "POST":
        form = ConceptVideoForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved video.")
            return redirect("dashboard:cms_videos")
    else:
        form = ConceptVideoForm(instance=obj)
    return render(request, "dashboard/cms_form.jinja", {"form": form, "title": "Video"})


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
