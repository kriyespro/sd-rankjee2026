import re

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class BlogCategory(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, db_index=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Blog categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:140] or 'category'
            slug = base
            n = 2
            while BlogCategory.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)


class BlogPost(models.Model):
    slug = models.SlugField(max_length=180, unique=True, db_index=True)
    title = models.CharField(max_length=220)
    excerpt = models.TextField(blank=True, help_text='Short summary for listings and meta fallback.')
    body = models.TextField(help_text='Plain text; paragraphs separated by blank lines.')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blog_posts',
    )
    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts',
    )
    hero_image = models.ImageField(
        upload_to='blog/hero/%Y/%m/',
        blank=True,
        null=True,
    )
    meta_title = models.CharField(max_length=220, blank=True)
    meta_description = models.CharField(max_length=320, blank=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-pk']

    def __str__(self):
        return self.title

    def is_published(self):
        return self.published_at is not None

    def _strip_template_preamble_for_body(self, raw: str) -> str:
        if not raw:
            return raw
        # Back-compat wrapper for older excerpt/title generation:
        # strip known template blocks (SEO metadata / research plan) but keep the article.
        cleaned, _ = self._clean_body_and_extract_seo(raw)
        return cleaned

    def _clean_body_and_extract_seo(self, raw: str) -> tuple[str, dict]:
        """
        Supports the "SEO draft" paste format:

        - Removes the top "# SEO Metadata" block from the saved body
        - Removes the whole "# Phase 1: Strategic Research" section (until next H1) from the saved body
        - Extracts:
          - Title Tag
          - Meta Description
          - Suggested URL Slug
        """
        if not raw:
            return raw, {}

        text = raw.replace("\r\n", "\n").strip()
        seo = {}

        # Extract SEO metadata block (if present) and remove it from body.
        # We remove from "# SEO Metadata" up to the next H1 heading ("# ...") OR end-of-text.
        meta_match = re.search(
            r"(?ims)^\s*#\s*seo metadata\s*\n(?P<body>.*?)(?=^\s*#\s+|\Z)",
            text,
        )
        if meta_match:
            meta_block = meta_match.group("body") or ""
            title_tag = re.search(r"(?im)^\s*\*\*title\s*tag:\*\*\s*(.+?)\s*$", meta_block)
            meta_desc = re.search(r"(?im)^\s*\*\*meta\s*description:\*\*\s*(.+?)\s*$", meta_block)
            slug_suggest = re.search(r"(?im)^\s*\*\*suggested\s*url\s*slug:\*\*\s*(.+?)\s*$", meta_block)
            if title_tag:
                seo["title_tag"] = title_tag.group(1).strip()
            if meta_desc:
                seo["meta_description"] = meta_desc.group(1).strip()
            if slug_suggest:
                seo["suggested_slug"] = slug_suggest.group(1).strip()

            text = (text[: meta_match.start()] + "\n\n" + text[meta_match.end() :]).strip()

        # Remove "Phase 1: Strategic Research" section anywhere in the document.
        # Remove from its H1 heading to the next H1 heading or end.
        text = re.sub(
            r"(?ims)^\s*#\s*phase\s*1:\s*strategic\s*research\s*\n.*?(?=^\s*#\s+|\Z)",
            "",
            text,
        ).strip()

        # Collapse excessive blank lines created by removals.
        text = re.sub(r"\n{4,}", "\n\n\n", text).strip()
        return text, seo

    def _extract_title_from_body(self) -> str:
        raw = self._strip_template_preamble_for_body((self.body or "").strip())
        if not raw:
            return ""
        lines = raw.splitlines()
        for line in lines:
            s = line.strip()
            if not s:
                continue
            heading = re.match(r"^#{1,4}\s+(.+)$", s)
            if heading:
                candidate = heading.group(1).strip()
                return candidate[:220]
            # fallback to first meaningful line
            candidate = re.sub(r"^[\-\*\d\.\)\s]+", "", s).strip()
            if candidate:
                return candidate[:220]
        return ""

    def _build_unique_slug(self, seed: str) -> str:
        base = slugify(seed)[:170] or "post"
        candidate = base
        n = 2
        while BlogPost.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
            suffix = f"-{n}"
            candidate = f"{base[:170-len(suffix)]}{suffix}"
            n += 1
        return candidate

    def _auto_excerpt_from_body(self) -> str:
        raw = self._strip_template_preamble_for_body((self.body or "").strip())
        if not raw:
            return ""

        # Strip markdown syntax to plain text summary.
        text = re.sub(r"^#{1,6}\s*", "", raw, flags=re.MULTILINE)
        text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\*([^*]+)\*", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
        text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:280]

    def _title_tokens(self, value: str) -> set[str]:
        stop = {
            "the",
            "a",
            "an",
            "for",
            "and",
            "with",
            "from",
            "into",
            "your",
            "guide",
            "best",
            "complete",
            "how",
            "to",
            "of",
            "in",
            "on",
        }
        cleaned = re.sub(r"[^a-z0-9\s]", " ", (value or "").lower())
        return {t for t in cleaned.split() if len(t) > 2 and t not in stop}

    def _resolve_internal_link_target(self, anchor_text: str, excluded_ids=None):
        tokens = self._title_tokens(anchor_text)
        excluded_ids = set(excluded_ids or [])
        if not tokens:
            return None

        qs = BlogPost.objects.exclude(pk=self.pk).exclude(pk__in=excluded_ids).filter(
            published_at__isnull=False
        ).order_by("-published_at", "-pk")[:200]

        best_post = None
        best_score = 0
        anchor_norm = " ".join(sorted(tokens))
        for post in qs:
            title_tokens = self._title_tokens(post.title or "")
            excerpt_tokens = self._title_tokens(post.excerpt or "")
            overlap = len(tokens & title_tokens)
            overlap += 0.5 * len(tokens & excerpt_tokens)

            # Prefer closer phrase matches in title.
            title_l = (post.title or "").lower()
            if anchor_text.lower() in title_l:
                overlap += 3
            if anchor_norm and anchor_norm in " ".join(sorted(title_tokens)):
                overlap += 1

            if overlap > best_score:
                best_score = overlap
                best_post = post

        if best_post and best_score > 0:
            return best_post
        # Fallback: pick the latest published post so suggestion still becomes a link.
        return (
            BlogPost.objects.exclude(pk=self.pk)
            .exclude(pk__in=excluded_ids)
            .filter(published_at__isnull=False)
            .order_by("-published_at", "-pk")
            .first()
        )

    def _autolink_internal_suggestions(self, raw: str) -> str:
        if not raw:
            return raw
        lines = raw.splitlines()
        out = []
        in_section = False
        used_target_ids = set()

        for line in lines:
            stripped = line.strip()
            low = stripped.lower()

            if not in_section:
                if low in {
                    "internal linking suggestions",
                    "# internal linking suggestions",
                    "## internal linking suggestions",
                }:
                    in_section = True
                out.append(line)
                continue

            # End this block at horizontal rule or next H1.
            if stripped == "---" or re.match(r"^#\s+.+", stripped):
                in_section = False
                out.append(line)
                continue

            # Bullet item containing bracket text only: "* [Some title]"
            m = re.match(r"^(\s*[-*]\s*)\[([^\]]+)\]\s*$", line)
            if m:
                prefix, anchor = m.group(1), m.group(2).strip()
                target = self._resolve_internal_link_target(anchor, excluded_ids=used_target_ids)
                if target:
                    used_target_ids.add(target.pk)
                    out.append(f"{prefix}[{anchor}](/blog/post/{target.slug}/)")
                else:
                    out.append(line)
                continue

            # Existing markdown link item: "* [Some title](/blog/post/slug/)"
            m_link = re.match(r"^(\s*[-*]\s*)\[([^\]]+)\]\(([^)]+)\)\s*$", line)
            if m_link:
                prefix, anchor, href = m_link.group(1), m_link.group(2).strip(), m_link.group(3).strip()
                slug_match = re.match(r"^/blog/post/([^/]+)/?$", href)
                current_target = None
                if slug_match:
                    current_target = BlogPost.objects.filter(
                        slug=slug_match.group(1),
                        published_at__isnull=False,
                    ).exclude(pk=self.pk).first()
                if current_target and current_target.pk not in used_target_ids:
                    used_target_ids.add(current_target.pk)
                    out.append(f"{prefix}[{anchor}](/blog/post/{current_target.slug}/)")
                else:
                    # Repair missing/duplicate/bad links by re-resolving best target.
                    target = self._resolve_internal_link_target(anchor, excluded_ids=used_target_ids)
                    if target:
                        used_target_ids.add(target.pk)
                        out.append(f"{prefix}[{anchor}](/blog/post/{target.slug}/)")
                    else:
                        out.append(line)
                continue

            # Bare bracket line: "[Some title]"
            m2 = re.match(r"^\s*\[([^\]]+)\]\s*$", line)
            if m2:
                anchor = m2.group(1).strip()
                target = self._resolve_internal_link_target(anchor, excluded_ids=used_target_ids)
                if target:
                    used_target_ids.add(target.pk)
                    out.append(f"- [{anchor}](/blog/post/{target.slug}/)")
                else:
                    out.append(line)
                continue

            out.append(line)

        return "\n".join(out)

    def save(self, *args, **kwargs):
        # Normalize body + extract SEO metadata from paste format (before deriving title/excerpt/meta).
        cleaned_body, extracted_seo = self._clean_body_and_extract_seo((self.body or "").strip())
        if cleaned_body != (self.body or "").strip():
            self.body = cleaned_body
        self.body = self._autolink_internal_suggestions(self.body or "")

        # Auto-fill from extracted SEO metadata if fields are blank.
        if extracted_seo:
            if (not self.meta_title or not self.meta_title.strip()) and extracted_seo.get("title_tag"):
                self.meta_title = extracted_seo["title_tag"][:220]
            if (not self.meta_description or not self.meta_description.strip()) and extracted_seo.get("meta_description"):
                self.meta_description = extracted_seo["meta_description"][:320]
            if (not self.slug or not self.slug.strip()) and extracted_seo.get("suggested_slug"):
                suggested = extracted_seo["suggested_slug"].strip()
                # Accept "/foo/bar" or "foo" — we store only the slug part.
                suggested = suggested.split("?", 1)[0].strip()
                suggested = suggested.strip("/")
                if "/" in suggested:
                    suggested = suggested.split("/")[-1]
                suggested = slugify(suggested)[:180]
                if suggested:
                    self.slug = suggested
            if (not self.title or not self.title.strip()) and extracted_seo.get("title_tag"):
                self.title = extracted_seo["title_tag"][:220]

        if not self.title or not self.title.strip():
            self.title = self._extract_title_from_body()
        if not self.slug or not self.slug.strip():
            self.slug = self._build_unique_slug(self.title or self._extract_title_from_body() or "post")
        if not self.excerpt or not self.excerpt.strip():
            self.excerpt = self._auto_excerpt_from_body()
        if not self.meta_title or not self.meta_title.strip():
            self.meta_title = (self.title or "")[:220]
        if not self.meta_description or not self.meta_description.strip():
            self.meta_description = (self.excerpt or self._auto_excerpt_from_body())[:320]
        if not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)
