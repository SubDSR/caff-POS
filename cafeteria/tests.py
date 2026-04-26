from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import Client, TestCase
from django.urls import reverse


class PosViewsTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.next_order_id = 1
        self.saved_orders: list[dict] = []
        self.pos_account = {
            "correo": "modulo.puntoventa@gmail.com",
            "password_hash": make_password("admin"),
            "nombre_modulo": "Caja Principal",
            "activa": 1,
        }
        self.catalog_products = {
            1: {"id": 1, "name": "Espresso", "price": 6.5, "category": "Cafés"},
            9: {"id": 9, "name": "Croissant", "price": 6.0, "category": "Snacks"},
        }
        self.promotions = {
            1: {"id": 1, "name": "2x1 en Cafés", "discount": 50, "conditions": "Promo café"},
            2: {"id": 2, "name": "Combo Desayuno", "discount": 20, "conditions": "Café + Croissant"},
        }
        self.frequent_clients = {
            "12345678": {"dni": "12345678", "saldo_cafes": 5},
            "87654321": {"dni": "87654321", "saldo_cafes": 3},
            "11111111": {"dni": "11111111", "saldo_cafes": 0},
        }

        self.patchers = [
            patch(
                "cafeteria.views.get_pos_account_by_email",
                side_effect=lambda email: self.pos_account if email == self.pos_account["correo"] else None,
            ),
            patch("cafeteria.views.touch_pos_account_access"),
            patch(
                "cafeteria.views.list_products",
                side_effect=lambda search_query="", selected_category=None: self._filtered_products(search_query, selected_category),
            ),
            patch(
                "cafeteria.views.get_product_by_id",
                side_effect=lambda product_id: self.catalog_products.get(int(product_id)),
            ),
            patch(
                "cafeteria.views.list_promotions",
                side_effect=lambda: list(self.promotions.values()),
            ),
            patch(
                "cafeteria.views.get_promotion_by_id",
                side_effect=lambda promotion_id: self.promotions.get(int(promotion_id)),
            ),
            patch(
                "cafeteria.views.get_frequent_client",
                side_effect=lambda dni: self.frequent_clients.get(dni),
            ),
            patch(
                "cafeteria.views.decrement_frequent_client_balance",
                side_effect=self._decrement_frequent_client_balance,
            ),
            patch(
                "cafeteria.views.order_exists",
                side_effect=lambda order_id: any(order["id"] == order_id for order in self.saved_orders),
            ),
            patch(
                "cafeteria.views.get_order_items_for_repeat",
                side_effect=self._get_order_items_for_repeat,
            ),
            patch(
                "cafeteria.views.create_order",
                side_effect=self._create_order,
            ),
        ]

        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _filtered_products(self, search_query: str = "", selected_category: str | None = None) -> list[dict]:
        products = list(self.catalog_products.values())
        if search_query:
            lowered_query = search_query.lower()
            products = [
                product
                for product in products
                if lowered_query in product["name"].lower() or lowered_query in product["category"].lower()
            ]
        if selected_category:
            products = [product for product in products if product["category"] == selected_category]
        return products

    def _decrement_frequent_client_balance(self, dni: str) -> int | None:
        client = self.frequent_clients.get(dni)
        if client is None:
            return None
        if client["saldo_cafes"] <= 0:
            return 0
        client["saldo_cafes"] -= 1
        return client["saldo_cafes"]

    def _create_order(
        self,
        cart: list[dict],
        discount_percentage,
        totals: dict,
        *,
        dni_cliente: str | None = None,
        orden_anterior_id: int | None = None,
        discount_entries: list[dict] | None = None,
    ) -> int:
        order_id = self.next_order_id
        self.next_order_id += 1
        self.saved_orders.append(
            {
                "id": order_id,
                "cart": [dict(item) for item in cart],
                "discount_percentage": discount_percentage,
                "totals": totals,
                "dni_cliente": dni_cliente,
                "orden_anterior_id": orden_anterior_id,
                "discount_entries": list(discount_entries or []),
            }
        )
        return order_id

    def _get_order_items_for_repeat(self, order_id: int) -> list[dict]:
        for order in self.saved_orders:
            if order["id"] == order_id:
                return [dict(item) for item in order["cart"]]
        return []

    def login(self) -> None:
        self.client.post(
            reverse("cafeteria:login"),
            {"username": self.pos_account["correo"], "password": "admin"},
        )

    def test_index_requires_login(self) -> None:
        response = self.client.get(reverse("cafeteria:index"))

        self.assertRedirects(response, reverse("cafeteria:login"))

    def test_login_post_starts_session_and_redirects_to_pos(self) -> None:
        response = self.client.post(
            reverse("cafeteria:login"),
            {"username": "modulo.puntoventa@gmail.com", "password": "admin"},
        )

        self.assertRedirects(response, reverse("cafeteria:index"))
        self.assertTrue(self.client.session.get("is_logged_in"))

    def test_add_to_cart_creates_session_item(self) -> None:
        self.login()

        response = self.client.post(reverse("cafeteria:add_to_cart", args=["1"]))

        self.assertRedirects(response, reverse("cafeteria:index"))
        self.assertEqual(
            self.client.session.get("cart"),
            [{"id": "1", "name": "Espresso", "price": 6.5, "category": "Cafés", "quantity": 1}],
        )

    def test_update_cart_item_changes_quantity(self) -> None:
        self.login()
        self.client.post(reverse("cafeteria:add_to_cart", args=["1"]))

        response = self.client.post(
            reverse("cafeteria:update_cart_item", args=["1"]),
            {"quantity": 3},
        )

        self.assertRedirects(response, reverse("cafeteria:index"))
        self.assertEqual(self.client.session["cart"][0]["quantity"], 3)

    def test_checkout_moves_cart_to_last_order(self) -> None:
        self.login()
        self.client.post(reverse("cafeteria:add_to_cart", args=["1"]))

        response = self.client.post(reverse("cafeteria:checkout"))

        self.assertRedirects(response, reverse("cafeteria:index"))
        self.assertEqual(self.client.session.get("cart"), [])
        self.assertEqual(self.client.session.get("discount"), 0)
        self.assertEqual(len(self.saved_orders), 1)
        self.assertEqual(len(self.saved_orders[0]["cart"]), 1)
        self.assertEqual(self.client.session.get("last_order_id"), 1)

    def test_apply_discount_updates_session_discount(self) -> None:
        self.login()

        response = self.client.post(reverse("cafeteria:apply_discount"), {"discount_custom": "15"})

        self.assertRedirects(response, reverse("cafeteria:index"))
        self.assertEqual(self.client.session.get("discount"), 15.0)

    def test_apply_discount_uses_selected_preset_only_on_submit(self) -> None:
        self.login()

        response = self.client.post(
            reverse("cafeteria:apply_discount"),
            {"discount_custom": "0", "preset_discount": "25"},
        )

        self.assertRedirects(response, reverse("cafeteria:index"))
        self.assertEqual(self.client.session.get("discount"), 25.0)

    def test_apply_promotion_updates_discount_from_catalog(self) -> None:
        self.login()

        response = self.client.post(
            reverse("cafeteria:apply_promotion"),
            {"promotion_id": "2"},
        )

        self.assertRedirects(response, reverse("cafeteria:index"))
        self.assertEqual(self.client.session.get("discount"), 20.0)

    def test_frequent_client_benefit_requires_coffee_in_cart(self) -> None:
        self.login()
        self.client.post(reverse("cafeteria:add_to_cart", args=["9"]))

        response = self.client.post(
            reverse("cafeteria:apply_frequent_client_benefit"),
            {"dni": "12345678", "modal": "frequent-client"},
            follow=True,
        )

        self.assertEqual(
            response.redirect_chain,
            [(f"{reverse('cafeteria:index')}?modal=frequent-client", 302)],
        )
        self.assertContains(response, "Debe tener al menos un café en el carrito")

    def test_frequent_client_benefit_applies_discount_and_consumes_balance(self) -> None:
        self.login()
        self.client.post(reverse("cafeteria:add_to_cart", args=["1"]))

        response = self.client.post(
            reverse("cafeteria:apply_frequent_client_benefit"),
            {"dni": "12345678", "modal": "frequent-client"},
        )

        self.assertRedirects(response, f"{reverse('cafeteria:index')}?modal=frequent-client")
        self.assertEqual(self.client.session.get("discount"), 100)
        self.assertEqual(self.frequent_clients["12345678"]["saldo_cafes"], 4)

    def test_repeat_order_restores_previous_cart(self) -> None:
        self.login()
        self.client.post(reverse("cafeteria:add_to_cart", args=["1"]))
        self.client.post(reverse("cafeteria:checkout"))

        response = self.client.post(reverse("cafeteria:repeat_order"))

        self.assertRedirects(response, reverse("cafeteria:index"))
        self.assertEqual(
            self.client.session.get("cart"),
            [{"id": "1", "name": "Espresso", "price": 6.5, "category": "Cafés", "quantity": 1}],
        )

    def test_checkout_persists_discount_metadata_for_mysql_order(self) -> None:
        self.login()
        self.client.post(reverse("cafeteria:add_to_cart", args=["1"]))
        self.client.post(reverse("cafeteria:apply_promotion"), {"promotion_id": "2"})

        self.client.post(reverse("cafeteria:checkout"))

        self.assertEqual(
            self.saved_orders[0]["discount_entries"],
            [{"type": "promocion", "pct": 20, "promotion_id": 2}],
        )
