from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("SalesAndTransport", "0010_godowntransaction"),
    ]

    operations = [
        migrations.CreateModel(
            name="PurchaseOrderSequence",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("year", models.PositiveIntegerField(unique=True)),
                ("next_serial", models.PositiveIntegerField(default=1)),
            ],
            options={
                "db_table": "purchase_order_sequence",
            },
        ),
    ]