from decimal import Decimal

from django.db import migrations, models


def seed_initial_data(apps, schema_editor):
    Product = apps.get_model("cafeteria", "Product")
    FrequentClient = apps.get_model("cafeteria", "FrequentClient")
    Promotion = apps.get_model("cafeteria", "Promotion")

    Product.objects.bulk_create(
        [
            Product(id=1, name="Espresso", price=Decimal("6.50"), category="Cafés"),
            Product(id=2, name="Cappuccino", price=Decimal("8.00"), category="Cafés"),
            Product(id=3, name="Latte", price=Decimal("8.50"), category="Cafés"),
            Product(id=4, name="Americano", price=Decimal("7.00"), category="Cafés"),
            Product(id=5, name="Mocha", price=Decimal("9.50"), category="Cafés"),
            Product(id=6, name="Frappé de Café", price=Decimal("12.00"), category="Bebidas Frías"),
            Product(id=7, name="Smoothie de Frutas", price=Decimal("11.00"), category="Bebidas Frías"),
            Product(id=8, name="Limonada Frozen", price=Decimal("9.00"), category="Bebidas Frías"),
            Product(id=9, name="Croissant", price=Decimal("6.00"), category="Snacks"),
            Product(id=10, name="Sándwich de Pollo", price=Decimal("14.00"), category="Snacks"),
            Product(id=11, name="Ensalada Cesar", price=Decimal("15.00"), category="Snacks"),
            Product(id=12, name="Brownie", price=Decimal("7.50"), category="Postres"),
            Product(id=13, name="Cheesecake", price=Decimal("10.00"), category="Postres"),
            Product(id=14, name="Tarta de Manzana", price=Decimal("9.00"), category="Postres"),
        ]
    )

    FrequentClient.objects.bulk_create(
        [
            FrequentClient(dni="12345678", saldo_cafes=5),
            FrequentClient(dni="87654321", saldo_cafes=3),
            FrequentClient(dni="11111111", saldo_cafes=0),
            FrequentClient(dni="22222222", saldo_cafes=10),
        ]
    )

    Promotion.objects.bulk_create(
        [
            Promotion(id=1, name="2x1 en Cafés", discount=50, conditions="Válido en compras de 2 o más cafés del mismo tipo"),
            Promotion(id=2, name="Combo Desayuno", discount=20, conditions="Café + Croissant: 20% de descuento"),
            Promotion(id=3, name="Happy Hour", discount=30, conditions="De 3pm a 5pm: 30% en bebidas frías"),
        ]
    )


def remove_initial_data(apps, schema_editor):
    Product = apps.get_model("cafeteria", "Product")
    FrequentClient = apps.get_model("cafeteria", "FrequentClient")
    Promotion = apps.get_model("cafeteria", "Promotion")

    Product.objects.all().delete()
    FrequentClient.objects.all().delete()
    Promotion.objects.all().delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="FrequentClient",
            fields=[
                ("dni", models.CharField(max_length=8, primary_key=True, serialize=False)),
                ("saldo_cafes", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ["dni"]},
        ),
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("subtotal", models.DecimalField(decimal_places=2, max_digits=10)),
                ("discount_percentage", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("discount_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("total", models.DecimalField(decimal_places=2, max_digits=10)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("price", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "category",
                    models.CharField(
                        choices=[("Cafés", "Cafés"), ("Bebidas Frías", "Bebidas Frías"), ("Snacks", "Snacks"), ("Postres", "Postres")],
                        max_length=30,
                    ),
                ),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="Promotion",
            fields=[
                ("id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("discount", models.PositiveIntegerField()),
                ("conditions", models.CharField(max_length=255)),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product_name", models.CharField(max_length=100)),
                ("product_category", models.CharField(max_length=30)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("line_total", models.DecimalField(decimal_places=2, max_digits=10)),
                ("order", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="items", to="cafeteria.order")),
                ("product", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="order_items", to="cafeteria.product")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.RunPython(seed_initial_data, remove_initial_data),
    ]
