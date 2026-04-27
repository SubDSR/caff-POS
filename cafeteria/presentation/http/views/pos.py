from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from cafeteria.application.navigation import (
    get_query_state,
    index_url_with_state,
    pop_modal_feedback,
    redirect_to_index,
    set_modal_feedback,
)
from cafeteria.application.session import (
    clear_discount_state,
    get_cart,
    get_discount,
    get_discount_entries,
    get_last_order_id,
    get_repeat_source_order_id,
    set_cart,
    set_discount,
    set_discount_entries,
    set_last_order_id,
    set_repeat_source_order_id,
)
from cafeteria.domain.cart import (
    add_or_increment_cart_item,
    cart_subtotal,
    cart_totals,
    enrich_cart_items,
    get_first_cart_item_by_category,
    remove_cart_item as remove_cart_item_from_cart,
    update_cart_quantity,
)
from cafeteria.domain.constants import CATEGORY_COFFEE, PRESET_DISCOUNTS, PRODUCT_CATEGORIES
from cafeteria.infrastructure.persistence.mysql import catalog


def _get_checkout_dni_cliente(discount_entries: list[dict]) -> str | None:
    for entry in reversed(discount_entries):
        if entry.get("type") == "cliente_frecuente" and entry.get("dni_cliente"):
            return str(entry["dni_cliente"])
    return None


def index(request: HttpRequest) -> HttpResponse:
    if not request.session.get("is_logged_in"):
        return redirect("cafeteria:login")

    state = get_query_state(request)
    search_query = state["q"]
    selected_category = state["category"] or None
    modal = state["modal"]

    try:
        products, promotions = catalog.get_index_catalog_data(
            search_query=search_query,
            selected_category=selected_category,
        )
    except catalog.MySQLCatalogError:
        products = []
        promotions = []
        messages.error(request, "No se pudo cargar el catálogo y promociones desde MySQL")

    last_order_id = get_last_order_id(request)
    try:
        can_repeat_order = bool(last_order_id and catalog.order_exists(last_order_id))
    except catalog.MySQLCatalogError:
        can_repeat_order = False

    discount = get_discount(request)
    cart_items = enrich_cart_items(get_cart(request))
    totals = cart_totals(cart_items, discount)

    context = {
        "base_state_url": index_url_with_state(request, modal=""),
        "all_products_url": index_url_with_state(request, category="", modal=""),
        "category_urls": {
            category: index_url_with_state(request, category=category, modal="")
            for category in PRODUCT_CATEGORIES
        },
        "frequent_client_modal_url": index_url_with_state(request, modal="frequent-client"),
        "discount_modal_url": index_url_with_state(request, modal="discount"),
        "promotion_modal_url": index_url_with_state(request, modal="promotion"),
        "products": products,
        "categories": PRODUCT_CATEGORIES,
        "preset_discounts": PRESET_DISCOUNTS,
        "selected_category": selected_category,
        "search_query": search_query,
        "modal": modal,
        "promotions": promotions,
        "cart_items": cart_items,
        "cart_count": len(cart_items),
        "discount": discount,
        "can_repeat_order": can_repeat_order,
        "modal_feedback": pop_modal_feedback(request),
        **totals,
    }
    return render(request, "cafeteria/pages/index.html", context)


def add_to_cart(request: HttpRequest, product_id: str) -> HttpResponse:
    if request.method != "POST":
        return redirect("cafeteria:index")

    try:
        product = catalog.get_product_by_id(product_id)
    except catalog.MySQLCatalogError:
        messages.error(request, "No se pudo consultar el producto en MySQL.")
        return redirect_to_index(request)

    if product is None:
        messages.error(request, "Producto no encontrado.")
        return redirect_to_index(request)

    cart = get_cart(request)
    add_or_increment_cart_item(cart, product)

    set_cart(request, cart)
    messages.success(request, f"{product['name']} agregado al carrito")
    return redirect_to_index(request)


def update_cart_item(request: HttpRequest, product_id: str) -> HttpResponse:
    if request.method != "POST":
        return redirect("cafeteria:index")

    try:
        quantity = int(request.POST.get("quantity", "1"))
    except ValueError:
        quantity = 1

    updated_cart, removed_name = update_cart_quantity(get_cart(request), product_id, quantity)

    set_cart(request, updated_cart)
    if removed_name:
        messages.info(request, f"{removed_name} eliminado del carrito")
    return redirect_to_index(request)


def remove_cart_item(request: HttpRequest, product_id: str) -> HttpResponse:
    if request.method != "POST":
        return redirect("cafeteria:index")

    remaining_items, removed_name = remove_cart_item_from_cart(get_cart(request), product_id)

    set_cart(request, remaining_items)
    if removed_name:
        messages.info(request, f"{removed_name} eliminado del carrito")
    return redirect_to_index(request)


