from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.contrib import messages
from .models import EarningTask, UserTaskSubmission
from assessment.models import UserAttempt
from users.gamification import on_task_approved


from django.utils import timezone
from assessment.models import DailyJackpot

def home(request):
    now = timezone.now()
    jackpot = DailyJackpot.objects.filter(is_active=True, is_completed=False).order_by('scheduled_time').first()
    time_to_go = int((jackpot.scheduled_time - now).total_seconds()) if jackpot else 0
    return render(request, 'core/home.jinja', {
        'jackpot': jackpot,
        'jackpot_time_to_go': time_to_go
    })


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
    wallet_transactions = user.wallet_transactions.all()[:20]
    withdrawals = user.withdrawals.all()[:5]
    
    return render(request, 'core/earnings.jinja', {
        'referrals': referrals,
        'referral_count': referral_count,
        'referral_link': referral_link,
        'total_earned': total_earned,
        'transactions': wallet_transactions,
        'withdrawals': withdrawals,
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
        
        # Gamification is handled via the post_save signal in core/signals.py
        messages.success(request, f"Task approved for {submission.user.username}. ₹{submission.task.reward_amount} added to wallet via automated signal.")
        
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


@login_required
def watch_ads(request):
    return render(request, 'core/watch_ads.jinja')


@login_required
def claim_ad_reward(request):
    if request.method == 'POST':
        # Basic anti-abuse check: prevent claims more than once every 30 seconds
        import time
        last_claim = request.session.get('last_ad_claim', 0)
        current_time = time.time()
        
        if current_time - last_claim < 30:
            messages.warning(request, "Please wait for the ad to finish before claiming.")
            return redirect('core:watch_ads')
            
        reward_amount = 0.50
        request.user.add_wallet(reward_amount, transaction_type='OTHER', reference_id='ad_watch')
        request.session['last_ad_claim'] = current_time
        messages.success(request, f"🎉 Success! ₹{reward_amount} added to your wallet.")
        
    return redirect('core:watch_ads')


@login_required
def request_withdrawal(request):
    if request.method == 'POST':
        from users.models import WithdrawalRequest
        from decimal import Decimal
        amount_str = request.POST.get('amount', '0')
        upi_id = request.POST.get('upi_id', '').strip()
        
        try:
            amount = Decimal(amount_str)
            if amount < 100:
                messages.error(request, "Minimum withdrawal amount is ₹100.")
            elif amount > request.user.wallet_balance:
                messages.error(request, "Insufficient wallet balance.")
            elif not upi_id:
                messages.error(request, "Please provide a valid UPI ID.")
            else:
                request.user.add_wallet(-amount, transaction_type='DEDUCT_WITHDRAW', reference_id='withdrawal_request')
                WithdrawalRequest.objects.create(
                    user=request.user, amount=amount, upi_id=upi_id
                )
                messages.success(request, f"Withdrawal request for ₹{amount} submitted successfully! We will process it within 24 hours.")
        except Exception:
            messages.error(request, "Invalid amount.")
            
    return redirect('core:earnings')
