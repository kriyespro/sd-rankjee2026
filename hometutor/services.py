"""Home tutor listing helpers (HT-1) + tutor utilities (HT-2)."""

import logging
from urllib.parse import quote_plus
from math import atan2, cos, radians, sin, sqrt

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from django.db.models import Avg, Count, Sum

from core.hometutor_data import FEATURED_HOME_TUTORS, LANDING_SUBJECTS, PILOT_CITY

from django.utils.text import slugify

from .models import DemoRequest, PincodeGeo, TutorEngagement, TutorProfile

logger = logging.getLogger('rankjee.hometutor')

TUTORS_PER_PAGE = 24


def crumb(label: str, url: str | None = None) -> dict:
    return {'label': label, 'url': url}


def landing_crumbs(city=None, subject=None, grade=None, location=None) -> list[dict]:
    """Breadcrumb trail for the tutor marketplace pages (fix: whole-app navigation pass).

    Mirrors the exact same city → subject → grade → location escalation used to build
    `canonical_name`/`canonical_kwargs` in `hometutor.views.tutor_city_landing` — these SEO
    landing pages can be up to 5 levels deep, and had zero breadcrumb support before this.
    """
    crumbs = [crumb('Find a tutor', reverse('hometutor:tutor_list'))]
    if not city:
        return crumbs

    city_kwargs = {'city_slug': slugify(city)}
    if not subject:
        crumbs.append(crumb(city))
        return crumbs
    crumbs.append(crumb(city, reverse('hometutor:tutor_city_landing', kwargs=city_kwargs)))

    subject_kwargs = {**city_kwargs, 'subject_slug': slugify(subject)}
    if not grade:
        crumbs.append(crumb(subject))
        return crumbs
    crumbs.append(crumb(subject, reverse('hometutor:tutor_city_subject_landing', kwargs=subject_kwargs)))

    grade_kwargs = {**subject_kwargs, 'grade': grade}
    if not location:
        crumbs.append(crumb(f'Class {grade}'))
        return crumbs
    crumbs.append(
        crumb(f'Class {grade}', reverse('hometutor:tutor_city_subject_class_landing', kwargs=grade_kwargs))
    )
    crumbs.append(crumb(location))
    return crumbs


def tutor_detail_crumbs(profile: TutorProfile) -> list[dict]:
    city = (profile.city or '').strip()
    crumbs = [crumb('Find a tutor', reverse('hometutor:tutor_list'))]
    if city:
        crumbs.append(crumb(city, reverse('hometutor:tutor_city_landing', kwargs={'city_slug': slugify(city)})))
    crumbs.append(crumb(profile.display_name))
    return crumbs


def get_tutor_profile(user) -> TutorProfile | None:
    if not user.is_authenticated:
        return None
    return TutorProfile.objects.filter(user=user).first()


def tutor_to_card_dict(profile: TutorProfile, pilot: str | None = None) -> dict:
    fallback_city = pilot or PILOT_CITY
    city = profile.city or fallback_city
    avatar_seed = quote_plus(profile.display_name or profile.slug or 'Tutor')
    image_url = (
        profile.profile_image.url
        if profile.profile_image
        else f'https://ui-avatars.com/api/?name={avatar_seed}&background=4f46e5&color=ffffff&size=256&rounded=true'
    )
    return {
        'name': profile.display_name,
        'image_url': image_url,
        'subjects': profile.subjects,
        'teaching_mode': profile.get_teaching_mode_display(),
        'languages': profile.languages or '—',
        'classes': profile.classes_label or (
            f'Class {profile.teaches_from}–{profile.teaches_to}'
        ),
        'class_range': f'Class {profile.teaches_from}-{profile.teaches_to}',
        'fee_label': profile.fee_label or 'Fee on request',
        'area': profile.area or '—',
        'city': city,
        'pincode': profile.pincode or '',
        'rating': str(profile.rating_display),
        'reviews': profile.reviews_count,
        'verified': profile.verification_status == TutorProfile.VerificationStatus.APPROVED,
        'profile_url': reverse('hometutor:tutor_detail', kwargs={'slug': profile.slug}),
        'slug': profile.slug,
        'pilot_city': fallback_city,
    }


