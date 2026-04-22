from django.urls import path

from . import views

app_name = 'hometutor'

urlpatterns = [
    path('', views.tutor_list, name='tutor_list'),
    path('city/<slug:city_slug>/', views.tutor_city_landing, name='tutor_city_landing'),
    path(
        'city/<slug:city_slug>/subject/<slug:subject_slug>/',
        views.tutor_city_landing,
        name='tutor_city_subject_landing',
    ),
    path(
        'city/<slug:city_slug>/subject/<slug:subject_slug>/class-<int:grade>/',
        views.tutor_city_landing,
        name='tutor_city_subject_class_landing',
    ),
    path(
        'city/<slug:city_slug>/subject/<slug:subject_slug>/class-<int:grade>/<slug:location_slug>/',
        views.tutor_city_landing,
        name='tutor_city_subject_class_location_landing',
    ),
    path('search/quick/', views.quick_tutor_search, name='quick_tutor_search'),
    path('compare/', views.compare_tutors, name='compare_tutors'),
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
