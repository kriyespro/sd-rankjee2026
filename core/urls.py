from django.urls import path
from . import views

app_name = 'core'
urlpatterns = [
    path('privacy/', views.privacy, name='privacy'),
    path('terms/', views.terms, name='terms'),
    path('courses/', views.courses, name='courses'),
    path('courses/<slug:slug>/<slug:city_slug>/', views.course_city_landing, name='course_city_landing'),
    path('courses/<slug:slug>/', views.course_detail, name='course_detail'),
    path('request-tutor/', views.request_tutor, name='request_tutor'),
    path('', views.home, name='home'),
    path('earnings/', views.earnings, name='earnings'),
    path('earnings/<int:task_id>/submit/', views.submit_task, name='submit_task'),
    path('watch-ads/', views.watch_ads, name='watch_ads'),
    path('watch-ads/claim-reward/', views.claim_ad_reward, name='claim_ad_reward'),
    path('admin/submissions/<int:submission_id>/approve/', views.admin_approve_submission, name='admin_approve'),
    path('admin/submissions/<int:submission_id>/reject/', views.admin_reject_submission, name='admin_reject'),
    path('earnings/request-withdrawal/', views.request_withdrawal, name='request_withdrawal'),
]
