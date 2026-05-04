"""Ensure demo_student / demo_tutor / demo_parent can exercise the home-tutor loop locally."""

from decimal import Decimal

from django.core.management.base import BaseCommand

from core.hometutor_data import PILOT_CITY
from hometutor.models import DemoRequest, TutorProfile
from users.models import CustomUser


def _ensure_user(username: str, email: str, role: str, password: str) -> CustomUser:
    user, _ = CustomUser.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'role': role,
            'is_active': True,
            'onboarding_completed': True,
            'state': 'GJ',
        },
    )
    user.email = email
    user.role = role
    user.is_active = True
    user.onboarding_completed = True
    user.set_password(password)
    user.save()
    return user


def _ensure_pending_demo(tutor: TutorProfile, requester: CustomUser, message: str) -> None:
    if DemoRequest.objects.filter(
        tutor=tutor,
        requester=requester,
        status=DemoRequest.Status.PENDING,
    ).exists():
        return
    DemoRequest.objects.create(
        tutor=tutor,
        requester=requester,
        message=message,
        status=DemoRequest.Status.PENDING,
    )


class Command(BaseCommand):
    help = (
        'Ensure demo_student, demo_tutor, demo_parent (password demo1234) and an approved '
        'listing for demo_tutor, plus sample pending demo requests for QA.'
    )

    def handle(self, *args, **options):
        pwd = 'demo1234'
        student = _ensure_user(
            'demo_student',
            'demo_student@example.com',
            CustomUser.Role.STUDENT,
            pwd,
        )
        tutor_user = _ensure_user(
            'demo_tutor',
            'demo_tutor@example.com',
            CustomUser.Role.TUTOR,
            pwd,
        )
        parent = _ensure_user(
            'demo_parent',
            'demo_parent@example.com',
            CustomUser.Role.PARENT,
            pwd,
        )

        profile, created = TutorProfile.objects.get_or_create(
            user=tutor_user,
            defaults={
                'display_name': 'Demo Tutor (sandbox)',
                'slug': 'demo-tutor-sandbox',
                'city': PILOT_CITY,
                'area': 'Pilot area',
                'pincode': '380015',
                'subjects': 'Math, Physics, Science',
                'teaching_mode': TutorProfile.TeachingMode.HYBRID,
                'languages': 'English, Hindi',
                'classes_label': 'Class 9–12',
                'teaches_from': 9,
                'teaches_to': 12,
                'fee_label': 'from ₹5000/mo',
                'bio': 'Sandbox tutor listing for manual QA with demo_student and demo_parent.',
                'rating_display': Decimal('4.9'),
                'reviews_count': 12,
                'verification_status': TutorProfile.VerificationStatus.APPROVED,
                'is_featured_home': False,
            },
        )
        # Keep slug stable if row existed without slug set.
        if profile.slug != 'demo-tutor-sandbox':
            TutorProfile.objects.filter(pk=profile.pk).update(slug='demo-tutor-sandbox')

        _ensure_pending_demo(
            profile,
            student,
            '[Playbook] Student demo — Algebra basics.',
        )
        _ensure_pending_demo(
            profile,
            parent,
            '[Playbook] Parent demo — weekend slots for Class 10.',
        )

        detail_url = f'/hometutor/t/{profile.slug}/'
        self.stdout.write(self.style.SUCCESS('demo_three_roles ready.'))
        self.stdout.write(f'  Tutor public page: {detail_url}')
        self.stdout.write('  Logins (password demo1234): demo_student, demo_tutor, demo_parent')
        self.stdout.write('  See simulate_demo_roles.txt for the full walkthrough.')
