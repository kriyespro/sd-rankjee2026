from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0012_customuser_onboarding_completed"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="role",
            field=models.CharField(
                choices=[
                    ("STUDENT", "Student"),
                    ("PARENT", "Parent"),
                    ("TUTOR", "Tutor"),
                    ("VIP_USER", "VIP user"),
                    ("CITY_ADMIN", "City admin"),
                    ("GLOBAL_ADMIN", "Global admin"),
                ],
                db_index=True,
                default="STUDENT",
                max_length=20,
            ),
        ),
    ]
