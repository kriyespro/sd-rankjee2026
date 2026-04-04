"""
Export SkillPaths, Skills, and Questions to a portable JSON file (no DB ids required on import).
Usage:
  python manage.py export_content_bundle backup.json
  python manage.py export_content_bundle backup.json --path-id 4
"""
import json
from django.core.management.base import BaseCommand

from assessment.models import SkillPath, Skill, Question


class Command(BaseCommand):
    help = "Export assessment content (paths, skills, questions) to JSON for import elsewhere."

    def add_arguments(self, parser):
        parser.add_argument("out_file", type=str, help="Output JSON path")
        parser.add_argument(
            "--path-id",
            type=int,
            default=None,
            help="Only export this SkillPath id (default: all active paths)",
        )

    def handle(self, *args, **options):
        path_qs = SkillPath.objects.filter(is_active=True).order_by("level_order", "id")
        if options["path_id"]:
            path_qs = path_qs.filter(id=options["path_id"])

        bundle = {"export_version": 1, "paths": []}

        for path in path_qs:
            path_entry = {
                "name": path.name,
                "description": path.description or "",
                "level_order": path.level_order,
                "is_active": path.is_active,
                "skills": [],
            }
            skills = Skill.objects.filter(path=path, is_active=True).order_by("order", "id")
            for skill in skills:
                qs = []
                for q in skill.questions.all().order_by("id"):
                    qs.append(
                        {
                            "text": q.text,
                            "concept_tag": q.concept_tag,
                            "explanation": q.explanation or "",
                            "difficulty": q.difficulty,
                            "option_a": q.option_a,
                            "option_b": q.option_b,
                            "option_c": q.option_c,
                            "option_d": q.option_d,
                            "correct_option": q.correct_option,
                        }
                    )
                path_entry["skills"].append(
                    {
                        "name": skill.name,
                        "description": skill.description or "",
                        "order": skill.order,
                        "is_active": skill.is_active,
                        "questions": qs,
                    }
                )
            bundle["paths"].append(path_entry)

        # Skills not linked to any path (still used in "Other Assessments" etc.)
        loose = Skill.objects.filter(path__isnull=True, is_active=True).order_by("order", "id")
        if loose.exists():
            bundle["unassigned_skills"] = []
            for skill in loose:
                qs = []
                for q in skill.questions.all().order_by("id"):
                    qs.append(
                        {
                            "text": q.text,
                            "concept_tag": q.concept_tag,
                            "explanation": q.explanation or "",
                            "difficulty": q.difficulty,
                            "option_a": q.option_a,
                            "option_b": q.option_b,
                            "option_c": q.option_c,
                            "option_d": q.option_d,
                            "correct_option": q.correct_option,
                        }
                    )
                bundle["unassigned_skills"].append(
                    {
                        "name": skill.name,
                        "description": skill.description or "",
                        "order": skill.order,
                        "is_active": skill.is_active,
                        "questions": qs,
                    }
                )

        out = options["out_file"]
        with open(out, "w", encoding="utf-8") as f:
            json.dump(bundle, f, ensure_ascii=False, indent=2)

        n_skills = sum(len(p["skills"]) for p in bundle["paths"])
        n_q = sum(
            len(s["questions"])
            for p in bundle["paths"]
            for s in p["skills"]
        )
        if bundle.get("unassigned_skills"):
            n_skills += len(bundle["unassigned_skills"])
            n_q += sum(len(s["questions"]) for s in bundle["unassigned_skills"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {out}: {len(bundle['paths'])} path(s), {n_skills} skill(s), {n_q} question(s)."
            )
        )
