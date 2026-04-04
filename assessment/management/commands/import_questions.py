import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from assessment.models import Skill, Question

class Command(BaseCommand):
    help = 'Imports questions from a JSON file into the assessment app'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='Path to the JSON file containing questions')

    def handle(self, *args, **options):
        json_file_path = options['json_file']

        if not os.path.exists(json_file_path):
            raise CommandError(f'File "{json_file_path}" does not exist.')

        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            raise CommandError(f'Failed to parse JSON file: {e}')

        if not isinstance(data, list):
            raise CommandError('JSON data must be a list of question objects.')

        total_imported = 0
        skills_to_partition = set()

        self.stdout.write(self.style.NOTICE(f'Starting import of {len(data)} questions...'))

        with transaction.atomic():
            for item in data:
                try:
                    skill = None
                    skill_id = item.get("skill_id")
                    skill_name = (item.get("skill_name") or "").strip()
                    if skill_id is not None:
                        skill = Skill.objects.filter(id=skill_id).first()
                    if skill is None and skill_name:
                        skill = Skill.objects.filter(name__iexact=skill_name).first()
                    if skill is None:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skip: need valid skill_id or skill_name (got id={skill_id!r}, name={skill_name!r})."
                            )
                        )
                        continue
                    
                    question = Question.objects.create(
                        skill=skill,
                        text=item['text'],
                        option_a=item['option_a'],
                        option_b=item['option_b'],
                        option_c=item['option_c'],
                        option_d=item['option_d'],
                        correct_option=item['correct_option'],
                        difficulty=item.get('difficulty', 'EASY'),
                        concept_tag=item.get('concept_tag', 'General'),
                        explanation=item.get('explanation', '')
                    )
                    total_imported += 1
                    skills_to_partition.add(skill)
                except KeyError as e:
                    self.stdout.write(self.style.WARNING(f"Missing required field {e}, skipping question."))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error importing question: {e}"))

        self.stdout.write(self.style.SUCCESS(f'Successfully imported {total_imported} questions.'))

        self.stdout.write(self.style.NOTICE('Re-partitioning skills...'))
        for skill in skills_to_partition:
            sets_created = skill.partition_questions()
            self.stdout.write(f'Skill "{skill.name}" partitioned into {sets_created} sets.')

        self.stdout.write(self.style.SUCCESS('Batch process completed.'))
