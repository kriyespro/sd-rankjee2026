"""
Import JSON produced by export_content_bundle (creates/updates paths, skills, questions).
Usage:
  python manage.py import_content_bundle
  python manage.py import_content_bundle /app/rankjee_full.json
"""
import json
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from assessment.models import SkillPath, Skill, Question

_DEFAULT_BUNDLE = Path(settings.BASE_DIR) / "rankjee_full.json"


class Command(BaseCommand):
    help = "Import assessment bundle JSON (paths → skills → questions). Re-partitions each touched skill."

    def add_arguments(self, parser):
        parser.add_argument(
            "json_file",
            nargs="?",
            default=str(_DEFAULT_BUNDLE),
            help=f"Path to bundle JSON (default: {_DEFAULT_BUNDLE.name} in project root)",
        )

    def handle(self, *args, **options):
        path = options["json_file"]
        path = str(Path(path).resolve()) if path else str(_DEFAULT_BUNDLE.resolve())
        self.stdout.write(f"Using bundle file: {path}")
        if not os.path.exists(path):
            raise CommandError(
                f"File not found: {path}\n"
                f"Add rankjee_full.json next to manage.py (or pass full path). "
                f"In Docker: copy to host project dir so it appears as /app/rankjee_full.json."
            )

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict) or "paths" not in data:
            raise CommandError("Invalid bundle: expected object with 'paths' array.")

        if not data["paths"]:
            raise CommandError(
                "Bundle has empty 'paths' array — nothing to import. "
                "Re-export locally: python manage.py export_content_bundle rankjee_full.json"
            )

        touched_skills = []

        with transaction.atomic():
            for p in data["paths"]:
                path_obj, _ = SkillPath.objects.update_or_create(
                    name=(p.get("name") or "").strip(),
                    defaults={
                        "description": (p.get("description") or "").strip(),
                        "level_order": int(p.get("level_order") or 1),
                        "is_active": p.get("is_active", True),
                    },
                )
                for s in p.get("skills") or []:
                    skill, _ = Skill.objects.update_or_create(
                        path=path_obj,
                        name=(s.get("name") or "").strip(),
                        defaults={
                            "description": (s.get("description") or "").strip(),
                            "order": int(s.get("order") or 0),
                            "is_active": s.get("is_active", True),
                        },
                    )
                    skill.questions.all().delete()
                    for q in s.get("questions") or []:
                        co = (q.get("correct_option") or "A").strip().upper()
                        if co not in ("A", "B", "C", "D"):
                            co = "A"
                        diff = (q.get("difficulty") or "EASY").strip().upper()
                        if diff not in ("EASY", "MEDIUM", "HARD"):
                            diff = "EASY"
                        Question.objects.create(
                            skill=skill,
                            text=(q.get("text") or "").strip(),
                            concept_tag=((q.get("concept_tag") or "General").strip())[:50],
                            explanation=(q.get("explanation") or "").strip(),
                            difficulty=diff,
                            option_a=(q.get("option_a") or "")[:200],
                            option_b=(q.get("option_b") or "")[:200],
                            option_c=(q.get("option_c") or "")[:200],
                            option_d=(q.get("option_d") or "")[:200],
                            correct_option=co,
                        )
                    touched_skills.append(skill)

            for s in data.get("unassigned_skills") or []:
                nm = (s.get("name") or "").strip()
                skill = Skill.objects.filter(path__isnull=True, name=nm).first()
                if skill:
                    skill.description = (s.get("description") or "").strip()
                    skill.order = int(s.get("order") or 0)
                    skill.is_active = s.get("is_active", True)
                    skill.save()
                else:
                    skill = Skill.objects.create(
                        path=None,
                        name=nm,
                        description=(s.get("description") or "").strip(),
                        order=int(s.get("order") or 0),
                        is_active=s.get("is_active", True),
                    )
                skill.questions.all().delete()
                for q in s.get("questions") or []:
                    co = (q.get("correct_option") or "A").strip().upper()
                    if co not in ("A", "B", "C", "D"):
                        co = "A"
                    diff = (q.get("difficulty") or "EASY").strip().upper()
                    if diff not in ("EASY", "MEDIUM", "HARD"):
                        diff = "EASY"
                    Question.objects.create(
                        skill=skill,
                        text=(q.get("text") or "").strip(),
                        concept_tag=((q.get("concept_tag") or "General").strip())[:50],
                        explanation=(q.get("explanation") or "").strip(),
                        difficulty=diff,
                        option_a=(q.get("option_a") or "")[:200],
                        option_b=(q.get("option_b") or "")[:200],
                        option_c=(q.get("option_c") or "")[:200],
                        option_d=(q.get("option_d") or "")[:200],
                        correct_option=co,
                    )
                touched_skills.append(skill)

        for skill in touched_skills:
            n = skill.partition_questions()
            self.stdout.write(f'Partitioned "{skill.name}": {n} set(s).')

        self.stdout.write(self.style.SUCCESS(f"Imported bundle from {path}"))
