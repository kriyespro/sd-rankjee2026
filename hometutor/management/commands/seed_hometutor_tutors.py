"""Seed realistic India-context tutor listings. Safe to re-run: upserts by slug."""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.hometutor_data import PILOT_CITY

from hometutor.models import DemoRequest, TutorProfile

_FIRST_NAMES = [
    'Aarav', 'Vivaan', 'Aditya', 'Arjun', 'Reyansh', 'Krishna', 'Ishaan', 'Karan', 'Rohan', 'Nikhil',
    'Ananya', 'Diya', 'Aadhya', 'Kavya', 'Ira', 'Meera', 'Priya', 'Riya', 'Sneha', 'Saanvi',
    'Neha', 'Tanvi', 'Pooja', 'Nidhi', 'Isha', 'Rahul', 'Vikram', 'Siddharth', 'Manish', 'Deepak',
]

_LAST_NAMES = [
    'Sharma', 'Verma', 'Patel', 'Gupta', 'Singh', 'Yadav', 'Iyer', 'Nair', 'Reddy', 'Mishra',
    'Kulkarni', 'Jain', 'Mehta', 'Chopra', 'Agarwal', 'Choudhary', 'Pandey', 'Khan', 'Das', 'Banerjee',
]

_SUBJECT_SETS = [
    ('Math', 'Science'),
    ('Math', 'Physics'),
    ('Chemistry', 'Biology'),
    ('English', 'Social Science'),
    ('Physics', 'Chemistry'),
    ('Biology', 'NEET Foundation'),
    ('Math', 'JEE Foundation'),
    ('Accountancy', 'Economics'),
    ('Business Studies', 'Economics'),
    ('Computer Science', 'Math'),
    ('SST', 'History'),
    ('Hindi', 'Sanskrit'),
    ('English', 'Spoken English'),
    ('Science', 'Olympiad Prep'),
]

_BOARD_LABELS = [
    'CBSE',
    'ICSE',
    'State Board',
    'CBSE + Olympiad',
    'CBSE + JEE/NEET Foundation',
]

_CITY_PROFILES = {
    'Ahmedabad': {
        'state': 'Gujarat',
        'areas': ['Satellite', 'Bodakdev', 'Vastrapur', 'Navrangpura', 'Prahlad Nagar', 'Thaltej', 'Bopal', 'Maninagar'],
        'languages': ['English, Hindi, Gujarati', 'Hindi, Gujarati', 'English, Gujarati'],
        'pincode_base': 380001,
    },
    'Surat': {
        'state': 'Gujarat',
        'areas': ['Adajan', 'Vesu', 'Athwa', 'Piplod', 'Katargam', 'Pal', 'Udhna', 'Varachha'],
        'languages': ['English, Hindi, Gujarati', 'Hindi, Gujarati'],
        'pincode_base': 395001,
    },
    'Mumbai': {
        'state': 'Maharashtra',
        'areas': ['Andheri', 'Borivali', 'Powai', 'Ghatkopar', 'Dadar', 'Thane West', 'Mulund', 'Chembur'],
        'languages': ['English, Hindi, Marathi', 'Hindi, Marathi', 'English, Marathi'],
        'pincode_base': 400001,
    },
    'Pune': {
        'state': 'Maharashtra',
        'areas': ['Kothrud', 'Baner', 'Wakad', 'Hinjewadi', 'Aundh', 'Hadapsar', 'Viman Nagar', 'Pimple Saudagar'],
        'languages': ['English, Hindi, Marathi', 'Hindi, Marathi'],
        'pincode_base': 411001,
    },
    'Delhi': {
        'state': 'Delhi',
        'areas': ['Rohini', 'Dwarka', 'Laxmi Nagar', 'Janakpuri', 'Pitampura', 'Saket', 'Karol Bagh', 'Vasant Kunj'],
        'languages': ['English, Hindi', 'Hindi, Punjabi', 'English, Hindi, Punjabi'],
        'pincode_base': 110001,
    },
    'Bengaluru': {
        'state': 'Karnataka',
        'areas': ['Whitefield', 'HSR Layout', 'Indiranagar', 'Jayanagar', 'BTM Layout', 'Marathahalli', 'Yelahanka', 'Koramangala'],
        'languages': ['English, Hindi, Kannada', 'English, Kannada', 'Hindi, Kannada'],
        'pincode_base': 560001,
    },
    'Hyderabad': {
        'state': 'Telangana',
        'areas': ['Madhapur', 'Kukatpally', 'Gachibowli', 'Miyapur', 'Begumpet', 'Ameerpet', 'Kondapur', 'Secunderabad'],
        'languages': ['English, Hindi, Telugu', 'Hindi, Telugu', 'English, Telugu'],
        'pincode_base': 500001,
    },
    'Chennai': {
        'state': 'Tamil Nadu',
        'areas': ['Anna Nagar', 'Velachery', 'Tambaram', 'Porur', 'Adyar', 'T Nagar', 'OMR', 'Ambattur'],
        'languages': ['English, Tamil', 'English, Hindi, Tamil', 'Tamil, Hindi'],
        'pincode_base': 600001,
    },
    'Kolkata': {
        'state': 'West Bengal',
        'areas': ['Salt Lake', 'New Town', 'Behala', 'Howrah', 'Garia', 'Dum Dum', 'Ballygunge', 'Tollygunge'],
        'languages': ['English, Hindi, Bengali', 'Hindi, Bengali', 'English, Bengali'],
        'pincode_base': 700001,
    },
    'Jaipur': {
        'state': 'Rajasthan',
        'areas': ['Malviya Nagar', 'Vaishali Nagar', 'Mansarovar', 'Jagatpura', 'C-Scheme', 'Vidyadhar Nagar', 'Raja Park', 'Tonk Road'],
        'languages': ['English, Hindi', 'Hindi, Rajasthani'],
        'pincode_base': 302001,
    },
}


