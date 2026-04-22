import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assessment", "0009_question_is_video_import_question_source_video"),
        ("learning", "0004_revision_bites"),
    ]

    operations = [
        migrations.AddField(
            model_name="userattempt",
            name="attempted_video",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="attempts",
                to="learning.conceptvideo",
            ),
        ),
    ]
