from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from core.hometutor_data import PILOT_CITY

from .forms import (
    DemoAcceptForm,
    DemoDeclineForm,
    EngagementChatMessageForm,
    EngagementDisputeForm,
    EngagementReviewForm,
    DemoRequestForm,
    SessionAttendanceForm,
    TutorDocumentForm,
    TutorProfileForm,
)
from hometutor_payments.models import MarketplaceOrder

from .models import DemoRequest, EngagementReview, SessionAttendance, TutorEngagement, TutorProfile
from .services import (
    attach_demo_status_to_cards,
    apply_engagement_confirm,
    ensure_engagement,
    get_tutor_profile,
    notify_demo_request_created,
    notify_demo_resolved_for_requester,
    notify_engagement_confirm,
    masked_email,
    masked_phone,
    public_tutor_queryset,
    tutor_to_card_dict,
)


def _tutor_filter_context(request):
    return {
        'filter_q': request.GET.get('q', ''),
        'filter_subject': request.GET.get('subject', ''),
        'filter_mode': request.GET.get('mode', ''),
        'filter_language': request.GET.get('language', ''),
        'filter_area': request.GET.get('area', ''),
        'filter_city': request.GET.get('city', '') or PILOT_CITY,
        'filter_class_min': request.GET.get('class_min', ''),
        'filter_pincode': request.GET.get('pincode', ''),
        'filter_radius_km': request.GET.get('radius_km', ''),
    }


def tutor_list(request):
    tutors = public_tutor_queryset(request.GET)
    cards = [tutor_to_card_dict(t, PILOT_CITY) for t in tutors]
    cards = attach_demo_status_to_cards(cards, request.user)
    return render(
        request,
        'hometutor/list.jinja',
        {
            'tutor_cards': cards,
            'hometutor_pilot_city': PILOT_CITY,
            **_tutor_filter_context(request),
        },
    )


def quick_tutor_search(request):
    """HTMX endpoint for lightweight dashboard tutor search."""
    tutors = public_tutor_queryset(request.GET)[:6]
    cards = [tutor_to_card_dict(t, PILOT_CITY) for t in tutors]
    cards = attach_demo_status_to_cards(cards, request.user)
    return render(
        request,
        'hometutor/partials/_tutor_search_results.jinja',
        {
            'tutor_cards': cards,
            'hometutor_pilot_city': PILOT_CITY,
            'enable_compare': True,
            'dashboard_mode': True,
            'parent_gate_enabled': request.GET.get('parent_gate') == '1',
            **_tutor_filter_context(request),
        },
    )


def compare_tutors(request):
    """Compare up to 3 tutor profiles side by side."""
    slugs = [s.strip() for s in request.GET.getlist('t') if s.strip()]
    # Preserve order from query string and cap list size.
    ordered_slugs = []
    for slug in slugs:
        if slug not in ordered_slugs:
            ordered_slugs.append(slug)
        if len(ordered_slugs) >= 3:
            break

    profiles = list(
        TutorProfile.objects.filter(
            slug__in=ordered_slugs,
            verification_status=TutorProfile.VerificationStatus.APPROVED,
        )
    )
    profile_map = {p.slug: p for p in profiles}
    ordered_profiles = [profile_map[s] for s in ordered_slugs if s in profile_map]
    tutor_cards = [tutor_to_card_dict(p, PILOT_CITY) for p in ordered_profiles]
    tutor_cards = attach_demo_status_to_cards(tutor_cards, request.user)

    return render(
        request,
        'hometutor/compare.jinja',
        {
            'tutor_cards': tutor_cards,
            'selected_count': len(tutor_cards),
            'hometutor_pilot_city': PILOT_CITY,
        },
    )


def tutor_detail(request, slug):
    profile = TutorProfile.objects.filter(slug=slug).first()
    if not profile:
        raise Http404()
    viewer_owner = (
        request.user.is_authenticated
        and profile.user_id
        and profile.user_id == request.user.id
    )
    staff_ok = request.user.is_authenticated and request.user.is_staff
    public_ok = profile.verification_status == TutorProfile.VerificationStatus.APPROVED
    if not public_ok and not viewer_owner and not staff_ok:
        raise Http404()

    demo_form = None
    can_request_demo = (
        request.user.is_authenticated
        and profile.user_id
        and profile.user_id != request.user.id
        and public_ok
    )
    if can_request_demo:
        demo_form = DemoRequestForm()

    return render(
        request,
        'hometutor/detail.jinja',
        {
            't': profile,
            'hometutor_pilot_city': PILOT_CITY,
            'viewer_is_owner': viewer_owner,
            'demo_form': demo_form,
            'can_request_demo': can_request_demo,
        },
    )


