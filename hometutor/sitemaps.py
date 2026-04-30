from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils.text import slugify

from core.sitemap_utils import CanonicalHostSitemap
from .models import TutorProfile


class TutorCityLandingSitemap(CanonicalHostSitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        cities = (
            TutorProfile.objects.filter(
                verification_status=TutorProfile.VerificationStatus.APPROVED
            )
            .values_list("city", flat=True)
            .distinct()[:200]
        )
        deduped = []
        seen = set()
        for raw_city in cities:
            city = (raw_city or "").strip()
            city_slug = slugify(city)
            if not city_slug or city_slug in seen:
                continue
            seen.add(city_slug)
            deduped.append(city)
            if len(deduped) >= 50:
                break
        return deduped

    def location(self, city):
        return reverse("hometutor:tutor_city_landing", kwargs={"city_slug": slugify(city)})


class TutorCitySubjectLandingSitemap(CanonicalHostSitemap):
    changefreq = "daily"
    priority = 0.95

    def items(self):
        pairs = []
        seen = set()
        tutors = TutorProfile.objects.filter(
            verification_status=TutorProfile.VerificationStatus.APPROVED
        ).only("city", "subjects")[:1000]
        for tutor in tutors:
            city = (tutor.city or "").strip()
            if not city:
                continue
            for token in (tutor.subjects or "").split(","):
                subject = token.strip()
                if not subject:
                    continue
                key = (slugify(city), slugify(subject))
                if key in seen:
                    continue
                seen.add(key)
                pairs.append((city, subject))
                if len(pairs) >= 300:
                    return pairs
        return pairs

    def location(self, item):
        city, subject = item
        return reverse(
            "hometutor:tutor_city_subject_landing",
            kwargs={"city_slug": slugify(city), "subject_slug": slugify(subject)},
        )
