from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .models import FrequentClient, Order, OrderItem, Product, Promotion


PRESET_DISCOUNTS = [5, 10, 15, 20, 25, 50]


def _quantize_amount(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _serialize_product(product: Product) -> dict:
    return {
        "id": str(product.pk),
        "name": product.name,
        "price": float(product.price),
        "category": product.category,
    }


def _redirect_to_index(request: HttpRequest, **overrides: str) -> HttpResponse:
    return redirect(_index_url_with_state(request, **overrides))


def _get_products(search_query: str, selected_category: str | None):
    products = Product.objects.all()
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | Q(category__icontains=search_query)
        )
    if selected_category:
        products = products.filter(category=selected_category)
    return products


def _add_or_increment_cart_item(cart: list[dict], product: Product) -> None:
    for item in cart:
        if item["id"] == str(product.pk):
            item["quantity"] += 1
            return

    cart.append({**_serialize_product(product), "quantity": 1})


def _update_cart_quantity(cart: list[dict], product_id: str, quantity: int) -> tuple[list[dict], str]:
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


def _remove_cart_item(cart: list[dict], product_id: str) -> tuple[list[dict], str]:
    remaining_items: list[dict] = []
    removed_name = ""
    for item in cart:
        if item["id"] == product_id:
            removed_name = item["name"]
            continue

        remaining_items.append(item)

    return remaining_items, removed_name


def _cart_subtotal(cart: list[dict]) -> Decimal:
    return sum((Decimal(str(item["price"])) * item["quantity"] for item in cart), Decimal("0"))


def _get_first_cart_item_by_category(cart: list[dict], category: str) -> dict | None:
    return next((item for item in cart if item["category"] == category), None)


def login_view(request: HttpRequest) -> HttpResponse:
    if request.session.get("is_logged_in"):
        return redirect("cafeteria:index")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        if username and password:
            request.session["is_logged_in"] = True
            request.session.modified = True
            messages.success(request, "Sesión iniciada correctamente")
            return redirect("cafeteria:index")
        messages.error(request, "Debe ingresar usuario y contraseña")

    return render(request, "cafeteria/login.html")


def logout_view(request: HttpRequest) -> HttpResponse:
    request.session["is_logged_in"] = False
    request.session.modified = True
    messages.info(request, "Sesión cerrada")
    return redirect("cafeteria:login")


def _get_cart(request: HttpRequest) -> list[dict]:
    return list(request.session.get("cart", []))


def _set_cart(request: HttpRequest, cart: list[dict]) -> None:
    request.session["cart"] = cart
    request.session.modified = True


def _get_last_order_id(request: HttpRequest) -> int | None:
    return request.session.get("last_order_id")


def _set_last_order_id(request: HttpRequest, order_id: int | None) -> None:
    request.session["last_order_id"] = order_id
    request.session.modified = True


def _get_discount(request: HttpRequest) -> float:
    return float(request.session.get("discount", 0))


def _set_discount(request: HttpRequest, discount: float | Decimal) -> None:
    normalized = round(max(0, min(float(discount), 100)), 2)
    request.session["discount"] = normalized
    request.session.modified = True


def _enrich_cart_items(items: list[dict]) -> list[dict]:
    enriched_items: list[dict] = []
    for item in items:
        line_total = _quantize_amount(Decimal(str(item["price"])) * item["quantity"])
        enriched_items.append({**item, "line_total": line_total})
    return enriched_items


def _cart_totals(cart_items: list[dict], discount: float | Decimal) -> dict[str, Decimal]:
    subtotal = sum((Decimal(str(item["price"])) * item["quantity"] for item in cart_items), Decimal("0"))
    subtotal = _quantize_amount(subtotal)
    discount_percentage = Decimal(str(discount))
    discount_amount = _quantize_amount(subtotal * (discount_percentage / Decimal("100")))
    total = _quantize_amount(subtotal - discount_amount)
    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "total": total,
    }


def _get_query_state(request: HttpRequest) -> dict[str, str]:
    search_query = request.GET.get("q") or request.POST.get("q") or ""
    selected_category = request.GET.get("category") or request.POST.get("category") or ""
    modal = request.GET.get("modal") or request.POST.get("modal") or ""
    return {
        "q": search_query.strip(),
        "category": selected_category.strip(),
        "modal": modal.strip(),
    }