@login_required
@require_http_methods(['POST'])
def demo_request_create(request, slug):
    profile = get_object_or_404(
        TutorProfile,
        slug=slug,
        verification_status=TutorProfile.VerificationStatus.APPROVED,
    )
    if not profile.user_id or profile.user_id == request.user.id:
        raise Http404()
    form = DemoRequestForm(request.POST)
    form._tutor = profile
    form._requester = request.user
    if form.is_valid():
        demo = form.save(commit=False)
        demo.tutor = profile
        demo.requester = request.user
        demo.status = DemoRequest.Status.PENDING
        demo.save()
        notify_demo_request_created(demo)
        messages.success(
            request,
            'Request a free demo submitted successfully. The tutor will receive your message in RankJee inbox.',
        )
    else:
        for err in form.non_field_errors():
            messages.error(request, err)
        for field, errs in form.errors.items():
            if field != '__all__':
                for e in errs:
                    messages.error(request, f'{field}: {e}')
    return redirect('hometutor:tutor_detail', slug=slug)


@login_required
def tutor_profile_edit(request):
    profile = get_tutor_profile(request.user)
    initial = {}
    if not profile:
        initial = {
            'display_name': (request.user.get_full_name() or '').strip() or request.user.username,
            'city': PILOT_CITY,
        }

    if request.method == 'POST':
        action = request.POST.get('action', 'submit_review')
        submit_for_review = action != 'save_draft'
        form = TutorProfileForm(request.POST, instance=profile)
        doc_form = TutorDocumentForm(request.POST, request.FILES, prefix='doc')
        if form.is_valid():
            obj = form.save(commit=False, user=request.user, submit_for_review=submit_for_review)
            obj.save()
            if doc_form.is_valid():
                if doc_form.cleaned_data.get('file'):
                    doc = doc_form.save(commit=False)
                    doc.tutor = obj
                    doc.save()
            else:
                messages.error(request, 'Please fix the optional document fields or clear them.')
                return render(
                    request,
                    'hometutor/tutor_profile.jinja',
                    {
                        'form': form,
                        'doc_form': doc_form,
                        'profile': obj,
                        'hometutor_pilot_city': PILOT_CITY,
                    },
                )
            verb = 'saved as draft' if action == 'save_draft' else 'submitted for review'
            messages.success(request, f'Profile {verb}.')
            return redirect('hometutor:my_profile')
    else:
        form = TutorProfileForm(instance=profile, initial=initial if not profile else None)
        doc_form = TutorDocumentForm(prefix='doc')

    profile = get_tutor_profile(request.user)
    return render(
        request,
        'hometutor/tutor_profile.jinja',
        {
            'form': form,
            'doc_form': doc_form,
            'profile': profile,
            'hometutor_pilot_city': PILOT_CITY,
        },
    )


@login_required
def tutor_incoming_demos(request):
    profile = get_tutor_profile(request.user)
    if not profile:
        messages.info(request, 'Create your tutor listing first.')
        return redirect('hometutor:my_profile')

    pending = profile.demo_requests.filter(status=DemoRequest.Status.PENDING).select_related(
        'requester',
    )
    pending_rows = []
    for d in pending:
        requester_email_masked = masked_email(d.requester.email or '')
        requester_phone_masked = masked_phone(d.contact_phone or '')
        pending_rows.append(
            {
                'demo': d,
                'requester_email_masked': requester_email_masked,
                'requester_phone_masked': requester_phone_masked,
                'accept_form': DemoAcceptForm(prefix=f'acc{d.pk}'),
                'decline_form': DemoDeclineForm(prefix=f'dec{d.pk}'),
            }
        )
    other = list(
        profile.demo_requests.exclude(status=DemoRequest.Status.PENDING)
        .select_related('requester', 'engagement')
        .order_by('-updated_at')[:50]
    )
    for d in other:
        if d.status == DemoRequest.Status.ACCEPTED:
            ensure_engagement(d)
    if other:
        refreshed = {
            x.pk: x
            for x in DemoRequest.objects.filter(pk__in=[d.pk for d in other]).select_related(
                'requester',
                'engagement',
            )
        }
        other = [refreshed[d.pk] for d in other]
    return render(
        request,
        'hometutor/tutor_demos.jinja',
        {
            'profile': profile,
            'pending_rows': pending_rows,
            'recent': other,
            'hometutor_pilot_city': PILOT_CITY,
        },
    )


