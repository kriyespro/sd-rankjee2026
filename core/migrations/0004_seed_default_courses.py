from django.db import migrations
from django.utils.text import slugify


def seed_courses(apps, schema_editor):
    Course = apps.get_model("core", "Course")
    defaults = [
        {
            "title": "Digital Marketing Growth Sprint",
            "short_description": "Run paid + organic campaigns that convert.",
            "description": "Hands-on funnels, ad creatives, analytics, and conversion optimization.",
            "price_inr": "4999.00",
            "duration_weeks": 6,
            "level": "Beginner",
            "is_featured": True,
        },
        {
            "title": "Python for Jobs Bootcamp",
            "short_description": "Python fundamentals to portfolio projects.",
            "description": "Build practical scripts, APIs, and interview-ready mini projects.",
            "price_inr": "6999.00",
            "duration_weeks": 8,
            "level": "Beginner",
            "is_featured": True,
        },
        {
            "title": "Data Analytics with Excel + SQL",
            "short_description": "Learn dashboards, SQL queries, and reporting workflows.",
            "description": "From raw data cleaning to stakeholder dashboards and insights.",
            "price_inr": "5999.00",
            "duration_weeks": 7,
            "level": "Intermediate",
            "is_featured": True,
        },
        {
            "title": "AI Tools for Freelancers",
            "short_description": "Use AI to deliver faster and win high-value clients.",
            "description": "Prompt design, content workflows, automation, and service packaging.",
            "price_inr": "3999.00",
            "duration_weeks": 4,
            "level": "All levels",
            "is_featured": False,
        },
        {
            "title": "Sales & Communication Mastery",
            "short_description": "Close more clients with confident communication.",
            "description": "Discovery calls, objection handling, and conversion scripts for revenue growth.",
            "price_inr": "4499.00",
            "duration_weeks": 5,
            "level": "Intermediate",
            "is_featured": False,
        },
    ]
    for row in defaults:
        slug = slugify(row["title"])[:180] or "course"
        candidate = slug
        i = 1
        while Course.objects.filter(slug=candidate).exists():
            i += 1
            candidate = f"{slug}-{i}"[:200]
        row_with_slug = dict(row)
        row_with_slug["slug"] = candidate
        Course.objects.get_or_create(slug=candidate, defaults=row_with_slug)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_course_coursereferral"),
    ]

    operations = [
        migrations.RunPython(seed_courses, migrations.RunPython.noop),
    ]

