from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils.text import slugify

from .models import Course


class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return ["core:home", "core:courses", "assessment:index", "learning:index", "hometutor:tutor_list"]

    def location(self, item):
        return reverse(item)


class CourseSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Course.objects.filter(is_active=True)

    def location(self, obj):
        return reverse("core:course_detail", kwargs={"slug": obj.slug})


class CourseCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.95

    def items(self):
        courses = list(Course.objects.filter(is_active=True).values_list("slug", flat=True)[:100])
        cities = ["ahmedabad", "surat", "vadodara", "rajkot", "mumbai", "delhi", "pune", "bangalore"]
        return [(slugify(course_slug), slugify(city)) for course_slug in courses for city in cities]

    def location(self, item):
        course_slug, city_slug = item
        return reverse("core:course_city_landing", kwargs={"slug": course_slug, "city_slug": city_slug})