def attach_demo_status_to_cards(cards: list[dict], requester) -> list[dict]:
    """
    Add latest demo request status (if any) for each tutor card and requester.
    Keeps card payload template-friendly.
    """
    if not requester or not getattr(requester, 'is_authenticated', False):
        for card in cards:
            card['demo_status'] = ''
        return cards

    slugs = [c.get('slug') for c in cards if c.get('slug')]
    if not slugs:
        return cards

    requests = (
        DemoRequest.objects.filter(requester=requester, tutor__slug__in=slugs)
        .select_related('tutor')
        .order_by('-created_at')
    )
    latest_by_slug = {}
    for item in requests:
        slug = item.tutor.slug
        if slug not in latest_by_slug:
            latest_by_slug[slug] = item.status

    for card in cards:
        card['demo_status'] = latest_by_slug.get(card.get('slug', ''), '')
    return cards


def hometutor_landing_stats() -> dict:
    """Aggregate stats for the public home tutor landing page.

    Same numbers for every visitor (not request-scoped), and this runs on
    every tutor list + every city/subject/grade/location SEO landing page —
    the highest-traffic surface in the app. Cache it instead of re-running
    two aggregate queries per pageview.
    """
    stats = cache.get("hometutor_landing_stats")
    if stats is not None:
        return stats

    qs = TutorProfile.objects.filter(
        verification_status=TutorProfile.VerificationStatus.APPROVED,
    )
    agg = qs.aggregate(
        tutors=Count("id"),
        reviews=Sum("reviews_count"),
        avg_rating=Avg("rating_display"),
    )
    city_count = qs.values("city").distinct().count()
    tutor_count = agg["tutors"] or 0
    review_count = int(agg["reviews"] or 0)
    avg_rating = float(agg["avg_rating"] or 4.8)
    stats = {
        "tutor_count": tutor_count,
        "city_count": city_count,
        "review_count": review_count,
        "avg_rating": round(avg_rating, 1),
        "families_label": f"{max(tutor_count * 8, review_count or 120)}+",
    }
    cache.set("hometutor_landing_stats", stats, timeout=600)
    return stats


def hometutor_landing_page_context() -> dict:
    return {
        "landing_stats": hometutor_landing_stats(),
        "landing_subjects": LANDING_SUBJECTS,
    }


def featured_home_tutors(limit: int = 6) -> tuple[list[dict], bool]:
    """
    Return (rows, from_database).
    Prefer approved tutors in the pilot city; fall back to static HT-0 data if none.
    """
    pilot = PILOT_CITY
    tutors = list(
        TutorProfile.objects.filter(
            verification_status=TutorProfile.VerificationStatus.APPROVED,
            city__iexact=pilot,
        )
        .order_by('-is_featured_home', '-rating_display', 'display_name')[:limit]
    )
    if not tutors:
        rows = []
        for row in FEATURED_HOME_TUTORS[:limit]:
            r = dict(row)
            r['profile_url'] = None
            r['pilot_city'] = pilot
            rows.append(r)
        return rows, False

    return [tutor_to_card_dict(p, pilot) for p in tutors], True


