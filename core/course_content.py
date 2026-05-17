"""Resolve course page copy — admin JSON overrides with smart defaults."""


def _topic_count(course) -> int:
    curriculum = course.curriculum or []
    return sum(len(m.get("topics") or []) for m in curriculum)


def resolve_hero_usps(course, total_topics: int | None = None) -> list[str]:
    """Left hero bullet lines (plain text; use **bold** markers optional — rendered as HTML in template)."""
    custom = course.hero_usps or []
    if custom:
        return [str(line).strip() for line in custom if str(line).strip()]

    topics = total_topics if total_topics is not None else _topic_count(course)
    lines = []
    if course.curriculum:
        mod_n = len(course.curriculum)
        lines.append(
            f"**{mod_n} structured modules** covering {topics}+ hands-on topics — "
            "from foundations to production deployment"
        )
    lines.append(
        "**Earn a verified certificate** on completion — recognized by employers across India"
    )
    if course.salary_after_min and course.salary_after_max:
        lines.append(
            f"**₹{int(course.salary_after_min)}–{int(course.salary_after_max)} LPA** expected salary range "
            "for graduates in the Indian job market"
        )
    return lines


def resolve_gain_outcomes(course, total_topics: int | None = None) -> list[str]:
    custom = course.gain_outcomes or []
    if custom:
        return [str(line).strip() for line in custom if str(line).strip()]

    topics = total_topics if total_topics is not None else _topic_count(course)
    lines = []
    if course.curriculum:
        mod_n = len(course.curriculum)
        lines.append(
            f"Master **{mod_n} modules** · {topics}+ hands-on lessons"
            if topics
            else f"Master **{mod_n} modules** with hands-on lessons"
        )
        lines.append("Build **portfolio-ready projects** you can demo to hiring managers")
    else:
        lines.append("**Job-ready skills** with structured, self-paced lessons")
    lines.append("Earn a **verified RankJee certificate** recognized by employers")
    return lines


def resolve_gain_perks(course) -> list[str]:
    custom = course.gain_perks or []
    if custom:
        return [str(line).strip() for line in custom if str(line).strip()]
    return [
        "Self-paced video lessons — learn on your schedule",
        "Live mentor Q&A & community support",
        "Verified certificate · lifetime full access",
    ]


def resolve_course_includes(course) -> list[str]:
    custom = course.course_includes or []
    if custom:
        return [str(line).strip() for line in custom if str(line).strip()]
    weeks = course.duration_weeks or 4
    return [
        f"{weeks} weeks of on-demand content",
        "Completion certificate",
        "Hands-on assignments & projects",
        "Live mentor Q&A support",
        "Mobile & desktop access",
        "Lifetime access",
    ]


def format_bold_markers(text: str) -> str:
    """Turn **phrase** into <strong>phrase</strong> for safe display."""
    import re

    def repl(match):
        return f"<strong>{match.group(1)}</strong>"

    return re.sub(r"\*\*(.+?)\*\*", repl, text)
