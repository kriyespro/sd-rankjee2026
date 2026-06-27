from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0010_course_page_content_json"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReferralLinkClick",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("path", models.CharField(blank=True, max_length=200)),
                ("session_key", models.CharField(blank=True, db_index=True, max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "course",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="referral_link_clicks",
                        to="core.course",
                    ),
                ),
                (
                    "referrer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referral_link_clicks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["referrer", "-created_at"], name="core_referr_referre_0a8f0d_idx"),
                ],
            },
        ),
    ]
