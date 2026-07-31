from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('signup/google/', views.google_signup_start, name='google_signup_start'),
    path('onboarding/role/', views.onboarding_role, name='onboarding_role'),
    path('onboarding/profile/', views.onboarding_profile, name='onboarding_profile'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('family/', views.family_hub, name='family_hub'),
    path('referral/regenerate/', views.regenerate_referral, name='regenerate_referral'),
    path('ui-lang/<str:lang>/', views.set_ui_lang, name='set_ui_lang'),
    path('u/<slug:slug>/inquiry/', views.company_inquiry_submit, name='company_inquiry'),
    path('u/<slug:slug>/', views.public_profile, name='public_profile'),
]
