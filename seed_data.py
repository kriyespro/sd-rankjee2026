"""
Seed script: creates Digital Marketing skill, 10 questions, 3 videos, and 3 earning tasks.
Usage: python seed_data.py
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from assessment.models import Skill, Question
from learning.models import ConceptVideo
from core.models import EarningTask

# ── Skill ──────────────────────────────────────────────────
skill, _ = Skill.objects.get_or_create(
    name="Digital Marketing",
    defaults={'description': 'Master SEO, Social Media, Affiliate Marketing and more.'}
)
print("Skill ready:", skill.name)

# ── Questions ──────────────────────────────────────────────
questions_data = [
    {'concept_tag': 'SEO', 'difficulty': 'EASY',
     'text': 'What does SEO stand for?',
     'option_a': 'Search Engine Optimization', 'option_b': 'Social Engagement Outreach',
     'option_c': 'Site Efficiency Operations', 'option_d': 'Search Experience Online',
     'correct_option': 'A'},
    {'concept_tag': 'SEO', 'difficulty': 'EASY',
     'text': 'Which of the following is a white-hat SEO technique?',
     'option_a': 'Keyword stuffing', 'option_b': 'Cloaking',
     'option_c': 'Writing quality content', 'option_d': 'Hidden text',
     'correct_option': 'C'},
    {'concept_tag': 'SEO', 'difficulty': 'MEDIUM',
     'text': 'What is the primary purpose of a meta description?',
     'option_a': 'Increase page speed', 'option_b': 'Summarize page content for search results',
     'option_c': 'Store cookie data', 'option_d': 'Define CSS styles',
     'correct_option': 'B'},
    {'concept_tag': 'Social Media', 'difficulty': 'EASY',
     'text': 'Which platform is best for B2B lead generation?',
     'option_a': 'TikTok', 'option_b': 'Snapchat',
     'option_c': 'LinkedIn', 'option_d': 'Pinterest',
     'correct_option': 'C'},
    {'concept_tag': 'Social Media', 'difficulty': 'EASY',
     'text': 'What does CTR stand for in digital marketing?',
     'option_a': 'Click To Rate', 'option_b': 'Click Through Rate',
     'option_c': 'Content Transfer Ratio', 'option_d': 'Campaign Tracking Report',
     'correct_option': 'B'},
    {'concept_tag': 'Social Media', 'difficulty': 'MEDIUM',
     'text': 'What is the recommended image size for Facebook posts?',
     'option_a': '800x600', 'option_b': '1200x628',
     'option_c': '720x1280', 'option_d': '400x400',
     'correct_option': 'B'},
    {'concept_tag': 'Affiliate Marketing', 'difficulty': 'EASY',
     'text': 'What is affiliate marketing?',
     'option_a': 'Selling your own products online',
     'option_b': 'Earning commission by promoting other companies\' products',
     'option_c': 'Running paid advertisements', 'option_d': 'Building an email list',
     'correct_option': 'B'},
    {'concept_tag': 'Affiliate Marketing', 'difficulty': 'EASY',
     'text': 'Which of the following is a popular affiliate marketplace?',
     'option_a': 'Shopify', 'option_b': 'Amazon Associates',
     'option_c': 'Google Ads', 'option_d': 'Mailchimp',
     'correct_option': 'B'},
    {'concept_tag': 'Email Marketing', 'difficulty': 'EASY',
     'text': 'What is the key metric used to measure email campaign success?',
     'option_a': 'Bounce Rate', 'option_b': 'Domain Authority',
     'option_c': 'Open Rate', 'option_d': 'Page Views',
     'correct_option': 'C'},
    {'concept_tag': 'Email Marketing', 'difficulty': 'MEDIUM',
     'text': 'What is a good email open rate for most industries?',
     'option_a': '5-10%', 'option_b': '15-25%',
     'option_c': '50-60%', 'option_d': '70-80%',
     'correct_option': 'B'},
]

for qd in questions_data:
    Question.objects.get_or_create(
        skill=skill, text=qd['text'],
        defaults={k: v for k, v in qd.items() if k != 'text'}
    )
print(f"Questions: {Question.objects.filter(skill=skill).count()}")

# ── Learning Videos ────────────────────────────────────────
videos_data = [
    {'concept_tag': 'SEO', 'title': 'SEO Basics in 5 Minutes', 'video_url': 'https://www.youtube.com/watch?v=LVV_93mBfSU', 'duration_seconds': 300},
    {'concept_tag': 'Social Media', 'title': 'Social Media Strategy Crash Course', 'video_url': 'https://www.youtube.com/watch?v=OiVgeBDPqnI', 'duration_seconds': 480},
    {'concept_tag': 'Affiliate Marketing', 'title': 'Affiliate Marketing for Beginners', 'video_url': 'https://www.youtube.com/watch?v=RrTQ65bimXQ', 'duration_seconds': 600},
    {'concept_tag': 'Email Marketing', 'title': 'Email Marketing Quick Start', 'video_url': 'https://www.youtube.com/watch?v=6b5p2m6Lfkg', 'duration_seconds': 420},
]
for vd in videos_data:
    ConceptVideo.objects.get_or_create(concept_tag=vd['concept_tag'], title=vd['title'], defaults=vd)
print(f"Videos: {ConceptVideo.objects.count()}")

# ── Earning Tasks ──────────────────────────────────────────
tasks_data = [
    {'title': 'Share RankJee on LinkedIn', 'description': 'Post about RankJee on your LinkedIn profile. Include a screenshot of your progress.', 'reward_amount': 50},
    {'title': 'Refer a Friend', 'description': 'Get a friend to sign up using your referral link. Submit their username as proof.', 'reward_amount': 100},
    {'title': 'Write a Product Review', 'description': 'Write a 200-word review of any affiliate product and share the link.', 'reward_amount': 150},
]
for td in tasks_data:
    EarningTask.objects.get_or_create(
        title=td['title'],
        defaults={**td, 'required_skill': skill, 'is_active': True}
    )
print(f"Earning Tasks: {EarningTask.objects.count()}")
print("\n✅ Seed complete!")
