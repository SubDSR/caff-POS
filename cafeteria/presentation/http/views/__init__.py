from .auth import login_view, logout_view
from .pos import (
    add_to_cart,
    apply_discount,
    apply_frequent_client_benefit,
    apply_promotion,
    checkout,
    clear_cart,
    index,
    remove_cart_item,
    remove_discount,
    repeat_order,
    update_cart_item,
)

__all__ = [
    "add_to_cart",
    "apply_discount",
    "apply_frequent_client_benefit",
    "apply_promotion",
    "checkout",
    "clear_cart",
    "index",
    "login_view",
    "logout_view",
    "remove_cart_item",
    "remove_discount",
    "repeat_order",
    "update_cart_item",
]
