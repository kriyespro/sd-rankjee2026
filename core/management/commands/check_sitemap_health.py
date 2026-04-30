from collections import Counter
from pathlib import Path
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import random
import xml.etree.ElementTree as ET

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Validate sitemap.xml health (duplicates + HTTP status checks)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sitemap-url",
            default="",
            help="Absolute sitemap URL. Defaults to <SITE_BASE_URL>/sitemap.xml",
        )
        parser.add_argument(
            "--sample-size",
            type=int,
            default=30,
            help="How many URLs to HTTP-check when --check-all is not used.",
        )
        parser.add_argument(
            "--check-all",
            action="store_true",
            help="Check HTTP status for all URLs in sitemap.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=10,
            help="Timeout (seconds) for sitemap and URL HTTP checks.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for deterministic sampling.",
        )
        parser.add_argument(
            "--report",
            default="seoplan/sitemap_health_report.txt",
            help="Write a plain-text report to this file path.",
        )
        parser.add_argument(
            "--insecure",
            action="store_true",
            help="Skip TLS certificate verification for URL fetches (debug only).",
        )

    def handle(self, *args, **options):
        sitemap_url = (options["sitemap_url"] or "").strip()
        if not sitemap_url:
            base = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
            if not base:
                self.stderr.write(self.style.ERROR("SITE_BASE_URL is empty. Pass --sitemap-url."))
                return
            sitemap_url = f"{base}/sitemap.xml"

        timeout = max(1, int(options["timeout"]))
        random.seed(int(options["seed"]))
        insecure = bool(options["insecure"])

        self.stdout.write(f"Fetching sitemap: {sitemap_url}")
        xml_text = self._fetch_text(sitemap_url, timeout=timeout, insecure=insecure)
        if xml_text is None:
            return

        urls = self._extract_urls(xml_text)
        if not urls:
            self.stderr.write(self.style.ERROR("No <loc> URLs found in sitemap."))
            return

        total = len(urls)
        counts = Counter(urls)
        duplicates = sorted([(u, c) for u, c in counts.items() if c > 1], key=lambda x: (-x[1], x[0]))
        unique_urls = list(counts.keys())

        has_non_https = any(not u.startswith("https://") for u in unique_urls)
        has_example_domain = any("example.com" in u for u in unique_urls)

        if options["check_all"]:
            to_check = unique_urls
        else:
            sample_size = max(1, int(options["sample_size"]))
            to_check = unique_urls if len(unique_urls) <= sample_size else random.sample(unique_urls, sample_size)

        self.stdout.write(f"Checking HTTP status for {len(to_check)} URL(s)...")
        status_rows = [self._check_url(u, timeout=timeout, insecure=insecure) for u in to_check]
        bad_rows = [row for row in status_rows if row["status"] != 200]

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Total URLs: {total}"))
        self.stdout.write(self.style.SUCCESS(f"Unique URLs: {len(unique_urls)}"))
        self.stdout.write(
            self.style.WARNING(f"Duplicate URL entries: {len(duplicates)}")
            if duplicates
            else self.style.SUCCESS("Duplicate URL entries: 0")
        )
        self.stdout.write(
            self.style.WARNING("Contains non-HTTPS URLs: yes")
            if has_non_https
            else self.style.SUCCESS("Contains non-HTTPS URLs: no")
        )
        self.stdout.write(
            self.style.WARNING("Contains example.com URLs: yes")
            if has_example_domain
            else self.style.SUCCESS("Contains example.com URLs: no")
        )
        self.stdout.write(
            self.style.WARNING(f"Non-200 responses in checked set: {len(bad_rows)}")
            if bad_rows
            else self.style.SUCCESS("Non-200 responses in checked set: 0")
        )

        if duplicates:
            self.stdout.write("\nTop duplicate URLs:")
            for url, count in duplicates[:20]:
                self.stdout.write(f"- {count}x {url}")

        if bad_rows:
            self.stdout.write("\nNon-200 URL checks:")
            for row in bad_rows[:30]:
                self.stdout.write(f"- {row['status']} {row['url']} ({row['detail']})")

        report_path = Path(settings.BASE_DIR) / options["report"]
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            self._build_report(
                sitemap_url=sitemap_url,
                total=total,
                unique_count=len(unique_urls),
                duplicates=duplicates,
                has_non_https=has_non_https,
                has_example_domain=has_example_domain,
                checked_count=len(to_check),
                bad_rows=bad_rows,
                status_rows=status_rows,
            ),
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS(f"Report written: {report_path}"))

    @staticmethod
    def _fetch_text(url: str, timeout: int, insecure: bool) -> str | None:
        req = Request(url, headers={"User-Agent": "RankJee-SitemapHealth/1.0"})
        context = ssl._create_unverified_context() if insecure else None
        try:
            with urlopen(req, timeout=timeout, context=context) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            print(f"Failed to fetch sitemap: HTTP {exc.code} ({url})")
        except URLError as exc:
            print(f"Failed to fetch sitemap: {exc.reason} ({url})")
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to fetch sitemap: {exc} ({url})")
        return None

    @staticmethod
    def _extract_urls(xml_text: str) -> list[str]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [elem.text.strip() for elem in root.findall(".//sm:loc", ns) if elem.text and elem.text.strip()]
        if urls:
            return urls
        return [elem.text.strip() for elem in root.findall(".//loc") if elem.text and elem.text.strip()]

    @staticmethod
    def _check_url(url: str, timeout: int, insecure: bool) -> dict:
        req = Request(url, headers={"User-Agent": "RankJee-SitemapHealth/1.0"})
        context = ssl._create_unverified_context() if insecure else None
        try:
            with urlopen(req, timeout=timeout, context=context) as resp:
                final_url = resp.geturl()
                return {
                    "url": url,
                    "status": int(resp.getcode() or 0),
                    "detail": "ok" if final_url == url else f"redirected->{final_url}",
                }
        except HTTPError as exc:
            return {"url": url, "status": int(exc.code), "detail": "http-error"}
        except URLError as exc:
            return {"url": url, "status": 0, "detail": f"url-error:{exc.reason}"}
        except Exception as exc:  # noqa: BLE001
            return {"url": url, "status": 0, "detail": f"error:{exc}"}

    @staticmethod
    def _build_report(
        *,
        sitemap_url: str,
        total: int,
        unique_count: int,
        duplicates: list[tuple[str, int]],
        has_non_https: bool,
        has_example_domain: bool,
        checked_count: int,
        bad_rows: list[dict],
        status_rows: list[dict],
    ) -> str:
        lines = [
            "Sitemap Health Report",
            "",
            f"Sitemap URL: {sitemap_url}",
            f"Total URLs: {total}",
            f"Unique URLs: {unique_count}",
            f"Duplicate URL entries: {len(duplicates)}",
            f"Contains non-HTTPS URLs: {'yes' if has_non_https else 'no'}",
            f"Contains example.com URLs: {'yes' if has_example_domain else 'no'}",
            f"Checked URL count: {checked_count}",
            f"Non-200 in checked set: {len(bad_rows)}",
            "",
        ]
        if duplicates:
            lines.append("Top duplicate URLs:")
            for url, count in duplicates[:50]:
                lines.append(f"- {count}x {url}")
            lines.append("")
        if bad_rows:
            lines.append("Non-200 URL checks:")
            for row in bad_rows[:100]:
                lines.append(f"- {row['status']} {row['url']} ({row['detail']})")
            lines.append("")
        lines.append("Checked URL status rows:")
        for row in status_rows:
            lines.append(f"- {row['status']} {row['url']} ({row['detail']})")
        return "\n".join(lines) + "\n"
