"""Normalize pasted study notes and render safe HTML (markdown)."""

from __future__ import annotations

import codecs
import html as html_module
import json
import re

from markupsafe import Markup, escape

try:
    from markdown import markdown as md_markdown
except ImportError:  # pragma: no cover
    md_markdown = None

_AI_FOOTER_MARKERS = (
    '\n# EXECUTION COMMAND:',
    '\n## PHASE 4: FINAL INTEGRATION',
    '\n"I am ready. Please provide the topic',
)

_GARBAGE_LINE_RE = re.compile(
    r'^[-*]?\s*`{0,2}\s*$',
)


def normalize_study_body_text(text: str) -> str:
    """Fix JSON/API copy-paste where line breaks were stored as literal \\n or \\r\\n."""
    if not text:
        return ''
    text = text.strip()
    text = html_module.unescape(text)

    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        try:
            text = json.loads(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    text = text.replace('&#92;r&#92;n', '\n').replace('&#92;n', '\n').replace('&#92;r', '\n')

    for _ in range(8):
        prev = text
        text = (
            text.replace('\\\\r\\\\n', '\n')
            .replace('\\\\n', '\n')
            .replace('\\\\r', '\n')
            .replace('\\r\\n', '\n')
            .replace('\\n', '\n')
            .replace('\\r', '\n')
            .replace('\\t', '\t')
        )
        if text == prev:
            break

    text = re.sub(r'\\+n', '\n', text)
    text = re.sub(r'\\+r', '\n', text)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'^`+', '', text)

    if re.search(r'\\u[0-9a-fA-F]{4}', text):
        try:
            text = codecs.decode(text, 'unicode_escape')
        except (UnicodeDecodeError, ValueError):
            pass

    for marker in _AI_FOOTER_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx].strip()

    lines = []
    for ln in text.split('\n'):
        if _GARBAGE_LINE_RE.match(ln.strip()):
            continue
        if ln.strip() in {'``', '`', '- ``', '- `', '* ``'}:
            continue
        lines.append(ln)
    return '\n'.join(lines).strip()


def _cleanup_study_html(html: str) -> str:
    html = re.sub(r'<li>\s*</li>', '', html)
    html = re.sub(r'<li>\s*`{1,2}\s*</li>', '', html)
    html = re.sub(r'<p>\s*</p>', '', html)
    return html


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
        if not stripped or stripped in {'``', '`'}:
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
            item = ul.group(1).strip()
            if item in {'``', '`'}:
                continue
            flush_para()
            if not in_ul:
                parts.append('<ul>')
                in_ul = True
            parts.append(f'<li>{_inline(item)}</li>')
            continue

        if in_ul:
            parts.append('</ul>')
            in_ul = False
        para.append(stripped)

    flush_para()
    if in_ul:
        parts.append('</ul>')
    return ''.join(parts)


def format_study_body_html(text: str) -> Markup:
    """Return safe HTML for study material body (markdown + pasted line fixes)."""
    text = normalize_study_body_text(text)
    if not text:
        return Markup('')
    safe_source = escape(text)
    if md_markdown is not None:
        html = md_markdown(
            str(safe_source),
            extensions=[
                'extra',
                'nl2br',
                'sane_lists',
            ],
        )
        return Markup(_cleanup_study_html(html))
    return Markup(_cleanup_study_html(_fallback_html(str(safe_source))))
