from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.urls import path
from django.http import HttpResponse
import csv, io, json, random, requests
from django.conf import settings
from .models import SkillPath, Skill, Question, UserAttempt, QuestionSet, UserSetAttempt


class CsvImportForm:
    pass


@admin.register(SkillPath)
class SkillPathAdmin(admin.ModelAdmin):
    list_display = ('name', 'level_order', 'is_active')
    list_editable = ('level_order', 'is_active')

from django.db import models # for Case/When

@admin.register(QuestionSet)
class QuestionSetAdmin(admin.ModelAdmin):
    list_display = ('name', 'skill', 'order', 'is_active')
    list_filter = ('skill', 'is_active')
    list_editable = ('order', 'is_active')

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('order', 'name', 'path', 'is_active')
    list_editable = ('order', 'is_active')
    list_display_links = ('name',)
    list_filter = ('path', 'is_active')
    actions = ['partition_into_sets']

    @admin.action(description="Partition Questions into Sets of 10")
    def partition_into_sets(self, request, queryset):
        for skill in queryset:
            skill.partition_questions()
            
        self.message_user(request, f"Successfully partitioned {queryset.count()} skill(s) into sets.", level=messages.SUCCESS)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'skill', 'concept_tag', 'difficulty', 'correct_option')
    list_filter = ('skill', 'difficulty', 'concept_tag')
    change_list_template = "assessment/question_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-csv/', self.import_csv, name='assessment_question_import_csv'),
            path('ai-generate/', self.ai_generate, name='assessment_question_ai_generate'),
        ]
        return custom + urls

    def import_csv(self, request):
        if request.method == 'POST':
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                self.message_user(request, "No file selected.", level=messages.ERROR)
                return redirect('..')
            decoded = csv_file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded))
            created = 0
            errors = []
            for i, row in enumerate(reader, 2):
                try:
                    skill, _ = Skill.objects.get_or_create(
                        name=row['skill_name'].strip(),
                        defaults={'description': row['skill_name'].strip()}
                    )
                    Question.objects.get_or_create(
                        skill=skill,
                        text=row['text'].strip(),
                        defaults={
                            'concept_tag': row.get('concept_tag', '').strip(),
                            'difficulty': row.get('difficulty', 'EASY').strip().upper(),
                            'option_a': row.get('option_a', '').strip(),
                            'option_b': row.get('option_b', '').strip(),
                            'option_c': row.get('option_c', '').strip(),
                            'option_d': row.get('option_d', '').strip(),
                            'correct_option': row.get('correct_option', 'A').strip().upper(),
                        }
                    )
                    created += 1
                except Exception as e:
                    errors.append(f"Row {i}: {e}")
            
            # UNIQUE: Auto-partition after import
            all_skills = Skill.objects.filter(name__in=[row['skill_name'].strip() for row in reader if 'skill_name' in row])
            for s in all_skills:
                s.partition_questions()
                
            msg = f"Imported {created} question(s) and auto-partitioned into sets."
            if errors:
                msg += " Errors: " + "; ".join(errors[:3])
            self.message_user(request, msg, level=messages.SUCCESS if not errors else messages.WARNING)
            return redirect('..')

        # GET — show upload form
        return render(request, 'assessment/csv_import.html', {'title': 'Import Questions CSV'})

    def download_template(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="questions_template.csv"'
        writer = csv.writer(response)
        writer.writerow(['skill_name', 'concept_tag', 'difficulty', 'text',
                         'option_a', 'option_b', 'option_c', 'option_d', 'correct_option'])
        writer.writerow(['Digital Marketing', 'SEO', 'EASY', 'What is SEO?',
                         'Search Engine Optimization', 'Social Engagement Outreach',
                         'Site Error Observer', 'Smart Encoding Option', 'A'])
        return response

    def ai_generate(self, request):
        if request.method == 'POST':
            skill_id = request.POST.get('skill')
            topic = request.POST.get('topic')
            count_str = request.POST.get('count', '5')
            try:
                count = int(count_str)
                skill = Skill.objects.get(pk=skill_id)
            except Exception as e:
                self.message_user(request, "Invalid input.", level=messages.ERROR)
                return redirect('..')

            # OpenRouter API call
            OPENROUTER_KEY = "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"
            models = [
                "google/gemma-3-27b-it:free",
                "meta-llama/llama-3.3-70b-instruct:free",
                "openrouter/free"
            ]
            selected_model = random.choice(models)

            prompt = f"""
Generate {count} multiple choice questions about "{topic}" for the skill "{skill.name}".
Provide mixed difficulties (EASY, MEDIUM, HARD).
Return exactly valid JSON with no markdown formatting, structured strictly as:
[
  {{
    "concept_tag": "{topic}",
    "difficulty": "EASY",
    "text": "Question text?",
    "option_a": "A",
    "option_b": "B",
    "option_c": "C",
    "option_d": "D",
    "correct_option": "B"
  }}
]
"""
            try:
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_KEY.strip()}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://127.0.0.1:8000/",
                    "X-Title": "SkillLoop Local"
                }
                data = {
                    "model": selected_model,
                    "messages": [{"role": "user", "content": prompt}]
                }
                resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=30)
                if resp.status_code == 401:
                    self.message_user(request, "AI generation failed: 401 Unauthorized. Your OpenRouter API key is invalid or revoked. Please update OPENROUTER_KEY in assessment/admin.py.", level=messages.ERROR)
                    return redirect('..')
                resp.raise_for_status()
                result = resp.json()
                content = result['choices'][0]['message']['content'].strip()
                # Clean up potential markdown formatting code blocks
                if content.startswith("```json"): content = content[7:]
                if content.startswith("```"): content = content[3:]
                if content.endswith("```"): content = content[:-3]
                content = content.strip()
                
                qs_data = json.loads(content)
                created = 0
                for qd in qs_data:
                    Question.objects.create(
                        skill=skill,
                        text=qd['text'],
                        concept_tag=qd.get('concept_tag', topic),
                        difficulty=qd.get('difficulty', 'EASY'),
                        option_a=qd['option_a'],
                        option_b=qd['option_b'],
                        option_c=qd['option_c'],
                        option_d=qd['option_d'],
                        correct_option=qd['correct_option'],
                    )
                    created += 1
                
                # UNIQUE: Auto-partition after generation
                skill.partition_questions()
                
                self.message_user(request, f"Successfully generated {created} questions and added them to levels via {selected_model}.", level=messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f"AI generation failed: {str(e)}", level=messages.ERROR)
            return redirect('..')

        skills = Skill.objects.filter(is_active=True).order_by('name')
        return render(request, 'assessment/ai_generate.html', {
            'title': 'AI Generate MCQs',
            'skills': skills,
        }, using='django')

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-csv/', self.import_csv, name='assessment_question_import_csv'),
            path('ai-generate/', self.ai_generate, name='assessment_question_ai_generate'),
            path('download-template/', self.download_template, name='assessment_question_download_template'),
        ]
        return custom + urls


@admin.register(UserSetAttempt)
class UserSetAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'question_set', 'score', 'passed', 'attempt_date')
    list_filter = ('passed', 'question_set__skill')

