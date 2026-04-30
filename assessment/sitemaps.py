from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils.text import slugify

from core.sitemap_utils import CanonicalHostSitemap


class MockTestLandingSitemap(CanonicalHostSitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        return ["jee-main", "neet", "upsc", "ssc-cgl", "bank-po", "cat"]

    def location(self, exam_slug):
        return reverse("assessment:mock_test_landing", kwargs={"exam_slug": exam_slug})


class MockTestCityLandingSitemap(CanonicalHostSitemap):
    changefreq = "daily"
    priority = 0.95

    def items(self):
        exams = ["jee-main", "neet", "upsc", "ssc-cgl", "bank-po"]
        cities = ["ahmedabad", "surat", "vadodara", "mumbai", "delhi", "pune"]
        return [(exam, city) for exam in exams for city in cities]

    def location(self, item):
        exam_slug, city_slug = item
        return reverse(
            "assessment:mock_test_city_landing",
            kwargs={"exam_slug": slugify(exam_slug), "city_slug": slugify(city_slug)},
        )
