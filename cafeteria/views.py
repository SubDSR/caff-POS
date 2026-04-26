from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .mysql_client import (
    MySQLCatalogError,
    create_order,
    decrement_frequent_client_balance,
    get_frequent_client,
    get_order_items_for_repeat,
    get_pos_account_by_email,
    get_product_by_id,
    get_promotion_by_id,
    list_products,
    list_promotions,
    order_exists,
    touch_pos_account_access,
)


PRESET_DISCOUNTS = [5, 10, 15, 20, 25, 50]
CATEGORY_COFFEE = "Cafés"
PRODUCT_CATEGORIES = (
    CATEGORY_COFFEE,
    "Bebidas Frías",
    "Snacks",
    "Postres",
)


def _quantize_amount(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _serialize_product(product: dict) -> dict:
    return {
        "id": str(product["id"]),
        "name": product["name"],
        "price": float(product["price"]),
        "category": product["category"],
    }


def _redirect_to_index(request: HttpRequest, **overrides: str) -> HttpResponse:
    return redirect(_index_url_with_state(request, **overrides))


def _get_products(search_query: str, selected_category: str | None) -> list[dict]:
    return list_products(search_query=search_query, selected_category=selected_category)


def _add_or_increment_cart_item(cart: list[dict], product: dict) -> None:
    product_id = str(product["id"])
    for item in cart:
        if item["id"] == product_id:
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
            try:
                account = get_pos_account_by_email(username)
            except MySQLCatalogError:
                messages.error(request, "No se pudo conectar a la base de datos MySQL")
                return render(request, "cafeteria/login.html")

            if account and account["activa"] and check_password(password, account["password_hash"]):
                try:
                    touch_pos_account_access(account["correo"])
                except MySQLCatalogError:
                    messages.warning(request, "Se inició sesión, pero no se pudo registrar el último acceso")

                request.session["is_logged_in"] = True
                request.session["pos_account_email"] = account["correo"]
                request.session["pos_module_name"] = account["nombre_modulo"]
                request.session.modified = True
                messages.success(request, "Sesión iniciada correctamente")
                return redirect("cafeteria:index")

            messages.error(request, "Credenciales inválidas")
        else:
            messages.error(request, "Debe ingresar correo y contraseña")

    return render(request, "cafeteria/login.html")


def logout_view(request: HttpRequest) -> HttpResponse:
    request.session["is_logged_in"] = False
    request.session.pop("pos_account_email", None)
    request.session.pop("pos_module_name", None)
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


def _get_repeat_source_order_id(request: HttpRequest) -> int | None:
    return request.session.get("repeat_source_order_id")


def _set_repeat_source_order_id(request: HttpRequest, order_id: int | None) -> None:
    if order_id is None:
        request.session.pop("repeat_source_order_id", None)
    else:
        request.session["repeat_source_order_id"] = order_id
    request.session.modified = True


def _get_discount(request: HttpRequest) -> float:
    return float(request.session.get("discount", 0))


def _set_discount(request: HttpRequest, discount: float | Decimal) -> None:
    normalized = round(max(0, min(float(discount), 100)), 2)
    request.session["discount"] = normalized
    request.session.modified = True


def _get_discount_entries(request: HttpRequest) -> list[dict]:
    return list(request.session.get("discount_entries", []))


def _set_discount_entries(request: HttpRequest, entries: list[dict]) -> None:
    request.session["discount_entries"] = entries
    request.session.modified = True


def _clear_discount_state(request: HttpRequest) -> None:
    _set_discount(request, 0)
    _set_discount_entries(request, [])


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


def _get_checkout_dni_cliente(discount_entries: list[dict]) -> str | None:
    for entry in reversed(discount_entries):
        if entry.get("type") == "cliente_frecuente" and entry.get("dni_cliente"):
            return str(entry["dni_cliente"])
    return None


def index(request: HttpRequest) -> HttpResponse:
    if not request.session.get("is_logged_in"):
        return redirect("cafeteria:login")

    state = _get_query_state(request)
    search_query = state["q"]
    selected_category = state["category"] or None
    modal = state["modal"]

    try:
        products = _get_products(search_query, selected_category)
    except MySQLCatalogError:
        products = []
        messages.error(request, "No se pudo cargar el catálogo desde MySQL")

    try:
        promotions = list_promotions()
    except MySQLCatalogError:
        promotions = []
        messages.error(request, "No se pudo cargar las promociones desde MySQL")

    last_order_id = _get_last_order_id(request)
    try:
        can_repeat_order = bool(last_order_id and order_exists(last_order_id))
    except MySQLCatalogError:
        can_repeat_order = False

    discount = _get_discount(request)
    cart_items = _enrich_cart_items(_get_cart(request))
    totals = _cart_totals(cart_items, discount)

    context = {
        "base_state_url": _index_url_with_state(request, modal=""),
        "all_products_url": _index_url_with_state(request, category="", modal=""),
        "category_urls": {
            category: _index_url_with_state(request, category=category, modal="")
            for category in PRODUCT_CATEGORIES
        },
        "frequent_client_modal_url": _index_url_with_state(request, modal="frequent-client"),
        "discount_modal_url": _index_url_with_state(request, modal="discount"),
        "promotion_modal_url": _index_url_with_state(request, modal="promotion"),
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
        "modal_feedback": _pop_modal_feedback(request),
        **totals,
    }
    return render(request, "cafeteria/index.html", context)


def add_to_cart(request: HttpRequest, product_id: str) -> HttpResponse:
    if request.method != "POST":
        return redirect("cafeteria:index")

    try:
        product = get_product_by_id(product_id)
    except MySQLCatalogError:
        messages.error(request, "No se pudo consultar el producto en MySQL.")
        return _redirect_to_index(request)

    if product is None:
        messages.error(request, "Producto no encontrado.")
        return _redirect_to_index(request)

    cart = _get_cart(request)
    _add_or_increment_cart_item(cart, product)

    _set_cart(request, cart)
    messages.success(request, f"{product['name']} agregado al carrito")
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
        _clear_discount_state(request)
        _set_repeat_source_order_id(request, None)
        messages.info(request, "Carrito anulado")
    return _redirect_to_index(request)


def repeat_order(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("cafeteria:index")

    last_order_id = _get_last_order_id(request)
    if not last_order_id:
        messages.error(request, "No hay orden anterior para repetir")
        return _redirect_to_index(request)

    try:
        order_items = get_order_items_for_repeat(last_order_id)
    except MySQLCatalogError:
        messages.error(request, "No se pudo consultar la orden anterior en MySQL")
        return _redirect_to_index(request)

    if not order_items:
        messages.error(request, "No hay orden anterior para repetir")
        return _redirect_to_index(request)

    _set_cart(request, order_items)
    _clear_discount_state(request)
    _set_repeat_source_order_id(request, last_order_id)
    messages.success(request, "Orden repetida")
    return _redirect_to_index(request)


def checkout(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("cafeteria:index")

    cart = _get_cart(request)
    if not cart:
        return _redirect_to_index(request)

    discount = _get_discount(request)
    discount_entries = _get_discount_entries(request)
    totals = _cart_totals(cart, discount)

    try:
        order_id = create_order(
            cart,
            Decimal(str(discount)),
            totals,
            dni_cliente=_get_checkout_dni_cliente(discount_entries),
            orden_anterior_id=_get_repeat_source_order_id(request),
            discount_entries=discount_entries,
        )
    except MySQLCatalogError:
        messages.error(request, "No se pudo registrar la orden en MySQL")
        return _redirect_to_index(request)

    _set_last_order_id(request, order_id)
    _set_cart(request, [])
    _clear_discount_state(request)
    _set_repeat_source_order_id(request, None)
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

    try:
        client = get_frequent_client(dni)
    except MySQLCatalogError:
        _set_modal_feedback(request, "error", "No se pudo consultar el cliente en MySQL")
        return _redirect_to_index(request, modal="frequent-client")

    if client is None:
        _set_modal_feedback(request, "error", "Cliente no registrado en el sistema")
        return _redirect_to_index(request, modal="frequent-client")

    if int(client["saldo_cafes"]) <= 0:
        _set_modal_feedback(request, "warning", "Cliente sin saldo de cafés disponibles")
        return _redirect_to_index(request, modal="frequent-client")

    coffee_in_cart = _get_first_cart_item_by_category(cart, CATEGORY_COFFEE)
    if coffee_in_cart is None:
        _set_modal_feedback(request, "error", "Debe tener al menos un café en el carrito")
        return _redirect_to_index(request, modal="frequent-client")

    subtotal = _cart_subtotal(cart)
    if subtotal <= 0:
        _set_modal_feedback(request, "error", "El carrito está vacío")
        return _redirect_to_index(request, modal="frequent-client")

    coffee_discount_percentage = (Decimal(str(coffee_in_cart["price"])) / subtotal) * Decimal("100")

    try:
        new_balance = decrement_frequent_client_balance(dni)
    except MySQLCatalogError:
        _set_modal_feedback(request, "error", "No se pudo actualizar el saldo del cliente en MySQL")
        return _redirect_to_index(request, modal="frequent-client")

    if new_balance is None:
        _set_modal_feedback(request, "error", "Cliente no registrado en el sistema")
        return _redirect_to_index(request, modal="frequent-client")

    if new_balance <= 0 and int(client["saldo_cafes"]) <= 0:
        _set_modal_feedback(request, "warning", "Cliente sin saldo de cafés disponibles")
        return _redirect_to_index(request, modal="frequent-client")

    _set_discount(request, _get_discount(request) + float(coffee_discount_percentage))
    _set_discount_entries(
        request,
        [
            *_get_discount_entries(request),
            {
                "type": "cliente_frecuente",
                "pct": float(coffee_discount_percentage),
                "dni_cliente": dni,
            },
        ],
    )
    _set_modal_feedback(
        request,
        "success",
        f"Beneficio aplicado. Saldo restante: {new_balance} café(s)",
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
        _set_discount_entries(request, [{"type": "manual", "pct": discount}])
        messages.success(request, f"Descuento de {discount:.2f}% aplicado")
    else:
        _set_modal_feedback(request, "error", "El descuento debe estar entre 0 y 100")
        return _redirect_to_index(request, modal="discount")

    return _redirect_to_index(request)


def remove_discount(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        _clear_discount_state(request)
        messages.info(request, "Descuento retirado")
    return _redirect_to_index(request)


def apply_promotion(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(_index_url_with_state(request, modal="promotion"))

    promotion_id = request.POST.get("promotion_id", "")
    try:
        promotion = get_promotion_by_id(promotion_id)
    except MySQLCatalogError:
        messages.error(request, "No se pudo consultar la promoción en MySQL")
        return _redirect_to_index(request, modal="promotion")

    if promotion is None:
        messages.error(request, "Promoción no encontrada")
        return _redirect_to_index(request, modal="promotion")

    _set_discount(request, promotion["discount"])
    _set_discount_entries(
        request,
        [{"type": "promocion", "pct": promotion["discount"], "promotion_id": promotion["id"]}],
    )
    messages.success(request, f'Promoción "{promotion["name"]}" aplicada')
    return _redirect_to_index(request)
