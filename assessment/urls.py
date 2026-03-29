from django.urls import path
from . import views

app_name = 'assessment'
urlpatterns = [
    path('', views.test_index, name='index'),
    path('<int:skill_id>/take/', views.take_test, name='take_test'),
    path('<int:skill_id>/submit/', views.submit_test, name='submit_test'),
]
