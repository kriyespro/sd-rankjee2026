from django.db import migrations
from django.utils import timezone


def seed_initial_blog_content(apps, schema_editor):
    BlogCategory = apps.get_model("blog", "BlogCategory")
    BlogPost = apps.get_model("blog", "BlogPost")

    category, _ = BlogCategory.objects.get_or_create(
        slug="exam-strategy",
        defaults={"name": "Exam Strategy"},
    )

    BlogPost.objects.get_or_create(
        slug="jee-main-30-day-study-plan",
        defaults={
            "title": "JEE Main 30-Day Study Plan (Daily Action Blueprint)",
            "excerpt": "A practical 30-day JEE Main plan with mock-test rhythm, revision loop, and score-improving daily checklist.",
            "body": (
                "Preparing for JEE Main in 30 days needs one clear loop: learn, test, fix, repeat.\n\n"
                "Start each morning with one high-weight chapter and solve 25-30 mixed questions in timed mode.\n\n"
                "In the afternoon, review errors from yesterday's test and create a short mistake notebook.\n\n"
                "In the evening, attempt one mini mock and spend at least the same time in analysis.\n\n"
                "Every 7th day, run a full-length mock test and track topic-wise accuracy, not only rank.\n\n"
                "Use tutor support for weak chapters and keep your plan realistic with fixed sleep and break slots.\n\n"
                "The goal is not finishing all chapters. The goal is maximizing correct attempts in your strongest topics while reducing avoidable negative marks."
            ),
            "category_id": category.id,
            "meta_title": "JEE Main 30-Day Study Plan: Daily Mock + Revision Strategy",
            "meta_description": "Follow this 30-day JEE Main preparation strategy with a daily schedule, mock test cycle, and revision system to improve score quickly.",
            "published_at": timezone.now(),
        },
    )


def unseed_initial_blog_content(apps, schema_editor):
    BlogPost = apps.get_model("blog", "BlogPost")
    BlogPost.objects.filter(slug="jee-main-30-day-study-plan").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_initial_blog_content, unseed_initial_blog_content),
    ]