@login_required
def my_demo_requests(request):
    demos = list(
        DemoRequest.objects.filter(requester=request.user)
        .select_related('tutor', 'engagement')
        .order_by('-created_at')[:100]
    )
    for d in demos:
        if d.status == DemoRequest.Status.ACCEPTED:
            ensure_engagement(d)
    if demos:
        refreshed = {
            x.pk: x
            for x in DemoRequest.objects.filter(pk__in=[d.pk for d in demos]).select_related(
                'tutor',
                'engagement',
            )
        }
        demos = [refreshed[d.pk] for d in demos]
    for d in demos:
        d.marketplace_paid = False
        d.engagement_pay_id = None
        if d.status != DemoRequest.Status.ACCEPTED:
            continue
        try:
            eng = d.engagement
        except ObjectDoesNotExist:
            continue
        if eng.status != TutorEngagement.Status.ACTIVE:
            continue
        d.engagement_pay_id = eng.pk
        mo = MarketplaceOrder.objects.filter(engagement_id=eng.pk).first()
        d.marketplace_paid = bool(mo and mo.status == MarketplaceOrder.Status.SUCCESS)
    return render(
        request,
        'hometutor/my_demo_requests.jinja',
        {
            'demos': demos,
            'hometutor_pilot_city': PILOT_CITY,
        },
    )


@login_required
@require_http_methods(['POST'])
def demo_accept(request, pk):
    demo = get_object_or_404(
        DemoRequest.objects.select_related('tutor'),
        pk=pk,
        status=DemoRequest.Status.PENDING,
    )
    if not demo.tutor.user_id or demo.tutor.user_id != request.user.id:
        raise Http404()
    form = DemoAcceptForm(request.POST, prefix=f'acc{pk}')
    if form.is_valid():
        dt = form.cleaned_data['scheduled_at']
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        demo.scheduled_at = dt
        demo.status = DemoRequest.Status.ACCEPTED
        demo.decline_reason = ''
        demo.demo_reminder_sent_at = None
        demo.save(
            update_fields=[
                'scheduled_at',
                'status',
                'decline_reason',
                'demo_reminder_sent_at',
                'updated_at',
            ]
        )
        ensure_engagement(demo)
        notify_demo_resolved_for_requester(demo)
        messages.success(request, 'Demo accepted — parent/student was notified.')
    else:
        messages.error(request, 'Choose a valid date and time for the demo.')
    return redirect('hometutor:tutor_demos')


@login_required
@require_http_methods(['POST'])
def demo_decline(request, pk):
    demo = get_object_or_404(
        DemoRequest.objects.select_related('tutor'),
        pk=pk,
        status=DemoRequest.Status.PENDING,
    )
    if not demo.tutor.user_id or demo.tutor.user_id != request.user.id:
        raise Http404()
    form = DemoDeclineForm(request.POST, prefix=f'dec{pk}')
    reason = ''
    if form.is_valid():
        reason = (form.cleaned_data.get('decline_reason') or '').strip()
    demo.status = DemoRequest.Status.DECLINED
    demo.decline_reason = reason
    demo.scheduled_at = None
    demo.save(update_fields=['status', 'decline_reason', 'scheduled_at', 'updated_at'])
    notify_demo_resolved_for_requester(demo)
    messages.success(request, 'Demo request declined.')
    return redirect('hometutor:tutor_demos')


@login_required
@require_http_methods(['POST'])
def demo_cancel(request, pk):
    demo = get_object_or_404(DemoRequest, pk=pk, requester=request.user)
    if demo.status != DemoRequest.Status.PENDING:
        messages.error(request, 'Only pending requests can be cancelled.')
        return redirect('hometutor:my_demo_requests')
    demo.status = DemoRequest.Status.CANCELLED
    demo.save(update_fields=['status', 'updated_at'])
    TutorEngagement.objects.filter(demo_request=demo).update(status=TutorEngagement.Status.CLOSED)
    messages.success(request, 'Demo request cancelled.')
    return redirect('hometutor:my_demo_requests')


@login_required
@require_http_methods(['POST'])
def demo_confirm_parent(request, pk):
    demo = get_object_or_404(
        DemoRequest.objects.select_related('tutor', 'engagement'),
        pk=pk,
        requester=request.user,
        status=DemoRequest.Status.ACCEPTED,
    )
    eng = ensure_engagement(demo)
    mutual_just, side_ok = apply_engagement_confirm(eng, as_parent=True)
    if not side_ok:
        messages.info(request, 'You already confirmed this demo time.')
        return redirect('hometutor:my_demo_requests')
    notify_engagement_confirm(eng, as_parent=True, just_completed=mutual_just)
    messages.success(
        request,
        'Thanks — both sides must confirm before the demo is locked in.'
        if not mutual_just
        else 'Demo is fully confirmed on both sides.',
    )
    return redirect('hometutor:my_demo_requests')


