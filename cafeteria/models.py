from django.db import models


class Product(models.Model):
    CATEGORY_COFFEE = "Cafés"
    CATEGORY_COLD_DRINKS = "Bebidas Frías"
    CATEGORY_SNACKS = "Snacks"
    CATEGORY_DESSERTS = "Postres"

    CATEGORY_CHOICES = (
        (CATEGORY_COFFEE, CATEGORY_COFFEE),
        (CATEGORY_COLD_DRINKS, CATEGORY_COLD_DRINKS),
        (CATEGORY_SNACKS, CATEGORY_SNACKS),
        (CATEGORY_DESSERTS, CATEGORY_DESSERTS),
    )

    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class FrequentClient(models.Model):
    dni = models.CharField(max_length=8, primary_key=True)
    saldo_cafes = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["dni"]

    def __str__(self) -> str:
        return self.dni


class Promotion(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    discount = models.PositiveIntegerField()
    conditions = models.CharField(max_length=255)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"Orden #{self.pk}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    product_name = models.CharField(max_length=100)
    product_category = models.CharField(max_length=30)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product_name} x{self.quantity}"
