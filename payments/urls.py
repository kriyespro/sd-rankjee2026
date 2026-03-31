from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('plans/', views.plans_view, name='plans'),
    path('order/<int:plan_id>/', views.create_order, name='create_order'),
    path('verify/', views.verify_payment, name='verify_payment'),
]