class Command(BaseCommand):
    help = 'Create or update realistic TutorProfile rows with India-focused data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--city',
            default=PILOT_CITY,
            help=f'City override (default: {PILOT_CITY}). Use --all-cities for India-wide mix.',
        )
        parser.add_argument(
            '--count',
            type=int,
            default=500,
            help='Number of tutors to generate (default: 500).',
        )
        parser.add_argument(
            '--all-cities',
            action='store_true',
            help='Spread tutors across major Indian cities instead of one city.',
        )
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Delete existing TutorProfile rows before seeding.',
        )

    def handle(self, *args, **options):
        city = (options['city'] or PILOT_CITY).strip()
        count = max(1, int(options['count'] or 500))
        use_all_cities = bool(options.get('all_cities'))
        wipe = bool(options.get('wipe'))
        created = 0
        updated = 0
        city_names = list(_CITY_PROFILES.keys())

        if wipe:
            protected_ids = set(
                DemoRequest.objects.exclude(tutor_id__isnull=True).values_list('tutor_id', flat=True)
            )
            delete_qs = TutorProfile.objects.exclude(id__in=protected_ids)
            deleted_count, _ = delete_qs.delete()
            self.stdout.write(self.style.WARNING(f'Wiped existing unlinked TutorProfile rows: {deleted_count}'))
            if protected_ids:
                self.stdout.write(
                    self.style.WARNING(
                        f'Skipped {len(protected_ids)} tutor(s) linked to demo/payment history (protected).'
                    )
                )

        for i in range(1, count + 1):
            selected_city = city_names[(i - 1) % len(city_names)] if use_all_cities else city
            city_profile = _CITY_PROFILES.get(selected_city) or _CITY_PROFILES[PILOT_CITY]
            selected_city = selected_city if selected_city in _CITY_PROFILES else PILOT_CITY

            first_name = _FIRST_NAMES[(i - 1) % len(_FIRST_NAMES)]
            last_name = _LAST_NAMES[(i - 1) % len(_LAST_NAMES)]
            display_name = f'{first_name} {last_name}'
            slug = slugify(f'{selected_city}-{display_name}-{i:03d}')[:110]

            area = city_profile['areas'][(i - 1) % len(city_profile['areas'])]
            subj = _SUBJECT_SETS[(i - 1) % len(_SUBJECT_SETS)]
            subjects = ', '.join(subj)
            board = _BOARD_LABELS[(i - 1) % len(_BOARD_LABELS)]

            tf = 3 + (i % 7)
            tt = min(12, max(tf, 8 + (i % 5)))
            fee = 3500 + (i * 220)
            rating = Decimal('4.1') + Decimal((i % 9)) / Decimal('10')
            reviews = 8 + (i * 5) % 120
            featured = i <= 12
            pincode = str(city_profile['pincode_base'] + (i % 200))

            defaults = {
                'display_name': display_name,
                'city': selected_city,
                'area': area,
                'pincode': pincode,
                'subjects': subjects,
                'teaching_mode': (
                    TutorProfile.TeachingMode.HYBRID
                    if i % 3 == 0
                    else (TutorProfile.TeachingMode.ONLINE if i % 2 == 0 else TutorProfile.TeachingMode.OFFLINE)
                ),
                'languages': city_profile['languages'][(i - 1) % len(city_profile['languages'])],
                'classes_label': f'Class {tf}-{tt} · {board}',
                'teaches_from': tf,
                'teaches_to': tt,
                'fee_label': f'from ₹{fee}/mo',
                'bio': (
                    f'Experienced home tutor in {area}, {selected_city}, {city_profile["state"]}. '
                    f'Specializes in {subjects} for {board} students with structured weekly plans and monthly progress reports.'
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
                f'Done. city={city!r} all_cities={use_all_cities} wipe={wipe} created={created} updated={updated} (total {count} upserts).'
            )
        )
