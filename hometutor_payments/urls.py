from django.urls import path

from . import views

app_name = 'hometutor_payments'

urlpatterns = [
    path('pay/<int:engagement_id>/', views.pay_checkout, name='pay_checkout'),
    path('pay/<int:engagement_id>/order/', views.create_order, name='create_order'),
    path('verify/', views.verify_payment, name='verify_payment'),
    path('webhook/razorpay/', views.razorpay_webhook, name='razorpay_webhook'),
]
