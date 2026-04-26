from __future__ import annotations

from decimal import Decimal

from django.http import HttpRequest


def get_cart(request: HttpRequest) -> list[dict]:
    return list(request.session.get("cart", []))


def set_cart(request: HttpRequest, cart: list[dict]) -> None:
    request.session["cart"] = cart
    request.session.modified = True


def get_last_order_id(request: HttpRequest) -> int | None:
    return request.session.get("last_order_id")


def set_last_order_id(request: HttpRequest, order_id: int | None) -> None:
    request.session["last_order_id"] = order_id
    request.session.modified = True


def get_repeat_source_order_id(request: HttpRequest) -> int | None:
    return request.session.get("repeat_source_order_id")


def set_repeat_source_order_id(request: HttpRequest, order_id: int | None) -> None:
    if order_id is None:
        request.session.pop("repeat_source_order_id", None)
    else:
        request.session["repeat_source_order_id"] = order_id
    request.session.modified = True


def get_discount(request: HttpRequest) -> float:
    return float(request.session.get("discount", 0))


def set_discount(request: HttpRequest, discount: float | Decimal) -> None:
    normalized = round(max(0, min(float(discount), 100)), 2)
    request.session["discount"] = normalized
    request.session.modified = True


def get_discount_entries(request: HttpRequest) -> list[dict]:
    return list(request.session.get("discount_entries", []))


def set_discount_entries(request: HttpRequest, entries: list[dict]) -> None:
    request.session["discount_entries"] = entries
    request.session.modified = True


def clear_discount_state(request: HttpRequest) -> None:
    set_discount(request, 0)
    set_discount_entries(request, [])
