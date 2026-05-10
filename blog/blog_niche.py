"""
Blog topic gate for author-created posts from /admin/blog/new/ (dashboard).

Non-staff saves run `apply_blog_niche_gate=True` on BlogPost.save(); if no allowed
topic phrase appears in title + excerpt + body + meta, `published_at` stays empty.
"""

from __future__ import annotations

import re

ALLOWED_TOPIC_REGEXES: tuple[re.Pattern[str], ...] = (
    # Home tutoring / tutors
    re.compile(r"home\s*tutor(?:s|ing)?"),
    re.compile(r"tutor(?:ing)?\s+(?:at\s+)?home"),
    re.compile(r"private\s*tutor"),
    re.compile(r"personal\s*tutor"),
    # Exams / prep (aligned with RankJee)
    re.compile(r"online\s*exam"),
    re.compile(r"online\s*exams"),
    re.compile(r"mock\s*test"),
    re.compile(r"practice\s*test"),
    re.compile(r"\bjee\b"),
    re.compile(r"\bneet\b"),
    re.compile(r"\bcbse\b"),
    re.compile(r"\bicse\b"),
    # Courses / learning products
    re.compile(r"\bcourses?\b"),
    re.compile(r"online\s*course"),
    # Digital marketing stack (user list + close variants)
    re.compile(r"digital\s*marketing"),
    re.compile(r"(?<![a-z])seo(?![a-z])"),
    re.compile(r"local\s*seo"),
    re.compile(r"search\s*engine\s*optimi[sz]ation"),
    re.compile(r"meta\s*ads?"),
    re.compile(r"facebook\s*ads?"),
    re.compile(r"instagram\s*ads?"),
    re.compile(r"google\s*ads?"),
    re.compile(r"googles?\s*ads?"),  # common typo
    re.compile(r"email\s*marketing"),
    re.compile(r"(?<![a-z])ppc(?![a-z])"),
    re.compile(r"pay\s*per\s*click"),
    re.compile(r"(?<![a-z])sem(?![a-z])"),
    re.compile(r"paid\s*media"),
    re.compile(r"performance\s*marketing"),
)

NICHE_REQUIREMENT_USER_MESSAGE = (
    "Your post was saved but is not published yet. Include at least one clear topic phrase "
    "somewhere in the title, excerpt, body, or SEO fields — for example: "
    "home tutor / home tutoring, online exam / mock test, courses, "
    "digital marketing, SEO, local SEO, Meta ads, Google ads, email marketing, "
    "or closely related exam-prep or growth-marketing wording. Staff can publish any topic."
)


def combined_blog_search_blob(post) -> str:
    """Flatten searchable text from a BlogPost-like instance."""
    parts = [
        getattr(post, "title", None) or "",
        getattr(post, "excerpt", None) or "",
        getattr(post, "body", None) or "",
        getattr(post, "meta_title", None) or "",
        getattr(post, "meta_description", None) or "",
    ]
    raw = "\n".join(parts)
    low = raw.lower().replace("\u00a0", " ")
    low = re.sub(r"\s+", " ", low)
    return f"\n{low}\n"


def blog_post_matches_allowed_topics(post) -> tuple[bool, str]:
    """
    Return (matches, empty_reason_detail).

    Detail is empty when matches; otherwise a short diagnostic for logs/UI if needed.
    """
    blob = combined_blog_search_blob(post)
    if not blob.strip():
        return False, "empty_content"

    for rx in ALLOWED_TOPIC_REGEXES:
        if rx.search(blob):
            return True, ""

    return False, "no_allowed_topic_phrase"


