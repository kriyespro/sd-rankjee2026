import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import EarningTask
from assessment.models import Skill

def seed_tasks():
    # If no skills exist, just use None
    skills = list(Skill.objects.filter(is_active=True))
    base_skill = skills[0] if skills else None

    tasks = [
        {
            "title": "Review SkillLoop App on ProductHunt",
            "description": "Leave an honest 5-star review on our ProductHunt launch page and share the screenshot link.",
            "reward_amount": 100,
            "auto_approve_domain": "producthunt.com"
        },
        {
            "title": "Share Your Score on Twitter",
            "description": "Tweet your latest test score tag @SkillLoop. Submit the tweet URL.",
            "reward_amount": 50,
            "auto_approve_domain": "twitter.com"
        },
        {
            "title": "Write a Medium Post",
            "description": "Write a short 300-word post about your learning experience here. Submit the Medium link.",
            "reward_amount": 250,
            "auto_approve_domain": "medium.com"
        },
        {
            "title": "Subscribe to our YouTube Channel",
            "description": "Subscribe and comment on our latest video. Submit your channel link.",
            "reward_amount": 20,
            "auto_approve_domain": "youtube.com"
        },
        {
            "title": "Join our official Discord Server",
            "description": "Join the community and introduce yourself in #general. Submit your Discord username.",
            "reward_amount": 30,
            "auto_approve_domain": ""
        }
    ]

    for t in tasks:
        task_obj, created = EarningTask.objects.get_or_create(
            title=t["title"],
            defaults={
                "description": t["description"],
                "reward_amount": t["reward_amount"],
                "auto_approve_domain": t["auto_approve_domain"],
                "required_skill": base_skill # Attaching to first skill so users who passed it can see it
            }
        )
        if created:
            print(f"Created Task: {task_obj.title}")
        else:
            print(f"Task exists: {task_obj.title}")

if __name__ == "__main__":
    seed_tasks()
