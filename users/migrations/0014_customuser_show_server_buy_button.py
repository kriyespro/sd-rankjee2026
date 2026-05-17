from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0013_customuser_role_vip_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="show_server_buy_button",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="If set, student sees “Server buy now” on dashboard and can open server checkout.",
            ),
        ),
    ]
