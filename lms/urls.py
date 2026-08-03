from django.urls import path

from . import views

app_name = 'lms'

urlpatterns = [
    path('', views.home, name='home'),
    path('topics/new/', views.topic_create, name='topic_create'),
    path('topics/<int:pk>/', views.topic_detail, name='topic_detail'),
    path('topics/<int:pk>/edit/', views.topic_edit, name='topic_edit'),
    path('assignments/new/', views.assignment_create, name='assignment_create'),
    path('a/<int:pk>/edit/', views.assignment_edit, name='assignment_edit'),
    path('a/<int:pk>/', views.assignment_detail, name='assignment_detail'),
    path('submissions/<int:pk>/react/', views.react, name='react'),
    path('submissions/<int:pk>/comment/', views.comment, name='comment'),
    path('courses/', views.courses, name='courses'),
    path('courses/bulk-enroll/', views.bulk_enroll, name='bulk_enroll'),
    path('builder/', views.course_builder, name='course_builder'),
    path('builder/<int:pk>/', views.course_builder, name='course_builder'),
    path('builder/<int:pk>/topics/add/', views.course_builder_add_topic, name='course_builder_add_topic'),
    path('builder/<int:pk>/assignments/add/', views.course_builder_add_assignment, name='course_builder_add_assignment'),
    path('students/assign/', views.student_assign, name='student_assign'),
    path('courses/<int:pk>/students/', views.students_for_course, name='students_for_course'),
    # Attendance
    path('courses/<int:pk>/attendance/mark/', views.attendance_mark, name='attendance_mark'),
    path('courses/<int:pk>/attendance/', views.attendance_student, name='attendance_student'),
    path('courses/<int:pk>/attendance/summary/', views.attendance_course_summary, name='attendance_course_summary'),
    path('attendance/', views.attendance_admin_all, name='attendance_admin'),
    path('notifications/<int:note_id>/read/', views.notification_read, name='notification_read'),
    # Course demo requests (recorded preview + hybrid live demo routing)
    path('course-demos/', views.course_demo_inbox, name='course_demo_inbox'),
    path('course-demos/<int:pk>/accept/', views.course_demo_accept, name='course_demo_accept'),
    path('course-demos/<int:pk>/decline/', views.course_demo_decline, name='course_demo_decline'),
]
