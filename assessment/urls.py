from django.urls import path
from . import views

app_name = 'assessment'
urlpatterns = [
    path('', views.test_index, name='index'),
    path('jackpot/', views.jackpot_lobby, name='jackpot_lobby'),
    path('<int:skill_id>/take/', views.take_test, name='take_test'),
    path('<int:skill_id>/submit/', views.submit_test, name='submit_test'),
    path('certificate/<uuid:certificate_id>/view/', views.view_certificate, name='view_certificate'),
    path('certificate/<uuid:certificate_id>/download/', views.download_certificate, name='download_certificate'),
]
