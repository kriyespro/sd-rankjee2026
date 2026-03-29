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
    user = request.user
    referrals = user.referrals.all().order_by('-date_joined')
    referral_count = referrals.count()
    
    # Referral link construction
    scheme = 'https' if request.is_secure() else 'http'
    site_domain = request.get_host()
    referral_link = f"{scheme}://{site_domain}/users/signup/?ref={user.referral_code}"
    
    total_earned = user.wallet_balance
    
    return render(request, 'core/earnings.jinja', {
        'referrals': referrals,
        'referral_count': referral_count,
        'referral_link': referral_link,
        'total_earned': total_earned,
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
