"""
Export questions as a JSON list compatible with import_questions (skill_id per row).
Usage:
  python manage.py export_questions_json questions.json
  python manage.py export_questions_json questions.json --skill-id 3
"""
import json
from django.core.management.base import BaseCommand

from assessment.models import Question


class Command(BaseCommand):
    help = "Export questions to JSON list for import_questions command."

    def add_arguments(self, parser):
        parser.add_argument("out_file", type=str)
        parser.add_argument("--skill-id", type=int, default=None)

    def handle(self, *args, **options):
        qs = Question.objects.select_related("skill").order_by("skill_id", "id")
        if options["skill_id"]:
            qs = qs.filter(skill_id=options["skill_id"])
        rows = []
        for q in qs:
            rows.append(
                {
                    "skill_id": q.skill_id,
                    "skill_name": q.skill.name,
                    "text": q.text,
                    "option_a": q.option_a,
                    "option_b": q.option_b,
                    "option_c": q.option_c,
                    "option_d": q.option_d,
                    "correct_option": q.correct_option,
                    "difficulty": q.difficulty,
                    "concept_tag": q.concept_tag,
                    "explanation": q.explanation or "",
                }
            )
        with open(options["out_file"], "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(rows)} questions to {options['out_file']}"))
