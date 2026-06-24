from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.contrib import messages
from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.conf import settings
from django.urls import reverse
from decimal import Decimal
from urllib.parse import quote
import re
from allauth.socialaccount.models import SocialAccount
from .forms import TutorLeadRequestForm
from .models import Course, CourseReferral, CoursePurchase, EarningTask, LegalPage, TutorLeadRequest, UserTaskSubmission
from .course_content import (
    format_bold_markers,
    resolve_course_includes,
    resolve_gain_outcomes,
    resolve_gain_perks,
    resolve_hero_usps,
)
from .services_course_checkout import (
    REFERRAL_COMMISSION_PERCENT_DEFAULT,
    REFERRAL_LEAD_DISCOUNT_PERCENT,
    expected_referral_sale_amount_inr,
    unit_checkout_price_inr,
    user_owned_course_ids,
)
from assessment.models import UserAttempt
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe
from assessment.models import DailyJackpot

from hometutor.services import featured_home_tutors

from .hometutor_data import PILOT_CITY, SHORT_LINK_CITY_SLUGS

try:
    from markdown import markdown as md_markdown
except ModuleNotFoundError:  # pragma: no cover - defensive fallback
    md_markdown = None


_LEGAL_PAGE_FALLBACKS = {
    "terms-and-conditions": {
        "title": "Terms and Conditions",
        "content": (
            "Welcome to RankJee.\n\n"
            "By using our website, tutor marketplace, exam tools, courses, and earning features, "
            "you agree to these Terms and Conditions.\n\n"
            "1) Eligibility and account use\n"
            "- You must provide accurate information at signup.\n"
            "- You are responsible for account activity and credential security.\n"
            "- We may suspend accounts for fraud, abuse, or policy violations.\n\n"
            "2) Platform scope\n"
            "- RankJee connects learners with tutors and learning resources.\n"
            "- Learning outcomes depend on user effort and tutor performance.\n"
            "- We may update products, pricing, and features without prior notice.\n\n"
            "3) Payments and pricing\n"
            "- Listed prices are in INR unless stated otherwise.\n"
            "- Paid features are activated after successful payment verification.\n"
            "- Taxes/charges (if applicable) may be included or shown at checkout.\n\n"
            "4) Acceptable use\n"
            "- Do not submit illegal, abusive, or misleading content.\n"
            "- Do not scrape, reverse engineer, or misuse platform data.\n\n"
            "5) Liability\n"
            "- Services are provided on an 'as available' basis.\n"
            "- RankJee is not liable for indirect or consequential losses.\n\n"
            "6) Contact\n"
            "For policy or legal queries, use the Contact Us page."
        ),
    },
    "privacy-policy": {
        "title": "Privacy Policy",
        "content": (
            "RankJee values your privacy.\n\n"
            "1) Data we collect\n"
            "- Account details: name, email, phone (if provided), login metadata.\n"
            "- Usage data: pages visited, activity logs, learning interactions.\n"
            "- Transaction data for paid features and payouts.\n\n"
            "2) How we use data\n"
            "- Deliver core features (tutors, courses, tests, dashboard).\n"
            "- Improve product quality, security, and support.\n"
            "- Process payments, withdrawals, and compliance obligations.\n\n"
            "3) Data sharing\n"
            "- With trusted service providers (payment, hosting, email, analytics) as needed.\n"
            "- With legal authorities when required by law.\n"
            "- We do not sell personal data.\n\n"
            "4) Data protection\n"
            "- We apply reasonable technical and operational safeguards.\n"
            "- Users should protect account passwords and device access.\n\n"
            "5) Retention and rights\n"
            "- We keep data as needed for service delivery and legal compliance.\n"
            "- You may request account/data actions by contacting support."
        ),
    },
    "cancellation-and-refund": {
        "title": "Cancellation and Refund",
        "content": (
            "This policy applies to digital services on RankJee.\n\n"
            "1) Order cancellation\n"
            "- If payment is not successful, no charge is captured.\n"
            "- If payment is successful and access is granted, cancellation may not be available.\n\n"
            "2) Refund eligibility\n"
            "- Duplicate/accidental charges are eligible after verification.\n"
            "- Technical failures where service is not delivered may be eligible.\n"
            "- Misuse or policy-violating transactions are not refundable.\n\n"
            "3) Refund process\n"
            "- Raise a support request with payment reference and account email.\n"
            "- Verified refunds are processed to the original payment method.\n"
            "- Processing timelines depend on payment provider/bank cycles.\n\n"
            "4) Non-refundable items\n"
            "- Consumed digital content and completed service milestones."
        ),
    },
    "shipping-and-exchange": {
        "title": "Shipping and Exchange",
        "content": (
            "RankJee primarily delivers digital services.\n\n"
            "1) Shipping\n"
            "- No physical shipping is applicable for most products.\n"
            "- Digital access is provided to your account after payment verification.\n\n"
            "2) Delivery timelines\n"
            "- Access is usually instant, subject to payment confirmation and system checks.\n"
            "- In rare cases, activation may take additional time.\n\n"
            "3) Exchange\n"
            "- Digital services are generally non-exchangeable.\n"
            "- If a wrong plan/course is purchased due to a platform error, contact support for review."
        ),
    },
    "contact-us": {
        "title": "Contact Us",
        "content": (
            "Need help? We are here for you.\n\n"
            "Support scope:\n"
            "- Account and login issues\n"
            "- Payment and billing queries\n"
            "- Tutor request and engagement support\n"
            "- Course and exam feature assistance\n\n"
            "Please share:\n"
            "- Registered email/username\n"
            "- Problem summary and screenshots (if any)\n"
            "- Payment reference/order id for billing issues\n\n"
            "You can also use in-app support links where available for faster resolution."
        ),
    },
}


