from django.test import Client, TestCase
from django.urls import reverse

from .models import FrequentClient, Order


class PosViewsTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def login(self) -> None:
        self.client.post(
            reverse("cafeteria:login"),
            {"username": "admin", "password": "admin"},
        )

    def test_index_requires_login(self) -> None:
        response = self.client.get(reverse("cafeteria:index"))

        self.assertRedirects(response, reverse("cafeteria:login"))

    def test_login_post_starts_session_and_redirects_to_pos(self) -> None:
        response = self.client.post(
            reverse("cafeteria:login"),
            {"username": "admin", "password": "admin"},
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
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.get()
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(self.client.session.get("last_order_id"), order.id)

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
        self.assertEqual(FrequentClient.objects.get(pk="12345678").saldo_cafes, 4)