def public_tutor_queryset(request_get):
    """Filter approved, bookable listings for the public search page."""
    qs = TutorProfile.objects.filter(
        verification_status=TutorProfile.VerificationStatus.APPROVED,
    )
    city = (request_get.get('city') or PILOT_CITY).strip()
    if city:
        qs = qs.filter(city__iexact=city)

    q = (request_get.get('q') or '').strip()
    if q:
        from django.db.models import Q

        qs = qs.filter(
            Q(display_name__icontains=q)
            | Q(subjects__icontains=q)
            | Q(area__icontains=q)
        )

    subject = (request_get.get('subject') or '').strip()
    if subject:
        qs = qs.filter(subjects__icontains=subject)
    mode = (request_get.get('mode') or '').strip().upper()
    if mode in {'OFFLINE', 'ONLINE', 'HYBRID'}:
        qs = qs.filter(teaching_mode=mode)
    language = (request_get.get('language') or '').strip()
    if language:
        qs = qs.filter(languages__icontains=language)

    class_min = request_get.get('class_min', '').strip()
    if class_min.isdigit():
        g = int(class_min)
        if 1 <= g <= 12:
            qs = qs.filter(teaches_from__lte=g, teaches_to__gte=g)

    area = (request_get.get('area') or '').strip()
    if area:
        qs = qs.filter(area__icontains=area)

    pincode = (request_get.get('pincode') or '').strip()
    radius_km = (request_get.get('radius_km') or '').strip()
    if pincode and radius_km.isdigit():
        radius = int(radius_km)
        if radius > 0:
            center = PincodeGeo.objects.filter(pincode=pincode, is_active=True).first()
            if center:
                with_coords = qs.filter(latitude__isnull=False, longitude__isnull=False)
                keep_ids = []
                for t in with_coords:
                    d = _haversine_km(
                        float(center.latitude),
                        float(center.longitude),
                        float(t.latitude),
                        float(t.longitude),
                    )
                    if d <= radius:
                        keep_ids.append(t.id)
                qs = qs.filter(id__in=keep_ids)
            else:
                qs = qs.none()

    # Smart ordering: after featured + rating (which are sparse/tied on a young marketplace),
    # break ties by proven responsiveness — tutors who actually accept demo requests surface
    # above dormant listings a parent would otherwise waste a request on.
    from django.db.models import Q as _Q

    qs = qs.annotate(
        _accepted_demos=Count(
            'demo_requests',
            filter=_Q(demo_requests__status=DemoRequest.Status.ACCEPTED),
        ),
    )
    return qs.order_by('-is_featured_home', '-rating_display', '-_accepted_demos', 'display_name')


def paginated_tutor_page(request_get, page_number, user=None):
    """Return (cards, page_obj) for marketplace listing — one page of tutors only."""
    from django.core.paginator import Paginator

    page = Paginator(public_tutor_queryset(request_get), TUTORS_PER_PAGE).get_page(page_number or 1)
    cards = [tutor_to_card_dict(t, PILOT_CITY) for t in page.object_list]
    if user is not None:
        cards = attach_demo_status_to_cards(cards, user)
    return cards, page


def top_featured_tutor_cards(request_get, user=None, limit: int = 3):
    """Top N tutors for hero strip — separate lightweight query."""
    tutors = list(public_tutor_queryset(request_get)[:limit])
    cards = [tutor_to_card_dict(t, PILOT_CITY) for t in tutors]
    if user is not None:
        cards = attach_demo_status_to_cards(cards, user)
    return cards


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


def masked_email(value: str) -> str:
    if not value or '@' not in value:
        return 'hidden'
    name, domain = value.split('@', 1)
    if len(name) <= 2:
        safe = name[0] + '*'
    else:
        safe = name[:2] + '*' * max(2, len(name) - 2)
    return f'{safe}@{domain}'


def masked_phone(value: str) -> str:
    if not value:
        return ''
    digits = ''.join(ch for ch in value if ch.isdigit())
    if len(digits) < 4:
        return 'hidden'
    return ('*' * (len(digits) - 4)) + digits[-4:]


def notify_demo_request_created(demo: DemoRequest) -> None:
    """Notify linked tutor, or staff when the listing has no live tutor account.

    Never raises — demo save must not fail because of email/notification issues.
    """
    try:
        _notify_demo_request_created_inner(demo)
    except Exception as exc:
        logger.warning('notify_demo_request_created failed: %s', exc, exc_info=True)


