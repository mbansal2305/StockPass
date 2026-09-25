from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("StockPassCore", "0004_alter_user_profile_picture"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
    ]