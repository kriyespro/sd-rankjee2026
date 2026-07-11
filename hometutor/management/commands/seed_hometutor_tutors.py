"""Seed realistic India-context tutor listings. Safe to re-run: upserts by slug.

Fees are always ₹5,000–₹10,000/mo. Names are full Indian name pairs (not
predictable first×last cycling).
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.hometutor_data import PILOT_CITY

from hometutor.models import DemoRequest, TutorProfile

# Realistic full names (common Indian combinations — not first×last grid)
_FULL_NAMES = [
    'Rahul Sharma', 'Priya Desai', 'Amit Patel', 'Sneha Iyer', 'Vikram Singh',
    'Ananya Mehta', 'Rohit Gupta', 'Kavita Reddy', 'Suresh Nair', 'Meera Joshi',
    'Arjun Malhotra', 'Neha Kapoor', 'Deepak Verma', 'Pooja Agarwal', 'Karan Chopra',
    'Divya Banerjee', 'Siddharth Rao', 'Anjali Mishra', 'Manish Yadav', 'Ritu Saxena',
    'Nikhil Kulkarni', 'Shreya Pandey', 'Abhishek Jain', 'Tanvi Choudhary', 'Harsh Trivedi',
    'Isha Bhatt', 'Yash Thakur', 'Nidhi Shah', 'Pranav Menon', 'Swati Das',
    'Aditya Bansal', 'Richa Goel', 'Varun Khanna', 'Pallavi Sinha', 'Gaurav Tiwari',
    'Sonal Krishnan', 'Ravi Shetty', 'Komal Bhatia', 'Mohit Chauhan', 'Ayesha Khan',
    'Sanjay Pillai', 'Lakshmi Narayanan', 'Farhan Ali', 'Geeta Rani', 'Naveen Kumar',
    'Sunita Devi', 'Rajesh Prasad', 'Fatima Begum', 'Vivek Anand', 'Jyoti Kumari',
    'Ashwin Subramanian', 'Rekha Nambiar', 'Imran Qureshi', 'Bhavna Solanki', 'Tejas Waghmare',
    'Chitra Venkatesh', 'Dinesh Rawat', 'Hema Sundaram', 'Jatin Arora', 'Kirti Lodha',
    'Lokesh Hegde', 'Madhuri Patil', 'Omkar Deshmukh', 'Parul Vyas', 'Qamar Hussain',
    'Ramesh Gowda', 'Sarita Mohanty', 'Uday Kamat', 'Vandana Biswas', 'Wasim Sheikh',
    'Xavier Fernandes', 'Yogesh Barot', 'Zoya Merchant', 'Ajay Chauhan', 'Bharti Jha',
    'Chetan Salvi', 'Devika Nair', 'Esha Grover', 'Faisal Ahmed', 'Gayatri Iyer',
    'Hemant Joshi', 'Indira Rao', 'Jaya Krishnan', 'Kunal Mehta', 'Lata Sharma',
    'Manoj Reddy', 'Naina Kapoor', 'Ojasvi Singh', 'Pradeep Gupta', 'Radhika Patel',
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
    ('Math', 'Mental Ability'),
    ('Physics', 'JEE Main'),
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

# Monthly fee buckets parents actually see in India home tuition (₹5k–₹10k)
_FEE_OPTIONS = [
    5000, 5500, 6000, 6500, 7000, 7500, 8000, 8500, 9000, 9500, 10000,
]


def _fee_label(amount: int) -> str:
    return f'₹{amount:,}/mo'


def _bio(display_name: str, area: str, city: str, state: str, subjects: str, board: str, years: int) -> str:
    return (
        f'{display_name} is a home tutor in {area}, {city} ({state}) with {years}+ years of teaching. '
        f'Teaches {subjects} for {board} students. Focus on concept clarity, weekly homework, '
        f'and parent updates after every month.'
    )


class Command(BaseCommand):
    help = 'Create or update realistic TutorProfile rows (fees ₹5,000–₹10,000/mo).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--city',
            default=PILOT_CITY,
            help=f'City override (default: {PILOT_CITY}). Use --all-cities for India-wide mix.',
        )
        parser.add_argument(
            '--count',
            type=int,
            default=80,
            help='Number of tutors to generate (default: 80).',
        )
        parser.add_argument(
            '--all-cities',
            action='store_true',
            help='Spread tutors across major Indian cities instead of one city.',
        )
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Delete existing TutorProfile rows before seeding (keeps tutors with demo history).',
        )
        parser.add_argument(
            '--fix-fees-only',
            action='store_true',
            help='Only clamp existing fee_label values into ₹5,000–₹10,000 (no new tutors).',
        )

    def handle(self, *args, **options):
        if options.get('fix_fees_only'):
            self._fix_fees_only()
            return

        city = (options['city'] or PILOT_CITY).strip()
        count = max(1, int(options['count'] or 80))
        use_all_cities = bool(options.get('all_cities'))
        wipe = bool(options.get('wipe'))
        created = 0
        updated = 0
        city_names = list(_CITY_PROFILES.keys())

        if wipe:
            protected_ids = set(
                DemoRequest.objects.exclude(tutor_id__isnull=True).values_list('tutor_id', flat=True)
            )
            delete_qs = TutorProfile.objects.exclude(id__in=protected_ids).filter(user__isnull=True)
            deleted_count, _ = delete_qs.delete()
            self.stdout.write(self.style.WARNING(f'Wiped unlinked seed TutorProfile rows: {deleted_count}'))
            if protected_ids:
                self.stdout.write(
                    self.style.WARNING(
                        f'Skipped {len(protected_ids)} tutor(s) linked to demo history (protected).'
                    )
                )

        for i in range(1, count + 1):
            selected_city = city_names[(i - 1) % len(city_names)] if use_all_cities else city
            city_profile = _CITY_PROFILES.get(selected_city) or _CITY_PROFILES[PILOT_CITY]
            selected_city = selected_city if selected_city in _CITY_PROFILES else PILOT_CITY

            display_name = _FULL_NAMES[(i - 1) % len(_FULL_NAMES)]
            # Avoid duplicate display names colliding on same slug when count > name list
            slug_base = f'{selected_city}-{display_name}'
            if i > len(_FULL_NAMES):
                slug_base = f'{slug_base}-{i}'
            slug = slugify(slug_base)[:110]

            area = city_profile['areas'][(i - 1) % len(city_profile['areas'])]
            subj = _SUBJECT_SETS[(i - 1) % len(_SUBJECT_SETS)]
            subjects = ', '.join(subj)
            board = _BOARD_LABELS[(i - 1) % len(_BOARD_LABELS)]

            tf = 6 + (i % 4)  # typically 6–9
            tt = min(12, max(tf + 2, 10 + (i % 3)))  # up to 10–12
            fee = _FEE_OPTIONS[(i - 1) % len(_FEE_OPTIONS)]
            rating = Decimal('4.2') + Decimal((i % 8)) / Decimal('10')  # 4.2–4.9
            if rating > Decimal('4.9'):
                rating = Decimal('4.9')
            reviews = 12 + (i * 7) % 95
            featured = i <= 10
            pincode = str(city_profile['pincode_base'] + (i % 80))
            years = 3 + (i % 12)

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
                'classes_label': f'Class {tf}–{tt} · {board}',
                'teaches_from': tf,
                'teaches_to': tt,
                'fee_label': _fee_label(fee),
                'bio': _bio(
                    display_name, area, selected_city, city_profile['state'], subjects, board, years
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
                f'Done. city={city!r} all_cities={use_all_cities} wipe={wipe} '
                f'created={created} updated={updated} (total {count} upserts). Fees ₹5,000–₹10,000/mo.'
            )
        )

    def _fix_fees_only(self):
        """Clamp any existing fee_label into the ₹5k–₹10k band and normalize format."""
        import re

        fixed = 0
        for t in TutorProfile.objects.all().iterator():
            m = re.search(r'(\d[\d,]*)', t.fee_label or '')
            if not m:
                new_label = _fee_label(6500)
            else:
                amount = int(m.group(1).replace(',', ''))
                if amount < 5000 or amount > 10000:
                    amount = 5000 + (t.pk * 500) % 5500
                    amount = min(10000, max(5000, (amount // 500) * 500))
                new_label = _fee_label(amount)
            if t.fee_label != new_label:
                t.fee_label = new_label
                t.save(update_fields=['fee_label', 'updated_at'])
                fixed += 1
        self.stdout.write(self.style.SUCCESS(f'Fixed fee_label on {fixed} tutor(s).'))
