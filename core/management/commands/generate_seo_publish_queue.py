from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate prioritized SEO publish queue from generated landing URLs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="seoplan/generated_landing_urls.txt",
            help="Source URL list file.",
        )
        parser.add_argument(
            "--output",
            default="seoplan/seo_publish_queue.csv",
            help="Output queue CSV file.",
        )
        parser.add_argument(
            "--default-status",
            default="needs-content",
            choices=["ready", "needs-content", "live"],
            help="Default status value for generated rows.",
        )

    def handle(self, *args, **options):
        source = Path(settings.BASE_DIR) / options["source"]
        output = Path(settings.BASE_DIR) / options["output"]
        default_status = options["default_status"]

        if not source.exists():
            self.stderr.write(self.style.ERROR(f"Source file not found: {source}"))
            return

        urls = [line.strip() for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        grouped = {
            "tutor": [],
            "mock": [],
            "course": [],
            "other": [],
        }

        for url in urls:
            bucket = self._bucket(url)
            grouped[bucket].append(url)

        priority_order = [("tutor", 1), ("mock", 2), ("course", 3), ("other", 4)]
        lines = ["priority,type,url,status,owner,notes"]
        for bucket, priority in priority_order:
            for url in grouped[bucket]:
                lines.append(f"{priority},{bucket},{url},{default_status},seo-team,")

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(f"Queue rows: {len(lines) - 1}"))
        self.stdout.write(self.style.SUCCESS(f"Wrote queue: {output}"))

    @staticmethod
    def _bucket(url: str) -> str:
        if url.startswith("/hometutor/"):
            return "tutor"
        if url.startswith("/assessment/mock-test/"):
            return "mock"
        if url.startswith("/courses/"):
            return "course"
        return "other"