def _index_url_with_state(request: HttpRequest, **overrides: str) -> str:
    state = _get_query_state(request)
    for key, value in overrides.items():
        state[key] = value
    cleaned_state = {key: value for key, value in state.items() if value}
    base_url = reverse("cafeteria:index")
    return f"{base_url}?{urlencode(cleaned_state)}" if cleaned_state else base_url


def _set_modal_feedback(request: HttpRequest, feedback_type: str, text: str) -> None:
    request.session["modal_feedback"] = {
        "type": feedback_type,
        "text": text,
    }
    request.session.modified = True


def _pop_modal_feedback(request: HttpRequest) -> dict | None:
    if "modal_feedback" not in request.session:
        return None

    return request.session.pop("modal_feedback")


def _build_repeat_cart_from_order(order: Order) -> list[dict]:
    return [
        {
            "id": str(item.product_id),
            "name": item.product_name,
            "price": float(item.unit_price),
            "category": item.product_category,
            "quantity": item.quantity,
        }
        for item in order.items.select_related("product").all()
    ]


def index(request: HttpRequest) -> HttpResponse:
    if not request.session.get("is_logged_in"):
        return redirect("cafeteria:login")

    state = _get_query_state(request)
    search_query = state["q"]
    selected_category = state["category"] or None
    modal = state["modal"]

    products = _get_products(search_query, selected_category)

    categories = [choice[0] for choice in Product.CATEGORY_CHOICES]
    last_order_id = _get_last_order_id(request)
    can_repeat_order = bool(last_order_id and Order.objects.filter(pk=last_order_id).exists())

    discount = _get_discount(request)
    cart_items = _enrich_cart_items(_get_cart(request))
    totals = _cart_totals(cart_items, discount)

    context = {
        "base_state_url": _index_url_with_state(request, modal=""),
        "all_products_url": _index_url_with_state(request, category="", modal=""),
        "category_urls": {
            category: _index_url_with_state(request, category=category, modal="")
            for category in categories
        },
        "frequent_client_modal_url": _index_url_with_state(request, modal="frequent-client"),
        "discount_modal_url": _index_url_with_state(request, modal="discount"),
        "promotion_modal_url": _index_url_with_state(request, modal="promotion"),
        "products": products,
        "categories": categories,
        "preset_discounts": PRESET_DISCOUNTS,
        "selected_category": selected_category,
        "search_query": search_query,
        "modal": modal,
        "promotions": Promotion.objects.all(),
        "cart_items": cart_items,
        "cart_count": len(cart_items),
        "discount": discount,
        "can_repeat_order": can_repeat_order,
        "modal_feedback": _pop_modal_feedback(request),
        **totals,
    }
    return render(request, "cafeteria/index.html", context)


def add_to_cart(request: HttpRequest, product_id: str) -> HttpResponse:
    if request.method != "POST":
        return redirect("cafeteria:index")

    product = Product.objects.filter(pk=product_id).first()
    if product is None:
        messages.error(request, "Producto no encontrado.")
        return _redirect_to_index(request)

    cart = _get_cart(request)
    _add_or_increment_cart_item(cart, product)

    _set_cart(request, cart)
    messages.success(request, f"{product.name} agregado al carrito")
    return _redirect_to_index(request)


def update_cart_item(request: HttpRequest, product_id: str) -> HttpResponse:
    if request.method != "POST":
        return redirect("cafeteria:index")

    try:
        quantity = int(request.POST.get("quantity", "1"))
    except ValueError:
        quantity = 1

    updated_cart, removed_name = _update_cart_quantity(_get_cart(request), product_id, quantity)

    _set_cart(request, updated_cart)
    if removed_name:
        messages.info(request, f"{removed_name} eliminado del carrito")
    return _redirect_to_index(request)


def remove_cart_item(request: HttpRequest, product_id: str) -> HttpResponse:
    if request.method != "POST":
        return redirect("cafeteria:index")

    remaining_items, removed_name = _remove_cart_item(_get_cart(request), product_id)

    _set_cart(request, remaining_items)
    if removed_name:
        messages.info(request, f"{removed_name} eliminado del carrito")
    return _redirect_to_index(request)


