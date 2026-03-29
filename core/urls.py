from django.urls import path
from . import views

app_name = 'core'
urlpatterns = [
    path('', views.home, name='home'),
    path('earnings/', views.earnings, name='earnings'),
    path('earnings/<int:task_id>/submit/', views.submit_task, name='submit_task'),
    path('admin/submissions/<int:submission_id>/approve/', views.admin_approve_submission, name='admin_approve'),
    path('admin/submissions/<int:submission_id>/reject/', views.admin_reject_submission, name='admin_reject'),
]