def _render_legal_page(request, slug: str):
    page = LegalPage.objects.filter(slug=slug, is_published=True).first()
    fallback = _LEGAL_PAGE_FALLBACKS[slug]
    title = page.title if page else fallback["title"]
    body = page.content if page else fallback["content"]
    seo_title = (page.seo_title if page else "") or f"{title} | RankJee"
    seo_description = (page.seo_description if page else "") or (body[:155] if body else title)
    return render(
        request,
        "core/legal_page.jinja",
        {
            "legal_page_title": title,
            "legal_page_content": body,
            "seo_title": seo_title,
            "seo_description": seo_description,
            "canonical_url": request.build_absolute_uri(request.path),
        },
    )


def privacy(request):
    return _render_legal_page(request, "privacy-policy")


def terms(request):
    return _render_legal_page(request, "terms-and-conditions")


def cancellation_refund(request):
    return _render_legal_page(request, "cancellation-and-refund")


def shipping_exchange(request):
    return _render_legal_page(request, "shipping-and-exchange")


def contact_us(request):
    return _render_legal_page(request, "contact-us")


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
        "Disallow: /study/\n"
        "Sitemap: " + sitemap_url + "\n"
    )
    return HttpResponse(body, content_type="text/plain")


def city_tutor_redirect(request, city_slug):
    """
    Keep short city URLs SEO-friendly by resolving to the canonical tutor city landing.
    Example: /surat -> /hometutor/city/surat/
    Unknown slugs (e.g. /earn/) are rejected so they do not hijack product URLs.
    """
    from django.utils.text import slugify
    from hometutor.models import TutorProfile

    canonical = slugify(city_slug)
    if canonical not in SHORT_LINK_CITY_SLUGS:
        city_label = " ".join(part.capitalize() for part in canonical.replace("-", " ").split())
        if not city_label:
            raise Http404()
        exists = TutorProfile.objects.filter(
            verification_status=TutorProfile.VerificationStatus.APPROVED,
            city__iexact=city_label,
        ).exists()
        if not exists:
            raise Http404()
    return redirect("hometutor:tutor_city_landing", city_slug=canonical, permanent=True)