def clear_cart(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        _set_cart(request, [])
        _set_discount(request, 0)
        messages.info(request, "Carrito anulado")
    return _redirect_to_index(request)


def repeat_order(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("cafeteria:index")

    last_order_id = _get_last_order_id(request)
    if not last_order_id:
        messages.error(request, "No hay orden anterior para repetir")
        return _redirect_to_index(request)

    order = Order.objects.prefetch_related("items").filter(pk=last_order_id).first()
    if order is None or not order.items.exists():
        messages.error(request, "No hay orden anterior para repetir")
        return _redirect_to_index(request)

    _set_cart(request, _build_repeat_cart_from_order(order))
    _set_discount(request, 0)
    messages.success(request, "Orden repetida")
    return _redirect_to_index(request)


def checkout(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("cafeteria:index")

    cart = _get_cart(request)
    if not cart:
        return _redirect_to_index(request)

    discount = _get_discount(request)
    totals = _cart_totals(cart, discount)

    with transaction.atomic():
        order = Order.objects.create(
            subtotal=totals["subtotal"],
            discount_percentage=Decimal(str(discount)),
            discount_amount=totals["discount_amount"],
            total=totals["total"],
        )

        products = Product.objects.in_bulk(int(item["id"]) for item in cart)
        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    product=products[int(item["id"])],
                    product_name=item["name"],
                    product_category=item["category"],
                    unit_price=Decimal(str(item["price"])),
                    quantity=item["quantity"],
                    line_total=_quantize_amount(Decimal(str(item["price"])) * item["quantity"]),
                )
                for item in cart
            ]
        )

    _set_last_order_id(request, order.pk)
    _set_cart(request, [])
    _set_discount(request, 0)
    messages.success(
        request,
        f"Orden realizada. Total: S/ {totals['total']:.2f}. Comprobante generado exitosamente.",
    )
    return redirect(_index_url_with_state(request))


def apply_frequent_client_benefit(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(_index_url_with_state(request, modal="frequent-client"))

    dni = "".join(character for character in request.POST.get("dni", "") if character.isdigit())[:8]
    cart = _get_cart(request)

    client = FrequentClient.objects.filter(pk=dni).first()
    if client is None:
        _set_modal_feedback(request, "error", "Cliente no registrado en el sistema")
        return _redirect_to_index(request, modal="frequent-client")

    if client.saldo_cafes <= 0:
        _set_modal_feedback(request, "warning", "Cliente sin saldo de cafés disponibles")
        return _redirect_to_index(request, modal="frequent-client")

    coffee_in_cart = _get_first_cart_item_by_category(cart, Product.CATEGORY_COFFEE)
    if coffee_in_cart is None:
        _set_modal_feedback(request, "error", "Debe tener al menos un café en el carrito")
        return _redirect_to_index(request, modal="frequent-client")

    subtotal = _cart_subtotal(cart)
    if subtotal <= 0:
        _set_modal_feedback(request, "error", "El carrito está vacío")
        return _redirect_to_index(request, modal="frequent-client")

    coffee_discount_percentage = (Decimal(str(coffee_in_cart["price"])) / subtotal) * Decimal("100")

    with transaction.atomic():
        client.saldo_cafes -= 1
        client.save(update_fields=["saldo_cafes"])

    _set_discount(request, _get_discount(request) + float(coffee_discount_percentage))
    _set_modal_feedback(
        request,
        "success",
        f"Beneficio aplicado. Saldo restante: {client.saldo_cafes} café(s)",
    )
    return _redirect_to_index(request, modal="frequent-client")


def apply_discount(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(_index_url_with_state(request, modal="discount"))

    raw_discount = request.POST.get("preset_discount") or request.POST.get("discount_custom", "0")

    try:
        discount = float(raw_discount)
    except ValueError:
        discount = 0

    if 0 <= discount <= 100:
        _set_discount(request, discount)
        messages.success(request, f"Descuento de {discount:.2f}% aplicado")
    else:
        _set_modal_feedback(request, "error", "El descuento debe estar entre 0 y 100")
        return _redirect_to_index(request, modal="discount")

    return _redirect_to_index(request)


def remove_discount(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        _set_discount(request, 0)
        messages.info(request, "Descuento retirado")
    return _redirect_to_index(request)


def apply_promotion(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(_index_url_with_state(request, modal="promotion"))

    promotion_id = request.POST.get("promotion_id", "")
    promotion = Promotion.objects.filter(pk=promotion_id).first()
    if promotion is None:
        messages.error(request, "Promoción no encontrada")
        return _redirect_to_index(request, modal="promotion")

    _set_discount(request, promotion.discount)
    messages.success(request, f'Promoción "{promotion.name}" aplicada')
    return _redirect_to_index(request)
