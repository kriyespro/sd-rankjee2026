from pathlib import Path
import re

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import Course


class Command(BaseCommand):
    help = "Generate SEO landing URL batch from seoplan keyword map."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="seoplan/keyword_url_map.txt",
            help="Path to keyword URL map file.",
        )
        parser.add_argument(
            "--output",
            default="seoplan/generated_landing_urls.txt",
            help="Where to write generated URL list.",
        )
        parser.add_argument(
            "--write",
            action="store_true",
            help="Write output file. Without this, only prints preview.",
        )
        parser.add_argument(
            "--target-tutor",
            type=int,
            default=50,
            help="Target count for tutor landing URLs.",
        )
        parser.add_argument(
            "--target-mock",
            type=int,
            default=20,
            help="Target count for mock test landing URLs.",
        )
        parser.add_argument(
            "--target-course",
            type=int,
            default=20,
            help="Target count for course-city landing URLs.",
        )

    def handle(self, *args, **options):
        source = Path(settings.BASE_DIR) / options["source"]
        output = Path(settings.BASE_DIR) / options["output"]
        if not source.exists():
            self.stderr.write(self.style.ERROR(f"Source file not found: {source}"))
            return

        raw = source.read_text(encoding="utf-8")
        urls = self._extract_urls(raw)
        expanded = self._expand_course_placeholders(urls)
        seeded = set(expanded)
        seeded.update(
            self._expand_targets(
                target_tutor=options["target_tutor"],
                target_mock=options["target_mock"],
                target_course=options["target_course"],
            )
        )
        unique_urls = sorted(seeded)

        self.stdout.write(self.style.SUCCESS(f"Generated {len(unique_urls)} unique URLs"))
        for row in unique_urls[:40]:
            self.stdout.write(row)
        if len(unique_urls) > 40:
            self.stdout.write(f"... and {len(unique_urls) - 40} more")

        if options["write"]:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("\n".join(unique_urls) + "\n", encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Wrote output: {output}"))

    @staticmethod
    def _extract_urls(raw: str) -> list[str]:
        lines = raw.splitlines()
        urls = []
        for line in lines:
            m = re.match(r"\s*-\s*URL:\s*(\S+)", line)
            if m:
                urls.append(m.group(1).strip())
        return urls

    @staticmethod
    def _expand_course_placeholders(urls: list[str]) -> list[str]:
        course_slugs = list(Course.objects.filter(is_active=True).values_list("slug", flat=True)[:100])
        result = []
        for url in urls:
            if "<course-slug>" in url:
                for slug in course_slugs:
                    result.append(url.replace("<course-slug>", slug))
            else:
                result.append(url)
        return result

    @staticmethod
    def _expand_targets(target_tutor: int, target_mock: int, target_course: int) -> set[str]:
        from django.utils.text import slugify

        cities = [
            "ahmedabad",
            "surat",
            "vadodara",
            "rajkot",
            "mumbai",
            "delhi",
            "pune",
            "bangalore",
            "hyderabad",
            "chennai",
        ]
        subjects = [
            "maths",
            "science",
            "english",
            "physics",
            "chemistry",
            "biology",
            "social-science",
            "hindi",
            "accounts",
            "economics",
        ]
        exams = [
            "jee-main",
            "neet",
            "upsc",
            "ssc-cgl",
            "bank-po",
            "cat",
            "gmat",
            "railway",
            "cuet",
            "nda",
        ]
        class_bands = [8, 9, 10, 11, 12]
        locations = ["satellite", "navrangpura", "maninagar", "vesu", "andheri"]
        course_slugs = list(Course.objects.filter(is_active=True).values_list("slug", flat=True))
        course_slugs = [slugify(s) for s in course_slugs if s]

        out: set[str] = set()

        tutor_urls = []
        for city in cities:
            tutor_urls.append(f"/hometutor/city/{city}/")
            for subject in subjects:
                tutor_urls.append(f"/hometutor/city/{city}/subject/{subject}/")
                for grade in class_bands:
                    tutor_urls.append(f"/hometutor/city/{city}/subject/{subject}/class-{grade}/")
            for subject in ("maths", "physics", "chemistry"):
                tutor_urls.append(f"/hometutor/city/{city}/subject/{subject}/class-12/{locations[0]}/")
        out.update(tutor_urls[: max(0, target_tutor)])

        mock_urls = []
        for exam in exams:
            mock_urls.append(f"/assessment/mock-test/{exam}/")
            for city in cities:
                mock_urls.append(f"/assessment/mock-test/{exam}/{city}/")
        out.update(mock_urls[: max(0, target_mock)])

        course_urls = []
        for slug in course_slugs:
            for city in cities:
                course_urls.append(f"/courses/{slug}/{city}/")
        out.update(course_urls[: max(0, target_course)])
        return out
