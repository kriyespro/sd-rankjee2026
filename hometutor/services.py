"""Home tutor listing helpers (HT-1) + tutor utilities (HT-2)."""

import logging
from urllib.parse import quote_plus
from math import atan2, cos, radians, sin, sqrt

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from core.hometutor_data import FEATURED_HOME_TUTORS, PILOT_CITY

from .models import DemoRequest, PincodeGeo, TutorEngagement, TutorProfile

logger = logging.getLogger('rankjee.hometutor')


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


def featured_home_tutors(limit: int = 6) -> tuple[list[dict], bool]:
    """
    Return (rows, from_database).
    Prefer approved tutors in the pilot city; fall back to static HT-0 data if none.
    """
    pilot = PILOT_CITY
    qs = (
        TutorProfile.objects.filter(
            verification_status=TutorProfile.VerificationStatus.APPROVED,
            city__iexact=pilot,
        )
        .order_by('-is_featured_home', '-rating_display', 'display_name')[:limit]
    )
    if not qs.exists():
        rows = []
        for row in FEATURED_HOME_TUTORS[:limit]:
            r = dict(row)
            r['profile_url'] = None
            r['pilot_city'] = pilot
            rows.append(r)
        return rows, False

    return [tutor_to_card_dict(p, pilot) for p in qs], True


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

    return qs.order_by('-is_featured_home', '-rating_display', 'display_name')


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
    """In-app notification + best-effort email to tutor."""
    from users.gamification import send_notification

    tutor_user = demo.tutor.user
    if tutor_user:
        link = reverse('hometutor:tutor_demos')
        send_notification(
            tutor_user,
            f'New demo request from {demo.requester.get_username()}.',
            link,
        )
    subject = f'[RankJee] New demo request for {demo.tutor.display_name}'
    body = (
        f'You have a new demo request on RankJee.\n\n'
        f'From: {demo.requester.get_username()} ({demo.requester.email})\n'
        f'Message:\n{demo.message or "(none)"}\n'
    )
    if tutor_user and tutor_user.email:
        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL or 'noreply@localhost',
                [tutor_user.email],
                fail_silently=False,
            )
        except Exception as exc:
            logger.warning('Demo request email failed: %s', exc, exc_info=True)


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
