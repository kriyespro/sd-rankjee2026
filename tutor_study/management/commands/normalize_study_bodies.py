from django.core.management.base import BaseCommand

from tutor_study.body_format import normalize_study_body_text
from tutor_study.models import StudyMaterial


class Command(BaseCommand):
    help = 'Normalize stored study material bodies (fix literal \\r\\n from copy-paste).'

    def handle(self, *args, **options):
        updated = 0
        for material in StudyMaterial.objects.all().only('id', 'body'):
            raw = material.body or ''
            normalized = normalize_study_body_text(raw)
            if normalized != raw:
                StudyMaterial.objects.filter(pk=material.pk).update(body=normalized)
                updated += 1
        self.stdout.write(self.style.SUCCESS(f'Normalized {updated} study material(s).'))
