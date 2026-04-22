from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponse
from django.conf import settings
from django.urls import reverse
from .models import Course, CourseReferral, EarningTask, UserTaskSubmission
from assessment.models import UserAttempt
from django.utils import timezone
from assessment.models import DailyJackpot

from hometutor.services import featured_home_tutors

from .hometutor_data import PILOT_CITY


def privacy(request):
    return render(request, 'core/privacy.jinja')


def terms(request):
    return render(request, 'core/terms.jinja')


def service_worker(request):
    # Return an empty service worker to silence stale browser registrations.
    return HttpResponse(
        "self.addEventListener('install', () => self.skipWaiting());"
        "self.addEventListener('activate', () => self.clients.claim());",
        content_type='application/javascript',
    )


def robots_txt(request):
    sitemap_url = f"{settings.SITE_BASE_URL}/sitemap.xml"
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /sd/\n"
        "Disallow: /admin/\n"
        "Disallow: /accounts/\n"
        "Sitemap: " + sitemap_url + "\n"
    )
    return HttpResponse(body, content_type="text/plain")


def home(request):
    now = timezone.now()
    jackpot = DailyJackpot.objects.filter(is_active=True, is_completed=False).order_by('scheduled_time').first()
    time_to_go = int((jackpot.scheduled_time - now).total_seconds()) if jackpot else 0
    featured_rows, featured_from_db = featured_home_tutors()
    return render(request, 'core/home.jinja', {
        'jackpot': jackpot,
        'jackpot_time_to_go': time_to_go,
        'featured_home_tutors': featured_rows,
        'featured_tutors_from_db': featured_from_db,
        'hometutor_pilot_city': PILOT_CITY,
        'seo_title': "RankJee - Home Tutors, Courses and Mock Tests",
        'seo_description': "Find trusted home tutors, explore job-ready courses, and practice with mock tests on RankJee.",
    })


def courses(request):
    ref_code = (request.GET.get("ref") or "").strip().upper()
    if ref_code:
        request.session["pending_course_referrer_code"] = ref_code
    courses_qs = Course.objects.filter(is_active=True).order_by("-is_featured", "title")
    return render(
        request,
        "core/courses.jinja",
        {
            "courses": courses_qs,
            "seo_title": "Courses - Upskill Faster with RankJee",
            "seo_description": "Explore practical courses with outcomes, duration, and pricing to accelerate your career.",
            "canonical_url": request.build_absolute_uri(request.path),
            "seo_noindex": bool(ref_code),
        },
    )


def course_detail(request, slug):
    ref_code = (request.GET.get("ref") or "").strip().upper()
    if ref_code:
        request.session["pending_course_referrer_code"] = ref_code
    pending_ref = request.session.get("pending_course_referrer_code", "")
    course = get_object_or_404(Course, slug=slug, is_active=True)

    if request.method == "POST":
        lead_name = (request.POST.get("lead_name") or "").strip()[:120]
        lead_email = (request.POST.get("lead_email") or "").strip().lower()
        if not lead_email:
            messages.error(request, "Please enter your email.")
            return redirect("core:course_detail", slug=course.slug)

        referrer = None
        if pending_ref:
            referrer = get_user_model().objects.filter(referral_code=pending_ref).first()
        if not referrer:
            messages.error(request, "Referral code missing/invalid. Use a referral link from Earn page.")
            return redirect("core:course_detail", slug=course.slug)
        if request.user.is_authenticated and referrer.id == request.user.id:
            messages.error(request, "You cannot refer yourself.")
            return redirect("core:course_detail", slug=course.slug)

        lead_user = request.user if request.user.is_authenticated else None
        referral, created = CourseReferral.objects.get_or_create(
            course=course,
            referrer=referrer,
            lead_email=lead_email,
            defaults={
                "lead_name": lead_name,
                "lead_user": lead_user,
                "status": CourseReferral.Status.PENDING,
                "sale_amount": course.price_inr,
            },
        )
        if not created:
            referral.lead_name = lead_name or referral.lead_name
            referral.lead_user = lead_user or referral.lead_user
            if not referral.sale_amount:
                referral.sale_amount = course.price_inr
            referral.save(update_fields=["lead_name", "lead_user", "sale_amount"])
        messages.success(
            request,
            "Enrollment interest recorded. On successful conversion, 30% referral commission is credited.",
        )
        return redirect("core:course_detail", slug=course.slug)

    return render(
        request,
        "core/course_detail.jinja",
        {
            "course": course,
            "pending_course_referrer_code": pending_ref,
            "seo_title": f"{course.title} - Course Details | RankJee",
            "seo_description": (course.short_description or course.description or "Explore this course on RankJee.")[:155],
            "canonical_url": request.build_absolute_uri(request.path),
            "seo_noindex": bool(ref_code),
        },
    )