def _notify_demo_request_created_inner(demo: DemoRequest) -> None:
    from django.contrib.auth import get_user_model

    from users.gamification import send_notification

    User = get_user_model()
    tutor_user = demo.tutor.user
    subject = f'[RankJee] New demo request for {demo.tutor.display_name}'
    body = (
        f'New demo request on RankJee.\n\n'
        f'Tutor listing: {demo.tutor.display_name} ({demo.tutor.city})\n'
        f'Slug: {demo.tutor.slug}\n'
        f'Linked account: {"yes" if tutor_user else "NO — platform-managed listing"}\n'
        f'From: {demo.requester.get_username()} ({demo.requester.email})\n'
        f'Phone: {demo.contact_phone or "(none)"}\n'
        f'Message:\n{demo.message or "(none)"}\n\n'
        f'Open admin: /sd/hometutor/demorequest/{demo.pk}/change/\n'
    )

    if tutor_user:
        link = reverse('hometutor:tutor_demos')
        send_notification(
            tutor_user,
            f'New demo request from {demo.requester.get_username()}.',
            link,
        )
        if tutor_user.email:
            try:
                send_mail(
                    subject,
                    body,
                    settings.DEFAULT_FROM_EMAIL or 'noreply@localhost',
                    [tutor_user.email],
                    fail_silently=True,
                )
            except Exception as exc:
                logger.warning('Demo request email failed: %s', exc, exc_info=True)
        return

    # Unlinked listing → staff inbox (in-app + email)
    staff_qs = User.objects.filter(is_staff=True, is_active=True)
    try:
        admin_link = reverse('admin:hometutor_demorequest_change', args=[demo.pk])
    except Exception:
        admin_link = f'/sd/hometutor/demorequest/{demo.pk}/change/'
    note = (
        f'Demo lead: {demo.tutor.display_name} ← {demo.requester.get_username()}'
    )[:300]
    for staff in staff_qs[:20]:
        try:
            send_notification(staff, note, admin_link)
        except Exception as exc:
            logger.warning('Staff demo notification failed: %s', exc, exc_info=True)
    staff_emails = list(
        staff_qs.exclude(email='').values_list('email', flat=True)[:10]
    )
    fallback = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or ''
    recipients = staff_emails or ([fallback] if fallback else [])
    if recipients:
        try:
            send_mail(
                subject + ' [needs staff follow-up]',
                body,
                settings.DEFAULT_FROM_EMAIL or 'noreply@localhost',
                recipients,
                fail_silently=True,
            )
        except Exception as exc:
            logger.warning('Staff demo-lead email failed: %s', exc, exc_info=True)


def notify_demo_resolved_for_requester(demo: DemoRequest) -> None:
    from users.gamification import send_notification

    u = demo.requester
    link = reverse('hometutor:my_demo_requests')
    if demo.status == DemoRequest.Status.ACCEPTED:
        msg = (
            f'{demo.tutor.display_name} accepted your demo'
            + (f' for {demo.scheduled_at:%d %b %Y %H:%M}' if demo.scheduled_at else '')
            + '. You and the tutor must confirm the time under My demo requests.'
        )
    elif demo.status == DemoRequest.Status.DECLINED:
        msg = f'{demo.tutor.display_name} declined your demo request.'
    else:
        return
    send_notification(u, msg, link)
    if u.email:
        try:
            send_mail(
                f'[RankJee] Demo {demo.get_status_display()}',
                msg + '\n\nOpen RankJee to view details.',
                settings.DEFAULT_FROM_EMAIL or 'noreply@localhost',
                [u.email],
                fail_silently=False,
            )
        except Exception as exc:
            logger.warning('Demo resolution email failed: %s', exc, exc_info=True)


def ensure_engagement(demo: DemoRequest) -> TutorEngagement:
    """Create engagement row when a demo is accepted (idempotent)."""
    eng, _ = TutorEngagement.objects.get_or_create(
        demo_request=demo,
        defaults={
            'tutor_profile': demo.tutor,
            'student': demo.requester,
            'status': TutorEngagement.Status.PENDING_MUTUAL,
        },
    )
    return eng


