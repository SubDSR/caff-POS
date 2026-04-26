from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def quantize_amount(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def serialize_product(product: dict) -> dict:
    return {
        "id": str(product["id"]),
        "name": product["name"],
        "price": float(product["price"]),
        "category": product["category"],
    }


def add_or_increment_cart_item(cart: list[dict], product: dict) -> None:
    product_id = str(product["id"])
    for item in cart:
        if item["id"] == product_id:
            item["quantity"] += 1
            return

    cart.append({**serialize_product(product), "quantity": 1})


def update_cart_quantity(cart: list[dict], product_id: str, quantity: int) -> tuple[list[dict], str]:
    updated_cart: list[dict] = []
    removed_name = ""
    for item in cart:
        if item["id"] != product_id:
            updated_cart.append(item)
            continue

        if quantity > 0:
            updated_cart.append({**item, "quantity": quantity})
        else:
            removed_name = item["name"]

    return updated_cart, removed_name


def remove_cart_item(cart: list[dict], product_id: str) -> tuple[list[dict], str]:
    remaining_items: list[dict] = []
    removed_name = ""
    for item in cart:
        if item["id"] == product_id:
            removed_name = item["name"]
            continue

        remaining_items.append(item)

    return remaining_items, removed_name


def cart_subtotal(cart: list[dict]) -> Decimal:
    return sum((Decimal(str(item["price"])) * item["quantity"] for item in cart), Decimal("0"))


def get_first_cart_item_by_category(cart: list[dict], category: str) -> dict | None:
    return next((item for item in cart if item["category"] == category), None)


def enrich_cart_items(items: list[dict]) -> list[dict]:
    enriched_items: list[dict] = []
    for item in items:
        line_total = quantize_amount(Decimal(str(item["price"])) * item["quantity"])
        enriched_items.append({**item, "line_total": line_total})
    return enriched_items


def cart_totals(cart_items: list[dict], discount: float | Decimal) -> dict[str, Decimal]:
    subtotal = sum((Decimal(str(item["price"])) * item["quantity"] for item in cart_items), Decimal("0"))
    subtotal = quantize_amount(subtotal)
    discount_percentage = Decimal(str(discount))
    discount_amount = quantize_amount(subtotal * (discount_percentage / Decimal("100")))
    total = quantize_amount(subtotal - discount_amount)
    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "total": total,
    }