def clear_cart(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        set_cart(request, [])
        clear_discount_state(request)
        set_repeat_source_order_id(request, None)
        messages.info(request, "Carrito anulado")
    return redirect_to_index(request)


def repeat_order(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("cafeteria:index")

    last_order_id = get_last_order_id(request)
    if not last_order_id:
        messages.error(request, "No hay orden anterior para repetir")
        return redirect_to_index(request)

    try:
        order_items = catalog.get_order_items_for_repeat(last_order_id)
    except catalog.MySQLCatalogError:
        messages.error(request, "No se pudo consultar la orden anterior en MySQL")
        return redirect_to_index(request)

    if not order_items:
        messages.error(request, "No hay orden anterior para repetir")
        return redirect_to_index(request)

    set_cart(request, order_items)
    clear_discount_state(request)
    set_repeat_source_order_id(request, last_order_id)
    messages.success(request, "Orden repetida")
    return redirect_to_index(request)


def checkout(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("cafeteria:index")

    cart = get_cart(request)
    if not cart:
        return redirect_to_index(request)

    discount = get_discount(request)
    discount_entries = get_discount_entries(request)
    totals = cart_totals(cart, discount)

    try:
        order_id = catalog.create_order(
            cart,
            Decimal(str(discount)),
            totals,
            dni_cliente=_get_checkout_dni_cliente(discount_entries),
            orden_anterior_id=get_repeat_source_order_id(request),
            discount_entries=discount_entries,
        )
    except catalog.MySQLCatalogError:
        messages.error(request, "No se pudo registrar la orden en MySQL")
        return redirect_to_index(request)

    set_last_order_id(request, order_id)
    set_cart(request, [])
    clear_discount_state(request)
    set_repeat_source_order_id(request, None)
    messages.success(
        request,
        f"Orden realizada. Total: S/ {totals['total']:.2f}. Comprobante generado exitosamente.",
    )
    return redirect(index_url_with_state(request))


def apply_frequent_client_benefit(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(index_url_with_state(request, modal="frequent-client"))

    dni = "".join(character for character in request.POST.get("dni", "") if character.isdigit())[:8]
    cart = get_cart(request)

    try:
        client = catalog.get_frequent_client(dni)
    except catalog.MySQLCatalogError:
        set_modal_feedback(request, "error", "No se pudo consultar el cliente en MySQL")
        return redirect_to_index(request, modal="frequent-client")

    if client is None:
        set_modal_feedback(request, "error", "Cliente no registrado en el sistema")
        return redirect_to_index(request, modal="frequent-client")

    if int(client["saldo_cafes"]) <= 0:
        set_modal_feedback(request, "warning", "Cliente sin saldo de cafés disponibles")
        return redirect_to_index(request, modal="frequent-client")

    coffee_in_cart = get_first_cart_item_by_category(cart, CATEGORY_COFFEE)
    if coffee_in_cart is None:
        set_modal_feedback(request, "error", "Debe tener al menos un café en el carrito")
        return redirect_to_index(request, modal="frequent-client")

    subtotal = cart_subtotal(cart)
    if subtotal <= 0:
        set_modal_feedback(request, "error", "El carrito está vacío")
        return redirect_to_index(request, modal="frequent-client")

    coffee_discount_percentage = (Decimal(str(coffee_in_cart["price"])) / subtotal) * Decimal("100")

    try:
        new_balance = catalog.decrement_frequent_client_balance(dni)
    except catalog.MySQLCatalogError:
        set_modal_feedback(request, "error", "No se pudo actualizar el saldo del cliente en MySQL")
        return redirect_to_index(request, modal="frequent-client")

    if new_balance is None:
        set_modal_feedback(request, "error", "Cliente no registrado en el sistema")
        return redirect_to_index(request, modal="frequent-client")

    if new_balance <= 0 and int(client["saldo_cafes"]) <= 0:
        set_modal_feedback(request, "warning", "Cliente sin saldo de cafés disponibles")
        return redirect_to_index(request, modal="frequent-client")

    set_discount(request, get_discount(request) + float(coffee_discount_percentage))
    set_discount_entries(
        request,
        [
            *get_discount_entries(request),
            {
                "type": "cliente_frecuente",
                "pct": float(coffee_discount_percentage),
                "dni_cliente": dni,
            },
        ],
    )
    set_modal_feedback(
        request,
        "success",
        f"Beneficio aplicado. Saldo restante: {new_balance} café(s)",
    )
    return redirect_to_index(request, modal="frequent-client")


def apply_discount(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(index_url_with_state(request, modal="discount"))

    raw_discount = request.POST.get("preset_discount") or request.POST.get("discount_custom", "0")

    try:
        discount = float(raw_discount)
    except ValueError:
        discount = 0

    if 0 <= discount <= 100:
        set_discount(request, discount)
        set_discount_entries(request, [{"type": "manual", "pct": discount}])
        messages.success(request, f"Descuento de {discount:.2f}% aplicado")
    else:
        set_modal_feedback(request, "error", "El descuento debe estar entre 0 y 100")
        return redirect_to_index(request, modal="discount")

    return redirect_to_index(request)


def remove_discount(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        clear_discount_state(request)
        messages.info(request, "Descuento retirado")
    return redirect_to_index(request)


def apply_promotion(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(index_url_with_state(request, modal="promotion"))

    promotion_id = request.POST.get("promotion_id", "")
    try:
        promotion = catalog.get_promotion_by_id(promotion_id)
    except catalog.MySQLCatalogError:
        messages.error(request, "No se pudo consultar la promoción en MySQL")
        return redirect_to_index(request, modal="promotion")

    if promotion is None:
        messages.error(request, "Promoción no encontrada")
        return redirect_to_index(request, modal="promotion")

    set_discount(request, promotion["discount"])
    set_discount_entries(
        request,
        [{"type": "promocion", "pct": promotion["discount"], "promotion_id": promotion["id"]}],
    )
    messages.success(request, f'Promoción "{promotion["name"]}" aplicada')
    return redirect_to_index(request)