def ensure_engagements_bulk(demos) -> None:
    """Batch-create engagement rows for accepted demos missing one — one INSERT instead
    of a get_or_create() round trip per row. Callers must query `demos` with
    select_related('engagement') so checking `d.engagement` below is query-free."""
    missing = []
    for d in demos:
        if d.status != DemoRequest.Status.ACCEPTED:
            continue
        try:
            d.engagement
        except TutorEngagement.DoesNotExist:
            missing.append(d)
    if not missing:
        return
    TutorEngagement.objects.bulk_create(
        [
            TutorEngagement(
                demo_request=d,
                tutor_profile=d.tutor,
                student=d.requester,
                status=TutorEngagement.Status.PENDING_MUTUAL,
            )
            for d in missing
        ],
        ignore_conflicts=True,
    )


def apply_engagement_confirm(eng: TutorEngagement, *, as_parent: bool) -> tuple[bool, bool]:
    """
    Record parent or tutor confirmation.
    Returns (mutual_just_completed, side_updated_this_call).
    Idempotent per side.
    """
    now = timezone.now()
    side_updated = False
    if as_parent:
        if not eng.parent_confirmed_at:
            eng.parent_confirmed_at = now
            side_updated = True
    else:
        if not eng.tutor_confirmed_at:
            eng.tutor_confirmed_at = now
            side_updated = True
    if not side_updated:
        return False, False

    mutual_just = False
    if eng.parent_confirmed_at and eng.tutor_confirmed_at:
        if eng.mutual_confirmed_at is None:
            eng.mutual_confirmed_at = now
            mutual_just = True
        eng.status = TutorEngagement.Status.ACTIVE
    else:
        eng.status = TutorEngagement.Status.PENDING_MUTUAL

    eng.save()
    return mutual_just, True


def notify_engagement_confirm(eng: TutorEngagement, *, as_parent: bool, just_completed: bool) -> None:
    """In-app + light email when one side confirms or both complete."""
    from users.gamification import send_notification

    demo = eng.demo_request
    when = demo.scheduled_at.strftime('%d %b %H:%M') if demo.scheduled_at else 'the agreed time'

    if just_completed:
        msg_p = f'Demo with {demo.tutor.display_name} is fully confirmed for {when}.'
        msg_t = f'Demo with {demo.requester.get_username()} is fully confirmed for {when}.'
        if demo.requester:
            send_notification(demo.requester, msg_p, reverse('hometutor:my_demo_requests'))
        tu = demo.tutor.user
        if tu:
            send_notification(tu, msg_t, reverse('hometutor:tutor_demos'))
        _email_pair(
            demo,
            f'[RankJee] Demo fully confirmed — {when}',
            f'Both sides confirmed the demo at {when}.',
        )
        return

    if as_parent:
        tu = demo.tutor.user
        if tu:
            send_notification(
                tu,
                f'{demo.requester.get_username()} confirmed the proposed demo ({when}).',
                reverse('hometutor:tutor_demos'),
            )
        _email_pair(
            demo,
            f'[RankJee] Parent confirmed demo ({when})',
            f'{demo.requester.get_username()} confirmed the proposed demo time.',
            to_tutor_only=True,
        )
    else:
        send_notification(
            demo.requester,
            f'{demo.tutor.display_name} confirmed the proposed demo ({when}).',
            reverse('hometutor:my_demo_requests'),
        )
        _email_pair(
            demo,
            f'[RankJee] Tutor confirmed demo ({when})',
            f'{demo.tutor.display_name} confirmed the proposed demo time.',
            to_parent_only=True,
        )


def _email_pair(demo: DemoRequest, subject: str, body: str, *, to_tutor_only=False, to_parent_only=False) -> None:
    addrs = []
    if not to_tutor_only and demo.requester.email:
        addrs.append(demo.requester.email)
    if not to_parent_only:
        tu = demo.tutor.user
        if tu and tu.email:
            addrs.append(tu.email)
    for addr in set(addrs):
        try:
            send_mail(
                subject,
                body + '\n\nOpen RankJee for details.',
                settings.DEFAULT_FROM_EMAIL or 'noreply@localhost',
                [addr],
                fail_silently=False,
            )
        except Exception as exc:
            logger.warning('Engagement email failed for %s: %s', addr, exc, exc_info=True)
