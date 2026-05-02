import json
import re

from django.core.paginator import Paginator
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

try:
    from markdown import markdown as md_markdown
except ModuleNotFoundError:  # pragma: no cover - defensive fallback for missing env dependency
    md_markdown = None

from .models import BlogPost

DEFAULT_BLOG_OG_IMAGE_URL = getattr(
    settings,
    "BLOG_DEFAULT_OG_IMAGE_URL",
    # HTTPS, permissive hotlinking for previews; override via settings if needed.
    "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=1200&q=80&auto=format&fit=crop",
)


def strip_template_preamble(text: str) -> str:
    """
    Remove planning/template preamble blocks often pasted before the real article.
    Keeps content from the first meaningful article heading onward.
    """
    if not text:
        return text

    lowered = text.lower()
    has_research_block = "phase 1: strategic research" in lowered
    has_seo_block = "seo metadata" in lowered
    if not (has_research_block or has_seo_block):
        return text

    lines = text.splitlines()
    saw_template_section = False

    for idx, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        low = s.lower()

        if "phase 1: strategic research" in low or "seo metadata" in low:
            saw_template_section = True
            continue

        # Start from first non-template markdown heading after template markers.
        if saw_template_section and s.startswith("#"):
            if "phase 1" not in low and "seo metadata" not in low:
                cleaned = "\n".join(lines[idx:]).strip()
                return cleaned or text

    return text


def _norm_heading(value: str) -> str:
    value = (value or "").lower().strip()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _title_tokens(value: str) -> set[str]:
    stop = {"how", "to", "the", "a", "an", "in", "for", "and", "of", "with", "without"}
    cleaned = _norm_heading(value)
    return {tok for tok in cleaned.split() if len(tok) > 2 and tok not in stop}


def strip_duplicate_title_heading(text: str, title: str) -> str:
    """
    If first meaningful markdown heading repeats the page title, remove it.
    Avoids double title display (template H1 + markdown H1).
    """
    if not text:
        return text
    target = _norm_heading(title)
    if not target:
        return text

    title_words = _title_tokens(title)
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        heading = re.match(r"^#{1,4}\s+(.+)$", s)
        if heading:
            heading_norm = _norm_heading(heading.group(1))
            heading_words = _title_tokens(heading.group(1))
            overlap = 0.0
            if title_words:
                overlap = len(title_words & heading_words) / len(title_words)
            if (
                heading_norm == target
                or heading_norm.startswith(target)
                or target.startswith(heading_norm)
                or overlap >= 0.6
            ):
                return "\n".join(lines[:idx] + lines[idx + 1 :]).strip()
            return text
        return text
    return text


def format_blog_body(text: str, post_title: str = ""):
    if not text:
        return mark_safe('')
    text = strip_template_preamble(text)
    text = strip_duplicate_title_heading(text, post_title)
    # Escape raw HTML first, then apply markdown so pasted content remains safe.
    safe_source = escape(text)
    if md_markdown is not None:
        html = md_markdown(
            safe_source,
            extensions=[
                'extra',       # tables, fenced code, footnotes, etc.
                'nl2br',       # preserve soft line breaks
                'sane_lists',  # cleaner list handling for pasted outlines
            ],
        )
        return mark_safe(html)

    # Fallback: no markdown package in current runtime env.
    def _inline(src: str) -> str:
        src = re.sub(r"`([^`]+)`", r"<code>\1</code>", src)
        src = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", src)
        src = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", src)
        src = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', src)
        return src

    lines = safe_source.replace("\r\n", "\n").split("\n")
    parts = []
    para = []
    in_ul = False
    in_ol = False

    def flush_para():
        nonlocal para
        if para:
            parts.append(f"<p>{_inline('<br>'.join(para))}</p>")
            para = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            flush_para()
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            if in_ol:
                parts.append("</ol>")
                in_ol = False
            continue

        if re.fullmatch(r"-{3,}", stripped):
            flush_para()
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            if in_ol:
                parts.append("</ol>")
                in_ol = False
            parts.append("<hr>")
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading:
            flush_para()
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            if in_ol:
                parts.append("</ol>")
                in_ol = False
            level = len(heading.group(1))
            parts.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue

        quote = re.match(r"^>\s+(.+)$", stripped)
        if quote:
            flush_para()
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            if in_ol:
                parts.append("</ol>")
                in_ol = False
            parts.append(f"<blockquote>{_inline(quote.group(1))}</blockquote>")
            continue

        ul = re.match(r"^[-*]\s+(.+)$", stripped)
        if ul:
            flush_para()
            if in_ol:
                parts.append("</ol>")
                in_ol = False
            if not in_ul:
                parts.append("<ul>")
                in_ul = True
            parts.append(f"<li>{_inline(ul.group(1))}</li>")
            continue

        ol = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ol:
            flush_para()
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            if not in_ol:
                parts.append("<ol>")
                in_ol = True
            parts.append(f"<li>{_inline(ol.group(1))}</li>")
            continue

        para.append(stripped)

    flush_para()
    if in_ul:
        parts.append("</ul>")
    if in_ol:
        parts.append("</ol>")
    return mark_safe("".join(parts))


