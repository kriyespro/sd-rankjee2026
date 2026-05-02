from django.urls import path

from . import views

app_name = 'study'

urlpatterns = [
    path('', views.student_hub, name='student_hub'),
    path('material/<int:pk>/', views.student_material_detail, name='student_material'),
    path('assignment/<int:pk>/', views.student_assignment_detail, name='student_assignment'),
    path('tutor/', views.tutor_dashboard, name='tutor_dashboard'),
    path('tutor/materials/new/', views.tutor_material_create, name='tutor_material_create'),
    path('tutor/materials/<int:pk>/edit/', views.tutor_material_edit, name='tutor_material_edit'),
    path('tutor/assignments/new/', views.tutor_assignment_create, name='tutor_assignment_create'),
    path('tutor/assignments/<int:pk>/edit/', views.tutor_assignment_edit, name='tutor_assignment_edit'),
    path('tutor/assignments/<int:pk>/submissions/', views.tutor_assignment_submissions, name='tutor_assignment_submissions'),
]