def favicon(request):
    """Avoid noisy /favicon.ico 404s without requiring static deploy of an .ico file."""
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        b'<rect width="32" height="32" rx="6" fill="#3b4cb8"/>'
        b'<text x="16" y="22" text-anchor="middle" fill="#fff" '
        b'font-family="system-ui,sans-serif" font-size="17" font-weight="800">R</text>'
        b"</svg>"
    )
    return HttpResponse(svg, content_type="image/svg+xml")


def handler404(request, exception):
    """Send unknown URLs to home (used when DEBUG is False)."""
    return redirect("core:home")


def home(request):
    now = timezone.now()
    jackpot = DailyJackpot.objects.filter(is_active=True, is_completed=False).order_by('scheduled_time').first()
    time_to_go = int((jackpot.scheduled_time - now).total_seconds()) if jackpot else 0

    # Cache featured tutors for 5 minutes — they change rarely, hit on every home load
    _cache_key = f"home_featured_tutors_{PILOT_CITY}"
    _cached = cache.get(_cache_key)
    if _cached is None:
        featured_rows, featured_from_db = featured_home_tutors()
        cache.set(_cache_key, (featured_rows, featured_from_db), timeout=300)
    else:
        featured_rows, featured_from_db = _cached

    city = PILOT_CITY
    seo_title = f"Get Home Tutors Jobs in {city} | Find Best Home Tutor in {city} | RankJee"
    seo_description = (
        f"Get home tutors jobs in {city}. Find the best home tutor in {city} — verified profiles, "
        "demo requests, and coaching-grade support on RankJee."
    )[:160]
    seo_keywords = (
        f"home tutor jobs {city}, best home tutor {city}, home tutor near me {city}, "
        "private tutor, tuition at home, RankJee"
    )
    return render(request, 'core/home.jinja', {
        'jackpot': jackpot,
        'jackpot_time_to_go': time_to_go,
        'featured_home_tutors': featured_rows,
        'featured_tutors_from_db': featured_from_db,
        'hometutor_pilot_city': PILOT_CITY,
        'seo_title': seo_title,
        'seo_description': seo_description,
        'seo_keywords': seo_keywords,
        'canonical_url': request.build_absolute_uri(request.path),
    })


def request_tutor(request):
    next_url = request.build_absolute_uri(reverse("core:request_tutor"))
    google_login_url = f"/accounts/google/login/?process=login&next={next_url}"

    if not request.user.is_authenticated:
        next_url = request.build_absolute_uri(reverse("core:request_tutor"))
        return render(
            request,
            "core/request_tutor_login_gate.jinja",
            {
                "google_login_url": google_login_url,
                "google_only_mode": True,
                "seo_title": "Login to Request a Tutor | RankJee",
                "seo_description": "Login with Google to submit your tutor requirement and prevent spam requests.",
                "canonical_url": request.build_absolute_uri(request.path),
            },
        )

    has_google_login = SocialAccount.objects.filter(user=request.user, provider="google").exists()
    if not has_google_login:
        messages.info(request, "For anti-spam protection, tutor requests require Google login.")
        return render(
            request,
            "core/request_tutor_login_gate.jinja",
            {
                "google_login_url": google_login_url,
                "google_only_mode": True,
                "seo_title": "Google Login Required | RankJee",
                "seo_description": "Connect or login with Google to submit tutor requirements and reduce spam.",
                "canonical_url": request.build_absolute_uri(request.path),
            },
        )

    initial = {"city": PILOT_CITY}
    role = getattr(request.user, "role", "")
    if role == "PARENT":
        initial["requester_type"] = TutorLeadRequest.RequesterType.PARENT
    else:
        initial["requester_type"] = TutorLeadRequest.RequesterType.STUDENT
    initial["full_name"] = (request.user.get_full_name() or "").strip() or request.user.username
    initial["email"] = request.user.email or ""

    if request.method == "POST":
        form = TutorLeadRequestForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.requester = request.user
            item.save()
            messages.success(request, "Your tutor request was submitted. Our team will contact you shortly.")
            return redirect(f"{reverse('core:request_tutor')}?submitted=1")
    else:
        form = TutorLeadRequestForm(initial=initial)

    return render(
        request,
        "core/request_tutor.jinja",
        {
            "form": form,
            "seo_title": "Request a Home Tutor | RankJee",
            "seo_description": "Submit your tutor requirement and get matched with verified home tutors quickly.",
            "canonical_url": request.build_absolute_uri(request.path),
        },
    )


