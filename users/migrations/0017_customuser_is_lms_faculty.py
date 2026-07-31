from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0016_customuser_role_faculty"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="is_lms_faculty",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "Grants LMS batch-teaching access (own courses/students only), independent "
                    "of is_staff (which only controls /sd/ Django admin access). Auto-set True "
                    "the first time this user is assigned ownership of an LmsCourse."
                ),
            ),
        ),
    ]
