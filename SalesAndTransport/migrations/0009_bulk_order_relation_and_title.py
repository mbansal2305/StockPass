from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("SalesAndTransport", "0008_alter_broker_city_alter_broker_name_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bulktransport",
            name="title",
            field=models.CharField(
                db_index=True,
                default="Bulk Transport",
                max_length=100,
            ),
        ),
    ]