def courses(request):
    ref_code = (request.GET.get("ref") or "").strip().upper()
    if ref_code:
        request.session["pending_course_referrer_code"] = ref_code
    # Cache active courses for 10 minutes — catalogue changes infrequently
    courses_qs = cache.get("active_courses_qs")
    if courses_qs is None:
        courses_qs = list(Course.objects.filter(is_active=True).order_by("-is_featured", "title"))
        cache.set("active_courses_qs", courses_qs, timeout=600)
    purchased_ids = (
        user_owned_course_ids(request.user)
        if request.user.is_authenticated
        else set()
    )
    return render(
        request,
        "core/courses.jinja",
        {
            "courses": courses_qs,
            "course_purchased_ids": purchased_ids,
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
                "sale_amount": expected_referral_sale_amount_inr(course),
            },
        )
        if not created:
            referral.lead_name = lead_name or referral.lead_name
            referral.lead_user = lead_user or referral.lead_user
            if not referral.sale_amount:
                referral.sale_amount = expected_referral_sale_amount_inr(course)
            referral.save(update_fields=["lead_name", "lead_user", "sale_amount"])
        messages.success(
            request,
            "Enrollment recorded. You get 15% off at checkout on this course; your referrer earns "
            f"{REFERRAL_COMMISSION_PERCENT_DEFAULT:g}% on the amount you pay after a successful purchase.",
        )
        return redirect("core:course_detail", slug=course.slug)

    owns_course = False
    if request.user.is_authenticated:
        owns_course = CoursePurchase.objects.filter(user=request.user, course=course).exists()

    list_inr = course.price_inr if course.price_inr is not None else Decimal("0")
    checkout_inr = (
        unit_checkout_price_inr(course, request.user)
        if request.user.is_authenticated
        else list_inr
    )
    referral_price_unlocked = bool(request.user.is_authenticated and checkout_inr < list_inr)

    description_sections = []
    if course.description:
        markdown_source = course.description.replace("\r\n", "\n")
        section_re = re.compile(r"^\s*#{1,3}\s+(.+?)\s*$")
        sections_raw = []
        current_title = "Course details"
        current_lines = []

        for line in markdown_source.split("\n"):
            heading_match = section_re.match(line)
            if heading_match:
                text_chunk = "\n".join(current_lines).strip()
                if text_chunk:
                    sections_raw.append((current_title, text_chunk))
                current_title = heading_match.group(1).strip()
                current_lines = []
                continue
            current_lines.append(line)

        text_chunk = "\n".join(current_lines).strip()
        if text_chunk:
            sections_raw.append((current_title, text_chunk))

        if not sections_raw:
            sections_raw = [("Course details", markdown_source.strip())]

        for title, content_md in sections_raw:
            safe_source = escape(content_md)
            if md_markdown is not None:
                html = mark_safe(
                    md_markdown(
                        safe_source,
                        extensions=["extra", "nl2br", "sane_lists"],
                    )
                )
            else:
                html = mark_safe(safe_source.replace("\n", "<br>"))
            description_sections.append(
                {
                    "title": title,
                    "html": html,
                }
            )

    total_topics = sum(
        len(m.get("topics") or []) for m in (course.curriculum or [])
    )

    return render(
        request,
        "core/course_detail.jinja",
        {
            "course": course,
            "total_topics": total_topics,
            "hero_usps": resolve_hero_usps(course, total_topics),
            "gain_outcomes": resolve_gain_outcomes(course, total_topics),
            "gain_perks": resolve_gain_perks(course),
            "course_includes": resolve_course_includes(course),
            "format_bold_markers": format_bold_markers,
            "course_description_sections": description_sections,
            "owns_course": owns_course,
            "course_list_price_inr": list_inr,
            "course_checkout_price_inr": checkout_inr,
            "referral_price_unlocked": referral_price_unlocked,
            "referral_lead_discount_pct": REFERRAL_LEAD_DISCOUNT_PERCENT,
            "referral_commission_pct": REFERRAL_COMMISSION_PERCENT_DEFAULT,
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

    scheme = 'https' if request.is_secure() else 'http'
    site_domain = request.get_host()
    ref_code = (getattr(user, "referral_code", "") or "").strip()
    referral_code_ready = bool(ref_code)
    referral_link = (
        f"{scheme}://{site_domain}/users/signup/?ref={ref_code}" if ref_code else ""
    )

    total_earned = user.wallet_balance
    wallet_transactions = user.wallet_transactions.select_related("user").order_by("-created_at")[:20]
    # Reuse cached catalogue from courses view (10-min TTL)
    active_courses = cache.get("active_courses_qs")
    if active_courses is None:
        active_courses = list(Course.objects.filter(is_active=True).order_by("-is_featured", "title"))
        cache.set("active_courses_qs", active_courses, timeout=600)
    course_ref_links = {}
    courses_hub_ref_url = ""
    whatsapp_share_all_url = ""
    course_whatsapp_urls = {}
    if ref_code:
        courses_hub_ref_url = f"{scheme}://{site_domain}/courses/?ref={ref_code}"
        for c in active_courses:
            course_ref_links[c.id] = (
                f"{scheme}://{site_domain}/courses/{c.slug}/?ref={ref_code}"
            )
        _wa = lambda msg: "https://wa.me/?text=" + quote(msg, safe="")
        whatsapp_share_all_url = _wa(
            "Hi! I'm sharing RankJee courses with my referral link.\n\n"
            "You save *15%* at checkout when you enroll via my link and pay.\n\n"
            "Browse all courses with my code attached — pick one, tap Enroll now while logged in, then pay.\n\n"
            f"{courses_hub_ref_url}\n\n"
            "Ask me if you want a direct link to a specific course."
        )
        for c in active_courses:
            _link = course_ref_links[c.id]
            course_whatsapp_urls[c.id] = _wa(
                f"Hi! Here's a RankJee course I recommend:\n*{c.title}*\n\n"
                "Open the link, log in, tap Enroll now — you'll get *15% off* when you pay.\n\n"
                f"{_link}"
            )

    course_referrals = (
        user.course_referrals.select_related("course", "lead_user")
        .order_by("-created_at")[:80]
    )
    course_ref_agg = user.course_referrals.aggregate(
        pending_n=Count("id", filter=Q(status=CourseReferral.Status.PENDING)),
        success_n=Count("id", filter=Q(status=CourseReferral.Status.SUCCESS)),
        success_total=Sum("commission_amount", filter=Q(status=CourseReferral.Status.SUCCESS)),
    )
    course_commission_paid = course_ref_agg["success_total"] or 0

    return render(
        request,
        "core/earnings.jinja",
        {
            "referral_link": referral_link,
            "referral_code_ready": referral_code_ready,
            "total_earned": total_earned,
            "transactions": wallet_transactions,
            "active_courses": active_courses,
            "course_ref_links": course_ref_links,
            "courses_hub_ref_url": courses_hub_ref_url,
            "whatsapp_share_all_url": whatsapp_share_all_url,
            "course_whatsapp_urls": course_whatsapp_urls,
            "course_referrals": course_referrals,
            "course_ref_pending_n": course_ref_agg["pending_n"] or 0,
            "course_ref_success_n": course_ref_agg["success_n"] or 0,
            "course_commission_paid": course_commission_paid,
            "referral_lead_discount_pct": REFERRAL_LEAD_DISCOUNT_PERCENT,
            "referral_commission_pct": REFERRAL_COMMISSION_PERCENT_DEFAULT,
            "seo_noindex": True,
        },
    )


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
