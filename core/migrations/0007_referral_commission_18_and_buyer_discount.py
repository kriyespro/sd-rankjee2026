from decimal import Decimal

from django.db import migrations, models


def pending_referrals_use_18_percent(apps, schema_editor):
    CourseReferral = apps.get_model("core", "CourseReferral")
    CourseReferral.objects.filter(status="PENDING").update(commission_percent=Decimal("18.00"))


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_course_orders_and_purchases"),
    ]

    operations = [
        migrations.RunPython(pending_referrals_use_18_percent, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="coursereferral",
            name="commission_percent",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("18.00"),
                max_digits=5,
            ),
        ),
    ]
