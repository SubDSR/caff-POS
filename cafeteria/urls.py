from django.urls import path

from . import views


app_name = "cafeteria"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.index, name="index"),
    path("cart/add/<str:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/<str:product_id>/", views.update_cart_item, name="update_cart_item"),
    path("cart/remove/<str:product_id>/", views.remove_cart_item, name="remove_cart_item"),
    path("cart/clear/", views.clear_cart, name="clear_cart"),
    path("cart/repeat/", views.repeat_order, name="repeat_order"),
    path("checkout/", views.checkout, name="checkout"),
    path("benefits/apply/", views.apply_frequent_client_benefit, name="apply_frequent_client_benefit"),
    path("discounts/apply/", views.apply_discount, name="apply_discount"),
    path("discounts/remove/", views.remove_discount, name="remove_discount"),
    path("promotions/apply/", views.apply_promotion, name="apply_promotion"),
]
