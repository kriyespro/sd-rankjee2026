from django.db import migrations
from django.utils import timezone

SLUG = "how-to-prepare-for-jee-at-home-complete-self-study-blueprint"

BODY = """# How to Prepare for JEE at Home: A Complete Self-Study Blueprint

Most home prep fails for a boring reason: **no visible calendar**. Not talent. Not "lack of discipline." You wake up in the same room you scroll in—so your brain never gets a clean mode switch.

Here is the counter-intuitive fix we see work: treat JEE at home like a **small engineering project**. Requirements (syllabus), milestones (weekly targets), QA (mock tests), and incident response (mistake logs).

## The non-negotiable foundation (NCERT → sharp practice)

**NCERT isn't optional decoration** for conceptual chapters—it is the stabilizer. If your fundamentals wobble, every advanced problem becomes roulette.

- Pick **one** chapter this week. Read actively (examples included).
- Same day: **25 timed problems** spanning easy→medium.
- Next day: **only mistakes + variants** until accuracy crosses your threshold.

We are not chasing completion speed on day one. We are chasing **error half-life**.

## Your weekly architecture (copy-friendly skeleton)

**Monday–Friday (school/coaching absent or minimal):**

- **Block A (90 min):** New theory slice + solved examples (no phone in room).
- **Block B (60 min):** Drill set tied to yesterday's slice.
- **Block C (45 min):** **Previous year questions** or chapter-adjacent mixed set—mark "slow" IDs.

**Saturday:**

- **Half mock** (timed, honest) OR **two chapters consolidation** if mocks are already weekly elsewhere.

**Sunday:**

- **Analysis Sabbath:** no fresh syllabus. Only logs: *why* wrong, *what* pattern, *what* fix in next 72 hours.

If you skip Sunday analysis, Saturday's mock is entertainment—not training.

## Mock tests: the analysis loop that actually moves rank

Every mock should produce **three artifacts**:

1. **Topic ledger:** Physics/Chemistry/Math buckets—accuracy + time per bucket.
2. **Mistake tags:** calculation slip vs concept gap vs panic skip.
3. **72-hour plan:** three micro-drills tied only to top mistake tags.

Bold rule: **never start a new chapter until yesterday's mock leaks are scheduled.**

## Physics at home (when you cannot "feel" the lab)

Use **diagram-first** solving: force diagrams, constraint sketches, energy bookkeeping. If you cannot draw it, you do not understand it yet—only memorized words.

## Chemistry at home (memory without hallucination)

Split Organic/Inorganic/Physical honestly. Inorganic rewards **spaced repetition**; Organic rewards **mechanism arrows**; Physical rewards **units discipline**.

## Mathematics at home (speed is earned)

Speed without accuracy is negative marks waiting to happen. Sequence: accuracy → pattern recognition → timed bursts.

## Dropper / gap-year note (without melodrama)

If you are a dropper, your asset is **time clarity**—and your risk is drift. Use public accountability minimally: one study partner or one mentor check-in weekly, not twelve Discord servers.

## RankJee alignment (internal actions)

- Run **diagnostic / topic quizzes** on RankJee to feed your mistake ledger with structured weak tags—not vibes.
- When a chapter keeps exploding, pair self-study with **targeted help** (mentor/tutor) for that bottleneck only—otherwise you outsource your entire agency.

## FAQ

**Is JEE preparation at home enough without coaching?**
Yes for many students—if mocks + analysis + syllabus discipline exist. Coaching compresses guidance; it does not replace reps.

**How many hours per day for JEE self study at home?**
Quality beats counting. Begin with **two deep blocks** (≈3–4 hours focused) and scale only if recovery stays intact.

**NCERT vs advanced books—what ratio?**
Foundation phase: NCERT-heavy. Once accuracy stabilizes, add one advanced source per subject without abandoning revision loops.

**How often should I take mock tests?**
Start sustainable: **one full mock weekly** once basics exist; increase only if analysis stays honest.

**How do I avoid phone distraction at home?**
Physical separation beats willpower: phone outside room, website blockers on laptop, and a written "start ritual" (2 minutes) before Block A.
"""


def seed_jee_at_home_blueprint(apps, schema_editor):
    BlogCategory = apps.get_model("blog", "BlogCategory")
    BlogPost = apps.get_model("blog", "BlogPost")

    category, _ = BlogCategory.objects.get_or_create(
        slug="exam-strategy",
        defaults={"name": "Exam Strategy"},
    )

    BlogPost.objects.get_or_create(
        slug=SLUG,
        defaults={
            "title": "How to Prepare for JEE at Home: A Complete Self-Study Blueprint",
            "excerpt": (
                "Build a JEE Main self-study system at home: weekly timetable, NCERT→advanced bridge, "
                "mock analysis loop, and habits that prevent burnout."
            ),
            "body": BODY,
            "category_id": category.id,
            "meta_title": "How to Prepare for JEE at Home: Complete Self-Study Blueprint | RankJee",
            "meta_description": (
                "Build a JEE Main self-study system at home: weekly timetable, NCERT→advanced bridge, "
                "mock analysis loop, and sanity habits—without burning out."
            )[:320],
            "published_at": timezone.now(),
        },
    )


def unseed_jee_at_home_blueprint(apps, schema_editor):
    BlogPost = apps.get_model("blog", "BlogPost")
    BlogPost.objects.filter(slug=SLUG).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0004_seed_home_tutor_keyword_posts"),
    ]

    operations = [
        migrations.RunPython(seed_jee_at_home_blueprint, unseed_jee_at_home_blueprint),
    ]
