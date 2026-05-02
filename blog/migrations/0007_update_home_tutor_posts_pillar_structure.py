from django.db import migrations

from blog.migrations._home_tutor_pillar_bodies import BODIES, EXCERPTS_META


def apply_pillar_bodies(apps, schema_editor):
    BlogPost = apps.get_model("blog", "BlogPost")
    for slug, body in BODIES.items():
        meta = EXCERPTS_META.get(slug)
        if not meta:
            continue
        BlogPost.objects.filter(slug=slug).update(
            body=body,
            excerpt=meta["excerpt"],
            meta_description=meta["meta_description"][:320],
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0006_update_jee_at_home_blueprint_structure"),
    ]

    operations = [
        migrations.RunPython(apply_pillar_bodies, noop_reverse),
    ]
