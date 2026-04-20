from django.urls import path

from . import views

app_name = 'hometutor'

urlpatterns = [
    path('', views.tutor_list, name='tutor_list'),
    path('my/profile/', views.tutor_profile_edit, name='my_profile'),
    path('my/demos/', views.tutor_incoming_demos, name='tutor_demos'),
    path('my/requests/', views.my_demo_requests, name='my_demo_requests'),
    path('demos/<int:pk>/accept/', views.demo_accept, name='demo_accept'),
    path('demos/<int:pk>/decline/', views.demo_decline, name='demo_decline'),
    path('demos/<int:pk>/cancel/', views.demo_cancel, name='demo_cancel'),
    path('demos/<int:pk>/confirm/parent/', views.demo_confirm_parent, name='demo_confirm_parent'),
    path('demos/<int:pk>/confirm/tutor/', views.demo_confirm_tutor, name='demo_confirm_tutor'),
    path('engagements/<int:pk>/', views.engagement_room, name='engagement_room'),
    path('t/<slug:slug>/demo/', views.demo_request_create, name='demo_request_create'),
    path('t/<slug:slug>/', views.tutor_detail, name='tutor_detail'),
]
