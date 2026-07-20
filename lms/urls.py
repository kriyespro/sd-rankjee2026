from django.urls import path

from . import views

app_name = 'lms'

urlpatterns = [
    path('', views.home, name='home'),
    path('assignments/new/', views.assignment_create, name='assignment_create'),
    path('a/<int:pk>/edit/', views.assignment_edit, name='assignment_edit'),
    path('a/<int:pk>/', views.assignment_detail, name='assignment_detail'),
    path('submissions/<int:pk>/react/', views.react, name='react'),
    path('submissions/<int:pk>/comment/', views.comment, name='comment'),
    path('batches/', views.batches, name='batches'),
]
