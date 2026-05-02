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
        lowered = raw.lower()
        if "phase 1: strategic research" not in lowered and "seo metadata" not in lowered:
            return raw
        lines = raw.splitlines()
        saw_template = False
        for idx, line in enumerate(lines):
            s = line.strip()
            if not s:
                continue
            low = s.lower()
            if "phase 1: strategic research" in low or "seo metadata" in low:
                saw_template = True
                continue
            if saw_template and s.startswith("#"):
                return "\n".join(lines[idx:]).strip()
        return raw

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

    def save(self, *args, **kwargs):
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