@login_required
@require_http_methods(['POST'])
def demo_confirm_tutor(request, pk):
    demo = get_object_or_404(
        DemoRequest.objects.select_related('tutor', 'tutor__user', 'engagement'),
        pk=pk,
        status=DemoRequest.Status.ACCEPTED,
    )
    if not demo.tutor.user_id or demo.tutor.user_id != request.user.id:
        raise Http404()
    eng = ensure_engagement(demo)
    mutual_just, side_ok = apply_engagement_confirm(eng, as_parent=False)
    if not side_ok:
        messages.info(request, 'You already confirmed this demo time.')
        return redirect('hometutor:tutor_demos')
    notify_engagement_confirm(eng, as_parent=False, just_completed=mutual_just)
    messages.success(
        request,
        'Recorded.'
        if not mutual_just
        else 'Demo is fully confirmed on both sides.',
    )
    return redirect('hometutor:tutor_demos')


@login_required
def engagement_room(request, pk):
    eng = get_object_or_404(
        TutorEngagement.objects.select_related('demo_request', 'tutor_profile', 'tutor_profile__user', 'student'),
        pk=pk,
    )
    is_requester = eng.student_id == request.user.id
    is_tutor = eng.tutor_profile.user_id == request.user.id if eng.tutor_profile.user_id else False
    if not (is_requester or is_tutor or request.user.is_staff):
        raise Http404()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_session':
            if not is_tutor:
                raise Http404()
            session_form = SessionAttendanceForm(request.POST, prefix='session')
            if session_form.is_valid():
                obj = session_form.save(commit=False)
                obj.engagement = eng
                obj.marked_by = request.user
                obj.save()
                messages.success(request, 'Session attendance logged.')
                return redirect('hometutor:engagement_room', pk=eng.pk)
            messages.error(request, 'Please fix session attendance fields.')
        elif action == 'submit_review':
            if not is_requester:
                raise Http404()
            if eng.status != TutorEngagement.Status.ACTIVE:
                messages.error(request, 'Review is available only for active engagements.')
                return redirect('hometutor:engagement_room', pk=eng.pk)
            review_form = EngagementReviewForm(request.POST, prefix='review')
            if review_form.is_valid():
                review, created = EngagementReview.objects.get_or_create(
                    engagement=eng,
                    defaults={
                        'reviewer': request.user,
                        'tutor_profile': eng.tutor_profile,
                        'rating': review_form.cleaned_data['rating'],
                        'comment': review_form.cleaned_data['comment'],
                    },
                )
                if not created:
                    review.rating = review_form.cleaned_data['rating']
                    review.comment = review_form.cleaned_data['comment']
                    review.save(update_fields=['rating', 'comment'])
                messages.success(request, 'Review saved.')
                return redirect('hometutor:engagement_room', pk=eng.pk)
            messages.error(request, 'Please fix review fields.')
        elif action == 'send_message':
            chat_form = EngagementChatMessageForm(request.POST, prefix='chat')
            if chat_form.is_valid():
                msg = chat_form.save(commit=False)
                msg.engagement = eng
                msg.sender = request.user
                msg.save()
                messages.success(request, 'Message sent.')
                return redirect('hometutor:engagement_room', pk=eng.pk)
            messages.error(request, 'Please type a valid message.')
        elif action == 'raise_dispute':
            dispute_form = EngagementDisputeForm(request.POST, prefix='dispute')
            if dispute_form.is_valid():
                item = dispute_form.save(commit=False)
                item.engagement = eng
                item.raised_by = request.user
                item.save()
                messages.success(request, 'Dispute submitted. Admin team will review it.')
                return redirect('hometutor:engagement_room', pk=eng.pk)
            messages.error(request, 'Please provide dispute details.')

    session_form = SessionAttendanceForm(prefix='session')
    review_form = EngagementReviewForm(prefix='review')
    chat_form = EngagementChatMessageForm(prefix='chat')
    dispute_form = EngagementDisputeForm(prefix='dispute')
    sessions = eng.sessions.all()[:50]
    chat_messages = eng.chat_messages.select_related('sender').all()[:100]
    disputes = eng.disputes.select_related('raised_by').all()[:20]
    review = getattr(eng, 'review', None)
    return render(
        request,
        'hometutor/engagement_room.jinja',
        {
            'engagement': eng,
            'is_requester': is_requester,
            'is_tutor': is_tutor,
            'session_form': session_form,
            'review_form': review_form,
            'chat_form': chat_form,
            'dispute_form': dispute_form,
            'sessions': sessions,
            'chat_messages': chat_messages,
            'disputes': disputes,
            'review': review,
        },
    )
