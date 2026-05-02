from django.urls import path

from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.post_list, name='index'),
    path('post/<slug:slug>/', views.post_detail, name='detail'),
]
