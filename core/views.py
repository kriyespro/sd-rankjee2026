from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.contrib import messages
from .models import EarningTask, UserTaskSubmission
from assessment.models import UserAttempt
from users.gamification import on_task_approved


def home(request):
    return render(request, 'core/home.jinja')


@login_required
def earnings(request):
    passed_skill_ids = set(UserAttempt.objects.filter(
        user=request.user, passed=True
    ).values_list('skill_id', flat=True))
    all_tasks = EarningTask.objects.filter(
        is_active=True
    ).select_related('required_skill')
    submitted_task_ids = UserTaskSubmission.objects.filter(
        user=request.user
    ).values_list('task_id', flat=True)
    total_earned = request.user.wallet_balance
    submissions = UserTaskSubmission.objects.filter(user=request.user).select_related('task').order_by('-submitted_at')
    return render(request, 'core/earnings.jinja', {
        'tasks': all_tasks,
        'passed_skill_ids': passed_skill_ids,
        'submitted_ids': list(submitted_task_ids),
        'total_earned': total_earned,
        'submissions': submissions,
    })


@login_required
def submit_task(request, task_id):
    if request.method == 'POST':
        task = get_object_or_404(EarningTask, pk=task_id, is_active=True)
        proof_url = request.POST.get('proof_url', '')
        proof_text = request.POST.get('proof_text', '')
        submission, created = UserTaskSubmission.objects.get_or_create(
            user=request.user,
            task=task,
            defaults={'proof_url': proof_url, 'proof_text': proof_text}
        )
        # Auto-approve if proof URL matches domain
        if created and task.auto_approve_domain and proof_url:
            if task.auto_approve_domain.lower() in proof_url.lower():
                submission.status = 'APPROVED'
                submission.save(update_fields=['status'])
                on_task_approved(request.user, task)
    return redirect('core:earnings')


@login_required
def admin_approve_submission(request, submission_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('dashboard:index')
    
    try:
        submission = UserTaskSubmission.objects.get(pk=submission_id)
        if submission.status != 'PENDING':
            messages.warning(request, f"Task '{submission.task.title}' was already {submission.status.lower()}.")
            return redirect('dashboard:index')
        
        submission.status = 'APPROVED'
        submission.save(update_fields=['status'])
        
        # Trigger gamification
        on_task_approved(submission.user, submission.task)
        messages.success(request, f"Task approved for {submission.user.username}. ₹{submission.task.reward_amount} added to wallet.")
        
    except UserTaskSubmission.DoesNotExist:
        messages.error(request, "Task submission not found.")
    
    return redirect('dashboard:index')


@login_required
def admin_reject_submission(request, submission_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('dashboard:index')
    
    try:
        submission = UserTaskSubmission.objects.get(pk=submission_id)
        if submission.status != 'PENDING':
            messages.warning(request, f"Task '{submission.task.title}' was already {submission.status.lower()}.")
            return redirect('dashboard:index')
            
        submission.status = 'REJECTED'
        submission.save(update_fields=['status'])
        messages.info(request, f"Task submission rejected for {submission.user.username}.")
        
    except UserTaskSubmission.DoesNotExist:
        messages.error(request, "Task submission not found.")
    
    return redirect('dashboard:index')
