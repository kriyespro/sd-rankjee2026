"""Import / upsert TutorProfile rows from a CSV file.

Expected columns (header row required):
  display_name, city, area, pincode, subjects, teaching_mode, languages,
  classes_label, teaches_from, teaches_to, fee_label (or monthly_fee), bio,
  rating_display, reviews_count, verification_status, is_featured_home, slug

- monthly_fee: integer 5000–10000 → stored as fee_label "₹6,500/mo"
- fee_label: free text (used if monthly_fee blank)
- slug: optional; auto-generated from city + display_name if missing
- Safe to re-run: upserts by slug
"""

from __future__ import annotations

import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from hometutor.models import TutorProfile

REQUIRED = ('display_name', 'city', 'subjects')


def _parse_bool(val: str | None, default: bool = False) -> bool:
    if val is None or str(val).strip() == '':
        return default
    return str(val).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _parse_int(val: str | None, default: int) -> int:
    if val is None or str(val).strip() == '':
        return default
    try:
        return int(float(str(val).strip().replace(',', '')))
    except (TypeError, ValueError):
        return default


def _parse_decimal(val: str | None, default: Decimal) -> Decimal:
    if val is None or str(val).strip() == '':
        return default
    try:
        return Decimal(str(val).strip())
    except (InvalidOperation, ValueError):
        return default


def _fee_from_row(row: dict) -> str:
    monthly = (row.get('monthly_fee') or '').strip()
    if monthly:
        amount = _parse_int(monthly, 6500)
        amount = min(10000, max(5000, amount))
        return f'₹{amount:,}/mo'
    fee_label = (row.get('fee_label') or '').strip()
    if fee_label:
        # If numeric-looking, normalize into ₹X/mo band
        m = re.search(r'(\d[\d,]*)', fee_label)
        if m and fee_label.replace(',', '').replace('₹', '').replace('/mo', '').strip().isdigit():
            amount = int(m.group(1).replace(',', ''))
            amount = min(10000, max(5000, amount))
            return f'₹{amount:,}/mo'
        return fee_label[:80]
    return '₹6,500/mo'


def _mode(val: str | None) -> str:
    raw = (val or 'OFFLINE').strip().upper()
    allowed = {c.value for c in TutorProfile.TeachingMode}
    return raw if raw in allowed else TutorProfile.TeachingMode.OFFLINE


def _status(val: str | None) -> str:
    raw = (val or 'APPROVED').strip().upper()
    allowed = {c.value for c in TutorProfile.VerificationStatus}
    return raw if raw in allowed else TutorProfile.VerificationStatus.APPROVED


class Command(BaseCommand):
    help = 'Import tutors from CSV (upsert by slug). Use monthly_fee 5000–10000.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Path to CSV file')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate and print actions without writing to DB',
        )

    def handle(self, *args, **options):
        path = Path(options['csv_path']).expanduser()
        if not path.is_file():
            raise CommandError(f'CSV not found: {path}')

        dry = bool(options.get('dry_run'))
        created = updated = skipped = 0

        with path.open(newline='', encoding='utf-8-sig') as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                raise CommandError('CSV has no header row')
            headers = {h.strip().lower(): h for h in reader.fieldnames if h}
            missing = [c for c in REQUIRED if c not in headers]
            if missing:
                raise CommandError(f'CSV missing required columns: {", ".join(missing)}')

            for line_no, raw in enumerate(reader, start=2):
                row = {k.strip().lower(): (v or '').strip() for k, v in raw.items() if k}
                display_name = row.get('display_name', '')
                city = row.get('city', '')
                subjects = row.get('subjects', '')
                if not display_name or not city or not subjects:
                    skipped += 1
                    self.stdout.write(self.style.WARNING(f'Line {line_no}: skipped (missing required fields)'))
                    continue

                slug = (row.get('slug') or '').strip() or slugify(f'{city}-{display_name}')[:110]
                if not slug:
                    skipped += 1
                    self.stdout.write(self.style.WARNING(f'Line {line_no}: skipped (empty slug)'))
                    continue

                tf = _parse_int(row.get('teaches_from'), 6)
                tt = _parse_int(row.get('teaches_to'), 12)
                tf = min(12, max(1, tf))
                tt = min(12, max(1, tt))
                if tf > tt:
                    tf, tt = tt, tf

                classes_label = row.get('classes_label') or f'Class {tf}–{tt}'
                defaults = {
                    'display_name': display_name[:120],
                    'city': city[:80],
                    'area': (row.get('area') or '')[:120],
                    'pincode': (row.get('pincode') or '')[:10],
                    'subjects': subjects[:500],
                    'teaching_mode': _mode(row.get('teaching_mode')),
                    'languages': (row.get('languages') or 'English, Hindi')[:200],
                    'classes_label': classes_label[:200],
                    'teaches_from': tf,
                    'teaches_to': tt,
                    'fee_label': _fee_from_row(row)[:80],
                    'bio': row.get('bio') or '',
                    'rating_display': min(
                        Decimal('5.0'),
                        max(Decimal('1.0'), _parse_decimal(row.get('rating_display'), Decimal('4.5'))),
                    ),
                    'reviews_count': max(0, _parse_int(row.get('reviews_count'), 0)),
                    'verification_status': _status(row.get('verification_status')),
                    'is_featured_home': _parse_bool(row.get('is_featured_home'), False),
                }

                if dry:
                    exists = TutorProfile.objects.filter(slug=slug).exists()
                    action = 'UPDATE' if exists else 'CREATE'
                    self.stdout.write(
                        f'{action} {slug}: {display_name} · {city} · {defaults["fee_label"]}'
                    )
                    if exists:
                        updated += 1
                    else:
                        created += 1
                    continue

                _, was_created = TutorProfile.objects.update_or_create(slug=slug, defaults=defaults)
                if was_created:
                    created += 1
                else:
                    updated += 1

        verb = 'Dry-run' if dry else 'Import'
        self.stdout.write(
            self.style.SUCCESS(
                f'{verb} done. created={created} updated={updated} skipped={skipped} file={path}'
            )
        )
