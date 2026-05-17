# Generated manually for course page JSON content fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_course_salary_curriculum_testimonials"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="course_includes",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='"This course includes" list on mobile buy card. JSON array of strings.',
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="gain_outcomes",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Left card "What you\'ll gain" lines. JSON array of strings.',
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="gain_perks",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Left card perk lines (3 recommended). JSON array of strings.",
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="hero_usps",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Hero bullet lines. JSON array of strings. Use **text** for bold. Example: ["**6 modules** covering AI agents"]',
            ),
        ),
    ]
