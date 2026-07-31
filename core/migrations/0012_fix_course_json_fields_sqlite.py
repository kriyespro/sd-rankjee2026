# Fixes a real bug in 0010_course_page_content_json on SQLite: that migration calls
# schema_editor.add_field() in a loop reusing a single stale `apps.get_model(...)` reference.
# On SQLite, JSONField requires a CHECK(JSON_VALID(...)) constraint, which forces Django to
# _remake_table() (rebuild-and-copy) on every add_field() call. Because the loop's model
# reference never picks up fields added by earlier iterations, each rebuild is based on the
# state *before* this RunPython started — so later iterations silently drop columns added by
# earlier ones (non-deterministic: sometimes only the last field survives, sometimes it raises
# a CHECK constraint IntegrityError entirely, depending on existing row data).
#
# This never affected production (Postgres ADD COLUMN doesn't need a table rebuild, so 0010's
# loop works fine there) — it only bites a fresh SQLite database (e.g. a new dev clone, or the
# test runner's in-memory DB), where `core_course` silently ends up missing some/all of
# course_includes/gain_outcomes/gain_perks/hero_usps.
#
# Fix: on SQLite only, add any still-missing columns with plain `ALTER TABLE ... ADD COLUMN`
# raw SQL (no CHECK constraint, so no remake, so no data loss). No-op everywhere the columns
# already exist (real production Postgres, or a dev SQLite db that already has them).

from django.db import migrations


def add_missing_json_columns_sqlite(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return  # Postgres already has these columns via 0010 — nothing to fix there.

    table = apps.get_model("core", "Course")._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}

    for name in ("course_includes", "gain_outcomes", "gain_perks", "hero_usps"):
        if name in existing:
            continue
        schema_editor.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" text NULL')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_referrallinkclick"),
    ]

    operations = [
        migrations.RunPython(add_missing_json_columns_sqlite, noop_reverse),
    ]
