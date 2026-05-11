from django.urls import path

from . import views

app_name = "server_buy"

urlpatterns = [
    path("", views.checkout, name="checkout"),
    path("quote/", views.quote_partial, name="quote_partial"),
    path("create-order/", views.create_order, name="create_order"),
    path("verify/", views.verify_payment, name="verify_payment"),
]
