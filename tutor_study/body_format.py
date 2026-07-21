"""Normalize pasted study notes and render safe HTML (markdown)."""

from __future__ import annotations

import re

from django.utils.html import escape
from django.utils.safestring import mark_safe

try:
    from markdown import markdown as md_markdown
except ImportError:  # pragma: no cover
    md_markdown = None


def normalize_study_body_text(text: str) -> str:
    """Fix Windows / JSON / API copy-paste line endings stored as literal \\r\\n."""
    if not text:
        return ''
    text = text.replace('\\\\r\\\\n', '\n')
    text = text.replace('\\\\n', '\n')
    text = text.replace('\\\\r', '\n')
    text = text.replace('\\r\\n', '\n')
    text = text.replace('\\n', '\n')
    text = text.replace('\\r', '\n')
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')
    return text


def _fallback_html(safe_source: str) -> str:
    """Minimal markdown-ish renderer when the Markdown package is unavailable."""

    def _inline(src: str) -> str:
        src = re.sub(r'`([^`]+)`', r'<code>\1</code>', src)
        src = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', src)
        src = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', src)
        src = re.sub(
            r'\[([^\]]+)\]\((https?://[^)]+)\)',
            r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
            src,
        )
        return src

    lines = safe_source.split('\n')
    parts: list[str] = []
    para: list[str] = []
    in_ul = False

    def flush_para() -> None:
        nonlocal para
        if para:
            parts.append(f'<p class="study-prose">{_inline("<br>".join(para))}</p>')
            para = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_para()
            if in_ul:
                parts.append('</ul>')
                in_ul = False
            continue

        heading = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if heading:
            flush_para()
            if in_ul:
                parts.append('</ul>')
                in_ul = False
            level = len(heading.group(1))
            parts.append(f'<h{level}>{_inline(heading.group(2))}</h{level}>')
            continue

        ul = re.match(r'^[-*]\s+(.+)$', stripped)
        if ul:
            flush_para()
            if not in_ul:
                parts.append('<ul>')
                in_ul = True
            parts.append(f'<li>{_inline(ul.group(1))}</li>')
            continue

        if in_ul:
            parts.append('</ul>')
            in_ul = False
        para.append(stripped)

    flush_para()
    if in_ul:
        parts.append('</ul>')
    return ''.join(parts)


def format_study_body_html(text: str):
    """Return safe HTML for study material body (markdown + pasted line fixes)."""
    text = normalize_study_body_text(text)
    if not text:
        return mark_safe('')
    safe_source = escape(text)
    if md_markdown is not None:
        html = md_markdown(
            safe_source,
            extensions=[
                'extra',
                'nl2br',
                'sane_lists',
            ],
        )
        return mark_safe(html)
    return mark_safe(_fallback_html(safe_source))
