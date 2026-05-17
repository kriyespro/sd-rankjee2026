# Course page JSON fields — idempotent (safe if columns already exist on Postgres)

from django.db import migrations, models


def _existing_columns(schema_editor, table_name: str) -> set[str]:
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = CURRENT_SCHEMA()
                  AND table_name = %s
                """,
                [table_name],
            )
            return {row[0] for row in cursor.fetchall()}
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {row[1] for row in cursor.fetchall()}


def add_page_content_fields_if_missing(apps, schema_editor):
    Course = apps.get_model("core", "Course")
    table = Course._meta.db_table
    existing = _existing_columns(schema_editor, table)

    fields = [
        models.JSONField(
            blank=True,
            default=list,
            help_text='"This course includes" list on mobile buy card. JSON array of strings.',
        ),
        models.JSONField(
            blank=True,
            default=list,
            help_text='Left card "What you\'ll gain" lines. JSON array of strings.',
        ),
        models.JSONField(
            blank=True,
            default=list,
            help_text="Left card perk lines (3 recommended). JSON array of strings.",
        ),
        models.JSONField(
            blank=True,
            default=list,
            help_text='Hero bullet lines. JSON array of strings. Use **text** for bold.',
        ),
    ]
    names = ("course_includes", "gain_outcomes", "gain_perks", "hero_usps")

    for name, field in zip(names, fields):
        if name in existing:
            continue
        field.set_attributes_from_name(name)
        schema_editor.add_field(Course, field)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_course_salary_curriculum_testimonials"),
    ]

    operations = [
        migrations.RunPython(add_page_content_fields_if_missing, noop_reverse),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
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
            ],
        ),
    ]