def post_list(request):
    qs = BlogPost.objects.filter(published_at__isnull=False, published_at__lte=timezone.now()).select_related(
        'author', 'category'
    )
    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get('page') or 1)
    return render(
        request,
        'blog/list.jinja',
        {
            'page_obj': page,
            'posts': page.object_list,
            'default_blog_og_image_url': DEFAULT_BLOG_OG_IMAGE_URL,
            'seo_title': 'Exam prep & learning guides — RankJee Blog',
            'seo_description': 'Study strategies, mock test tips, and tutor insights from RankJee.',
            'canonical_url': request.build_absolute_uri(request.path),
        },
    )


def post_detail(request, slug):
    post = get_object_or_404(
        BlogPost.objects.select_related('author', 'category'),
        slug=slug,
        published_at__isnull=False,
        published_at__lte=timezone.now(),
    )
    related_qs = BlogPost.objects.filter(
        published_at__isnull=False,
        published_at__lte=timezone.now(),
    ).exclude(pk=post.pk)
    if post.category_id:
        related_posts = list(
            related_qs.filter(category_id=post.category_id).order_by('-published_at', '-pk')[:3]
        )
        if len(related_posts) < 3:
            needed = 3 - len(related_posts)
            existing_ids = [p.pk for p in related_posts]
            fallback = related_qs.exclude(pk__in=existing_ids).order_by('-published_at', '-pk')[:needed]
            related_posts.extend(list(fallback))
    else:
        related_posts = list(related_qs.order_by('-published_at', '-pk')[:3])
    seo_title = post.meta_title or f'{post.title} — RankJee Blog'
    seo_description = post.meta_description or (post.excerpt[:315] if post.excerpt else post.title)
    canonical = request.build_absolute_uri(request.path)
    published_iso = post.published_at.isoformat() if post.published_at else ''
    modified_iso = post.updated_at.isoformat() if post.updated_at else published_iso
    author_name = ''
    if post.author:
        author_name = post.author.get_full_name() or post.author.username or post.author.email or ''
    posting_ld = {
        '@context': 'https://schema.org',
        '@type': 'BlogPosting',
        'headline': post.title,
        'description': seo_description,
        'datePublished': published_iso,
        'dateModified': modified_iso,
        'publisher': {'@type': 'Organization', 'name': 'RankJee'},
        'mainEntityOfPage': {'@type': 'WebPage', '@id': canonical},
    }
    if author_name:
        posting_ld['author'] = {'@type': 'Person', 'name': author_name}

    blog_image_url = (
        request.build_absolute_uri(post.hero_image.url) if post.hero_image else DEFAULT_BLOG_OG_IMAGE_URL
    )
    posting_ld['image'] = blog_image_url

    breadcrumb_ld = {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {
                '@type': 'ListItem',
                'position': 1,
                'name': 'Home',
                'item': request.build_absolute_uri(reverse('core:home')),
            },
            {
                '@type': 'ListItem',
                'position': 2,
                'name': 'Blog',
                'item': request.build_absolute_uri(reverse('blog:index')),
            },
            {
                '@type': 'ListItem',
                'position': 3,
                'name': post.title,
                'item': canonical,
            },
        ],
    }
    return render(
        request,
        'blog/detail.jinja',
        {
            'post': post,
            'related_posts': related_posts,
            'body_html': format_blog_body(post.body, post.title),
            'seo_title': seo_title,
            'seo_description': seo_description,
            'canonical_url': canonical,
            'blog_image_url': blog_image_url,
            'blog_hero_is_upload': bool(post.hero_image),
            'blog_posting_ld_json': mark_safe(json.dumps(posting_ld, ensure_ascii=False)),
            'breadcrumb_ld_json': mark_safe(json.dumps(breadcrumb_ld, ensure_ascii=False)),
        },
    )
