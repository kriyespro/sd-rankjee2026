"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views as core_views
from core.sitemaps import StaticViewSitemap, CourseSitemap, CourseCitySitemap
from hometutor.sitemaps import TutorCityLandingSitemap, TutorCitySubjectLandingSitemap
from assessment.sitemaps import MockTestLandingSitemap, MockTestCityLandingSitemap

admin.site.site_header = "RankJee Admin Control"
admin.site.site_title = "RankJee Admin"
admin.site.index_title = "Welcome to RankJee Control Centre"

urlpatterns = [
    path('sd/', admin.site.urls), # standard django admin
    path('admin/', include('dashboard.urls')), # custom dashboard
    path('robots.txt', core_views.robots_txt, name='robots_txt'),
    path(
        'sitemap.xml',
        sitemap,
        {
            'sitemaps': {
                'static': StaticViewSitemap,
                'courses': CourseSitemap,
                'course_cities': CourseCitySitemap,
                'tutor_cities': TutorCityLandingSitemap,
                'tutor_city_subjects': TutorCitySubjectLandingSitemap,
                'mock_tests': MockTestLandingSitemap,
                'mock_test_cities': MockTestCityLandingSitemap,
            }
        },
        name='django.contrib.sitemaps.views.sitemap',
    ),
    path('accounts/', include('allauth.urls')),
    path('users/', include('users.urls')),
    path('assessment/', include('assessment.urls')),
    path('learning/', include('learning.urls')),
    path('payments/', include('payments.urls')),
    path('hometutor/', include('hometutor.urls')),
    path('hometutor/payments/', include('hometutor_payments.urls')),
    path('sw.js', core_views.service_worker, name='service_worker'),
    path('', include('core.urls')),
    path('<slug:city_slug>/', core_views.city_tutor_redirect, name='city_tutor_redirect'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
