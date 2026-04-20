"""Seed ~25 approved home tutors in the pilot city (HT-1). Safe to re-run: upserts by slug."""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.hometutor_data import PILOT_CITY

from hometutor.models import TutorProfile

_AREAS = [
    'Satellite', 'Bodakdev', 'Vastrapur', 'Navrangpura', 'SG Highway',
    'Prahlad Nagar', 'Maninagar', 'Naranpura', 'Gurukul', 'Thaltej',
    'Bopal', 'Nikol', 'Chandkheda', 'Gota', 'Ambawadi',
]

_SUBJECT_SETS = [
    ('Math', 'Physics'),
    ('Chemistry', 'Biology'),
    ('English', 'Hindi'),
    ('Science', 'Math'),
    ('Physics', 'Chemistry'),
    ('Math',),
    ('Accountancy', 'Economics'),
    ('Computer Science', 'Math'),
    ('Biology', 'Chemistry'),
    ('Social Science', 'English'),
]


class Command(BaseCommand):
    help = 'Create or update ~25 approved TutorProfile rows in the pilot city (default Ahmedabad).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--city',
            default=PILOT_CITY,
            help=f'Pilot city (default: {PILOT_CITY})',
        )

    def handle(self, *args, **options):
        city = (options['city'] or PILOT_CITY).strip()
        created = 0
        updated = 0

        for i in range(1, 26):
            display_name = f'Seed Tutor {i:02d}'
            slug = slugify(f'{city}-{display_name}')[:110]

            area = _AREAS[(i - 1) % len(_AREAS)]
            subj = _SUBJECT_SETS[(i - 1) % len(_SUBJECT_SETS)]
            subjects = ', '.join(subj)
            tf = 6 + (i % 5)
            tt = min(12, max(tf, 9 + (i % 4)))
            fee = 4500 + (i * 180)
            rating = Decimal('4.0') + Decimal((i % 10)) / Decimal('10')
            reviews = 5 + (i * 3) % 40
            featured = i <= 6

            defaults = {
                'display_name': display_name,
                'city': city,
                'area': area,
                'pincode': f'380{10 + i:03d}',
                'subjects': subjects,
                'teaching_mode': (
                    TutorProfile.TeachingMode.HYBRID
                    if i % 3 == 0
                    else (TutorProfile.TeachingMode.ONLINE if i % 2 == 0 else TutorProfile.TeachingMode.OFFLINE)
                ),
                'languages': 'English, Hindi' if i % 2 == 0 else 'English, Gujarati',
                'classes_label': f'Class {tf}–{tt} · CBSE',
                'teaches_from': tf,
                'teaches_to': tt,
                'fee_label': f'from ₹{fee}/mo',
                'bio': (
                    f'Experienced home tutor in {area}, {city}. '
                    f'Focus on boards and exam readiness; structured weekly plans.'
                ),
                'rating_display': rating,
                'reviews_count': reviews,
                'verification_status': TutorProfile.VerificationStatus.APPROVED,
                'is_featured_home': featured,
            }

            obj, was_created = TutorProfile.objects.update_or_create(
                slug=slug,
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. city={city!r} created={created} updated={updated} (total 25 upserts).'
            )
        )
