"""
Quick runner for seeding professional tutor data.

Usage:
    python seed_500_tutors.py
    python seed_500_tutors.py --wipe
    python seed_500_tutors.py --count 500 --all-cities --city Ahmedabad
"""

import argparse
import os


def main():
    parser = argparse.ArgumentParser(description='Seed TutorProfile data into database.')
    parser.add_argument('--count', type=int, default=500)
    parser.add_argument('--city', default='Ahmedabad')
    parser.add_argument('--all-cities', action='store_true')
    parser.add_argument('--wipe', action='store_true')
    args = parser.parse_args()

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rankjee.settings')
    import django  # noqa: PLC0415

    django.setup()
    from django.core.management import call_command  # noqa: PLC0415

    call_command(
        'seed_hometutor_tutors',
        count=args.count,
        city=args.city,
        all_cities=args.all_cities,
        wipe=args.wipe,
    )


if __name__ == '__main__':
    main()
