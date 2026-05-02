from django.db import migrations
from django.utils import timezone


def seed_more_blog_posts(apps, schema_editor):
    BlogCategory = apps.get_model("blog", "BlogCategory")
    BlogPost = apps.get_model("blog", "BlogPost")

    category, _ = BlogCategory.objects.get_or_create(
        slug="exam-strategy",
        defaults={"name": "Exam Strategy"},
    )

    BlogPost.objects.get_or_create(
        slug="neet-45-day-revision-plan",
        defaults={
            "title": "NEET 45-Day Revision Plan (Biology-First Score Strategy)",
            "excerpt": "A 45-day NEET revision blueprint with smart Biology weighting, mock analysis routine, and daily confidence loop.",
            "body": (
                "The fastest NEET score gains usually come from consistency and error reduction, not random long study hours.\n\n"
                "Keep Biology as your daily anchor with NCERT line-by-line revision and short active recall blocks.\n\n"
                "Pair Physics and Chemistry in timed practice sets so your brain adapts to exam pressure.\n\n"
                "Follow a fixed cycle: chapter revise, timed questions, error log, and same-day correction.\n\n"
                "Take full mocks every 5 to 7 days and spend extra time on post-test analysis.\n\n"
                "Track your weak areas by topic, then assign tutor-led doubt sessions for repeated mistakes.\n\n"
                "In the final week, focus on accuracy and speed balance instead of learning brand-new heavy chapters."
            ),
            "category_id": category.id,
            "meta_title": "NEET 45-Day Revision Plan: Biology + Mock Test Strategy",
            "meta_description": "Use this NEET 45-day revision strategy to improve score with NCERT-focused Biology, timed practice, and mock-test analysis.",
            "published_at": timezone.now(),
        },
    )

    BlogPost.objects.get_or_create(
        slug="class-10-board-exam-last-30-days-plan",
        defaults={
            "title": "Class 10 Board Exam: Last 30 Days Plan for Higher Marks",
            "excerpt": "A practical Class 10 board prep plan for the final 30 days with subject rotation, writing practice, and score tracking.",
            "body": (
                "The final 30 days before board exams should be structured, measurable, and low-stress.\n\n"
                "Start with a daily subject rotation: one scoring subject, one conceptual subject, one revision slot.\n\n"
                "Practice writing full answers within time limits so your exam speed matches your preparation quality.\n\n"
                "Use previous-year questions to identify repeated patterns in long-answer and case-based sections.\n\n"
                "Reserve one hour daily for formula, theorem, grammar, and map-based quick revision.\n\n"
                "Every weekend, run a mini test and compare accuracy against your past attempt to measure progress.\n\n"
                "Keep sleep, breaks, and hydration steady; stable routines improve memory retention better than late-night cramming."
            ),
            "category_id": category.id,
            "meta_title": "Class 10 Board Exam Last 30 Days Plan (High Score Strategy)",
            "meta_description": "Follow this Class 10 board exam 30-day study plan with timed writing practice, PYQ revision, and weekly score tracking.",
            "published_at": timezone.now(),
        },
    )


def unseed_more_blog_posts(apps, schema_editor):
    BlogPost = apps.get_model("blog", "BlogPost")
    BlogPost.objects.filter(
        slug__in=[
            "neet-45-day-revision-plan",
            "class-10-board-exam-last-30-days-plan",
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0002_seed_initial_blog_content"),
    ]

    operations = [
        migrations.RunPython(seed_more_blog_posts, unseed_more_blog_posts),
    ]