def course_city_landing(request, slug, city_slug):
    course = get_object_or_404(Course, slug=slug, is_active=True)
    city = (city_slug or "").replace("-", " ").strip().title()
    if not city:
        city = PILOT_CITY

    seo_title = f"{course.title} Course in {city} | RankJee"
    seo_description = (
        f"Join the {course.title} course in {city}. "
        f"Duration: {course.duration_weeks} weeks. "
        "Compare outcomes, pricing, and register your interest on RankJee."
    )[:160]

    faq_items = [
        {
            "q": f"Is {course.title} available for students in {city}?",
            "a": "Yes, learners in this city can register interest and start the course through RankJee.",
        },
        {
            "q": "Do I get mentor support and structured learning?",
            "a": "Yes, course flow is designed with structured milestones and support to improve outcomes.",
        },
        {
            "q": "How do I enroll quickly?",
            "a": "Use the enrollment form on this page. Our team will contact you with next steps.",
        },
    ]

    top_cities = ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Mumbai", "Delhi", "Pune", "Bangalore"]
    related_cities = [c for c in top_cities if c.lower() != city.lower()][:6]

    return render(
        request,
        "core/course_city_landing.jinja",
        {
            "course": course,
            "city_label": city,
            "related_cities": related_cities,
            "faq_items": faq_items,
            "seo_title": seo_title,
            "seo_description": seo_description,
            "canonical_url": request.build_absolute_uri(
                reverse("core:course_city_landing", kwargs={"slug": course.slug, "city_slug": city_slug})
            ),
        },
    )


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
    active_courses = Course.objects.filter(is_active=True).order_by("-is_featured", "title")
    course_ref_links = {}
    if getattr(user, "referral_code", ""):
        for c in active_courses:
            course_ref_links[c.id] = (
                f"{scheme}://{site_domain}/courses/{c.slug}/?ref={user.referral_code}"
            )
    
    return render(request, 'core/earnings.jinja', {
        'referrals': referrals,
        'referral_count': referral_count,
        'referral_link': referral_link,
        'total_earned': total_earned,
        'transactions': wallet_transactions,
        'withdrawals': withdrawals,
        'active_courses': active_courses,
        'course_ref_links': course_ref_links,
        'seo_noindex': True,
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
                # Gamification runs via core.signals post_save (idempotent in on_task_approved)
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
    return render(request, 'core/watch_ads.jinja', {'seo_noindex': True})


@login_required
def claim_ad_reward(request):
    if request.method == 'POST':
        now = timezone.now()
        if request.user.last_ad_claim_at:
            elapsed = (now - request.user.last_ad_claim_at).total_seconds()
            if elapsed < 30:
                messages.warning(request, "Please wait for the ad to finish before claiming.")
                return redirect('core:watch_ads')

        reward_amount = 0.50
        request.user.add_wallet(reward_amount, transaction_type='OTHER', reference_id='ad_watch')
        request.user.last_ad_claim_at = now
        request.user.save(update_fields=['last_ad_claim_at'])
        messages.success(request, f"🎉 Success! ₹{reward_amount} added to your wallet.")

    return redirect('core:watch_ads')


@login_required
def request_withdrawal(request):
    if request.method == 'POST':
        if not cache.add(f"rl:withdraw:{request.user.id}", 1, 20):
            messages.error(request, "Please wait a few seconds before submitting again.")
            return redirect('core:earnings')
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
