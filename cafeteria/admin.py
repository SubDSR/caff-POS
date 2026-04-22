from django.contrib import admin

from .models import FrequentClient, Order, OrderItem, Product, Promotion


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "price")
    list_filter = ("category",)
    search_fields = ("name",)


@admin.register(FrequentClient)
class FrequentClientAdmin(admin.ModelAdmin):
    list_display = ("dni", "saldo_cafes")
    search_fields = ("dni",)


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "discount")
    search_fields = ("name",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "product_category", "unit_price", "quantity", "line_total")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "subtotal", "discount_percentage", "discount_amount", "total")
    readonly_fields = ("created_at", "subtotal", "discount_percentage", "discount_amount", "total")
    inlines = [OrderItemInline]
