from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:note_id>/read/', views.mark_notification_read, name='mark_read'),
    path('recharge/', views.recharge_wallet, name='recharge'),
]
