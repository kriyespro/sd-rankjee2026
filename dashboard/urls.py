from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('seo/smart-view/', views.seo_smart_view, name='seo_smart_view'),
    path('students/scores/', views.students_score_table, name='students_score_table'),
    path('users/referrals/', views.users_referral_table, name='users_referral_table'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:note_id>/read/', views.mark_notification_read, name='mark_read'),
    path('recharge/', views.recharge_wallet, name='recharge'),
    path('imports/questions/', views.import_questions_csv, name='import_questions'),
    path('ai/generate-mcqs/', views.ai_generate_mcqs, name='ai_generate_mcqs'),
    path('cms/', views.cms_home, name='cms_home'),
    path('cms/paths/', views.cms_skillpaths, name='cms_skillpaths'),
    path('cms/paths/new/', views.cms_skillpath_edit, name='cms_skillpath_new'),
    path('cms/paths/<int:pk>/', views.cms_skillpath_edit, name='cms_skillpath_edit'),
    path('cms/skills/', views.cms_skills, name='cms_skills'),
    path('cms/skills/new/', views.cms_skill_edit, name='cms_skill_new'),
    path('cms/skills/<int:pk>/', views.cms_skill_edit, name='cms_skill_edit'),
    path('cms/questions/', views.cms_questions, name='cms_questions'),
    path('cms/questions/new/', views.cms_question_edit, name='cms_question_new'),
    path('cms/questions/<int:pk>/', views.cms_question_edit, name='cms_question_edit'),
    path('cms/videos/', views.cms_videos, name='cms_videos'),
    path('cms/videos/new/', views.cms_video_edit, name='cms_video_new'),
    path('cms/videos/<int:pk>/', views.cms_video_edit, name='cms_video_edit'),
    path('cms/tasks/', views.cms_tasks, name='cms_tasks'),
    path('cms/tasks/new/', views.cms_task_edit, name='cms_task_new'),
    path('cms/tasks/<int:pk>/', views.cms_task_edit, name='cms_task_edit'),
]
