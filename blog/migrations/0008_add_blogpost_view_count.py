from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0007_update_home_tutor_posts_pillar_structure"),
    ]

    operations = [
        migrations.AddField(
            model_name="blogpost",
            name="view_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
