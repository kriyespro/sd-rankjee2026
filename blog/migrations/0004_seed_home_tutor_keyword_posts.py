from django.db import migrations
from django.utils import timezone


SLUGS = (
    "home-tutors-near-me-guide",
    "online-home-tutors-india",
    "book-home-tutor-demo-rankjee",
    "private-tutor-at-home-vs-online",
    "verified-home-tutors-trust",
    "home-tutoring-fees-india-explained",
    "jee-preparation-home-tutor",
    "home-tutor-class-10-12-board-exams",
    "best-home-tutors-by-city",
    "request-tutor-demo-online",
)


def seed_home_tutor_posts(apps, schema_editor):
    BlogCategory = apps.get_model("blog", "BlogCategory")
    BlogPost = apps.get_model("blog", "BlogPost")

    category, _ = BlogCategory.objects.get_or_create(
        slug="home-tutors",
        defaults={"name": "Home Tutors"},
    )

    posts = [
        {
            "slug": "home-tutors-near-me-guide",
            "title": "Home Tutors Near Me: How to Shortlist Without Wasting a Semester",
            "excerpt": "Use city + subject + class filters, read verification signals, and book a demo before you commit to weekly slots.",
            "meta_title": "Home Tutors Near Me: Shortlist, Demo, Then Decide | RankJee",
            "meta_description": "Find home tutors near you with a clear checklist: local fit, subject depth, and a demo-first workflow on RankJee.",
            "body": (
                "Searching **home tutors near me** returns noise fast—every profile claims results. What you actually need is a repeatable filter: "
                "subject expertise for your board or entrance, schedule overlap, and proof that the tutor can teach *your* pace.\n\n"
                "Start with non-negotiables: class level, syllabus (CBSE, ICSE, State), and whether you want someone who travels to your home or teaches online with the same rigor.\n\n"
                "Next, look for consistency signals: described methodology, topic coverage, and availability—not only a low hourly quote.\n\n"
                "On RankJee, treat distance as one variable and **trust** as the main one. Use **request tutor demo online** as your first serious step: "
                "a short session beats a long phone chat.\n\n"
                "After the demo, decide weekly frequency and payment structure in writing. Clarity now prevents friction when exams approach.\n\n"
                "**Next step:** Browse tutors on RankJee at `/hometutor/`, filter by your city, then open profiles that match your subject stack."
            ),
        },
        {
            "slug": "online-home-tutors-india",
            "title": "Online Home Tutors in India: What Works (and What Breaks)",
            "excerpt": "Stable internet, shared notes, and demo-led matching beat generic ‘top tutor’ lists for Indian boards and competitive exams.",
            "meta_title": "Online Home Tutors India: Demo-Led Matching | RankJee Blog",
            "meta_description": "Choose online home tutors in India with structured demos, clear homework loops, and fee transparency—built for Indian syllabi.",
            "body": (
                "**Online home tutors India** is no longer a compromise—it is often the fastest way to access specialists for JEE segments, "
                "language skills, or niche boards without relocating.\n\n"
                "What breaks poor matches: vague homework, no accountability loop, and tutors who cannot adapt to your school’s question style.\n\n"
                "What works: a fixed weekly rhythm, shared PDFs or board snapshots of mistakes, and mini checkpoints before monthly renewal.\n\n"
                "RankJee treats tutoring like a product workflow: discover tutors, compare options, then **book home tutor demo** so you validate teaching style early.\n\n"
                "If you need hybrid support—online classes plus occasional in-person doubt clearing—state that upfront in your first message.\n\n"
                "**Next step:** Start from `/hometutor/` and shortlist two tutors; run demos before you lock in a package."
            ),
        },
        {
            "slug": "book-home-tutor-demo-rankjee",
            "title": "Book a Home Tutor Demo on RankJee (Before You Pay for the Month)",
            "excerpt": "Why demos matter, what to observe in 45 minutes, and how to convert a strong demo into a sustainable weekly plan.",
            "meta_title": "Book Home Tutor Demo on RankJee | RankJee Blog",
            "meta_description": "Learn how to book a home tutor demo on RankJee, what to evaluate live, and how to align fees and schedule after a strong trial.",
            "body": (
                "The phrase **book home tutor demo** should mean one thing: evidence before expense. A demo is not a sales pitch—it is a lesson sample.\n\n"
                "Bring real material: the last test paper, a chapter you failed, or three representative problems. Watch how the tutor diagnoses gaps versus jumping randomly.\n\n"
                "Observe pacing: do they check understanding every few minutes? Do they assign two crisp follow-ups instead of vague “study more”?\n\n"
                "On RankJee, keep **request tutor demo online** friction low: pick slots that mirror your real study windows so chemistry doesn’t break later.\n\n"
                "After a strong demo, align expectations—weekly hours, assignment policy, parent updates if needed—and only then discuss monthly commitments.\n\n"
                "**Next step:** Visit `/hometutor/my/requests/` to track demo status after you submit requests from tutor profiles."
            ),
        },
        {
            "slug": "private-tutor-at-home-vs-online",
            "title": "Private Tutor at Home vs Online: Picking the Right Mode for Your Child",
            "excerpt": "Younger learners often need presence; older students may prefer online specialists—here is a practical decision frame.",
            "meta_title": "Private Tutor at Home vs Online Tutoring | RankJee Blog",
            "meta_description": "Compare private tutor at home with online tutoring: attention span, logistics, safety, and exam outcomes—plus how RankJee demos help.",
            "body": (
                "Choosing between a **private tutor at home** and online coaching is not about fashion—it is about attention and logistics.\n\n"
                "Younger students often gain from in-person cues and handwriting correction; senior students chasing competitive exams may prioritize depth over proximity.\n\n"
                "Hybrid patterns work: online core classes plus monthly in-person doubt marathons if travel time is costly.\n\n"
                "Safety and boundaries matter for home visits. Confirm identity, references, and session windows—RankJee’s marketplace workflow pushes "
                "**verified home tutors** forward so families spend less time guessing.\n\n"
                "Whatever mode you pick, anchor on outcomes: error reduction in mocks, faster homework cycles, and clearer weekly goals.\n\n"
                "**Next step:** Explore `/hometutor/` and filter tutors who match your preferred mode before booking demos."
            ),
        },
        {
            "slug": "verified-home-tutors-trust",
            "title": "Verified Home Tutors: What Verification Should Mean for Families",
            "excerpt": "Stars are easy to fake—verification should tie to identity, teaching proof, and transparent engagement rules.",
            "meta_title": "Verified Home Tutors: Trust Signals That Matter | RankJee",
            "meta_description": "Understand what verified home tutors should represent—checks, clarity, and accountable demos—not vanity badges.",
            "body": (
                "When parents search **verified home tutors**, they want risk reduction: fewer no-shows, fewer inflated bios, fewer payment disputes.\n\n"
                "Strong verification combines documentation with behavior: consistent attendance, visible subject expertise, and professional communication.\n\n"
                "Families should still run their own smell test: request a structured demo, ask for a concrete plan for your syllabus week, and clarify cancellation rules.\n\n"
                "RankJee’s marketplace is built around discovery → demo → engagement so **best home tutors [city]** searches eventually meet accountability, not hype.\n\n"
                "Trust also means clarity on outcomes: what progress looks like in four weeks versus four days.\n\n"
                "**Next step:** Compare multiple profiles on `/hometutor/`, then prioritize tutors who welcome questions about methodology and reporting."
            ),
        },
        {
            "slug": "home-tutoring-fees-india-explained",
            "title": "Home Tutoring Fees in India: Questions That Protect Your Budget",
            "excerpt": "Per-session vs monthly packs, travel extras, and exam-season premiums—ask upfront so quotes stay honest.",
            "meta_title": "Home Tutoring Fees India: What to Ask Tutors | RankJee Blog",
            "meta_description": "Decode home tutoring fees in India: hourly vs monthly pricing, cancellation norms, and how demos help you compare value before paying.",
            "body": (
                "**Home tutoring fees India** vary wildly by city, subject difficulty, and tutor experience—so comparing quotes without context misleads families.\n\n"
                "Ask what is included: assessments, study material, test marking, WhatsApp doubt hours, and whether travel charges apply for **private tutor at home** visits.\n\n"
                "Monthly packages can save money but lock you in—demos reduce the chance you discover a mismatch after paying upfront.\n\n"
                "Exam-season premiums happen; negotiate clarity early instead of debating during boards.\n\n"
                "RankJee encourages families to pair fee clarity with workflow clarity: objectives, homework load, and escalation if sessions slip.\n\n"
                "**Next step:** After you shortlist tutors, align fee structure in writing after a successful demo—not before."
            ),
        },
        {
            "slug": "jee-preparation-home-tutor",
            "title": "JEE Preparation with a Home Tutor: Where a Specialist Actually Helps",
            "excerpt": "Drills, error analytics, and chapter sequencing beat passive watching—use tutors for bottlenecks, not motivation speeches.",
            "meta_title": "JEE Preparation Home Tutor: Specialist Bottlenecks | RankJee",
            "meta_description": "Use a JEE preparation home tutor for targeted concept fixes, timed drills, and mistake analysis—plus how to book demos on RankJee.",
            "body": (
                "A **JEE preparation home tutor** earns their fee when they shrink time-to-fix on hard chapters—mechanics, rotation, electrochemistry, integration tricks—not when they repeat generic theory.\n\n"
                "Bring data: recent mock percentile, topic-level accuracy, and your fastest-growing error types.\n\n"
                "Demand structured homework: small question sets with difficulty ramp and same-week correction.\n\n"
                "Pair tutoring with your own test rhythm; tutors amplify discipline but cannot replace daily problem volume.\n\n"
                "RankJee also connects practice tests with tutor discovery so **online home tutors India** specialists can align with your diagnostic gaps.\n\n"
                "**Next step:** Book demos with tutors who show past student workflows—not vague promise lists—and confirm weekly availability through exam season."
            ),
        },
        {
            "slug": "home-tutor-class-10-12-board-exams",
            "title": "Home Tutor for Class 10 & 12 Board Exams: Schedule, Writing Practice, Peace",
            "excerpt": "Board prep needs answer-writing discipline and predictable revision—your tutor should own both with weekly checkpoints.",
            "meta_title": "Home Tutor for Class 10 & 12 Boards | RankJee Blog",
            "meta_description": "Hire a home tutor for Class 10 and 12 board exams with writing drills, PYQ cycles, and parent-friendly progress updates.",
            "body": (
                "The right **home tutor for Class 10 12** pressure is not always the cheapest—it is the one who installs routine: revision maps, timed writing, and error logs.\n\n"
                "Board exams punish careless presentation; insist on evaluated answers, not only lectures.\n\n"
                "Balance school homework with tutor assignments—overload burns students two weeks before papers.\n\n"
                "Parents should ask for a simple weekly summary: chapters covered, confidence signals, and upcoming milestones.\n\n"
                "RankJee helps families move from search → **book home tutor demo** → steady engagement without losing weeks to unstructured trials.\n\n"
                "**Next step:** Filter tutors by board relevance on `/hometutor/`, then validate teaching style with a paid or structured trial aligned to your syllabus."
            ),
        },
        {
            "slug": "best-home-tutors-by-city",
            "title": "Best Home Tutors by City: How to Search Without Chasing Rankings",
            "excerpt": "City-wise discovery works when you combine locality with subject depth—use landing filters and demos to validate fit.",
            "meta_title": "Best Home Tutors by City: Local Discovery Tips | RankJee",
            "meta_description": "Find the best home tutors in your city using structured filters, demos, and verification signals—RankJee marketplace playbook.",
            "body": (
                "Typing **best home tutors [city]** should start locally but validate academically—proximity matters only after competence is proven.\n\n"
                "Use city filters to shrink commute stress, especially for younger learners or late-evening slots.\n\n"
                "Subject breadth differs by metro; compare tutors who actively teach your board’s question patterns, not generic international curricula unless that is your goal.\n\n"
                "Demos remain the equalizer: two strong tutors in the same city may feel totally different for your child’s attention profile.\n\n"
                "RankJee’s `/hometutor/` flows support city-aware browsing so families combine **home tutors near me** intent with accountable engagement paths.\n\n"
                "**Next step:** Open city or subject landing pages when available, then shortlist three profiles and run two demos maximum before deciding."
            ),
        },
        {
            "slug": "request-tutor-demo-online",
            "title": "Request a Tutor Demo Online: Checklist for a 10/10 First Session",
            "excerpt": "Send syllabus context, pick a focused topic, and define success before the call—demos fail when goals are fuzzy.",
            "meta_title": "Request Tutor Demo Online: First Session Checklist | RankJee",
            "meta_description": "Request a tutor demo online with clear goals, materials, and success criteria—RankJee-friendly checklist for parents and students.",
            "body": (
                "When you **request tutor demo online**, treat it like a scoped workshop—not an open conversation.\n\n"
                "Share class, board, and one painful topic. Upload or describe a recent test mistake pattern.\n\n"
                "Define success: “Can this tutor explain why I drop marks in 5-mark questions?” beats “Let’s see how it goes.”\n\n"
                "Logistics matter: stable audio, a quiet desk, and digital scratch paper or notebook ready.\n\n"
                "Afterward, score the demo on clarity, homework assignment quality, and professionalism—then decide fast so slots don’t disappear.\n\n"
                "RankJee keeps demos tied to real profiles so **verified home tutors** and serious learners waste less time.\n\n"
                "**Next step:** From any tutor profile, complete demo scheduling, then track progress under `/hometutor/my/requests/`."
            ),
        },
    ]

    now = timezone.now()
    for item in posts:
        BlogPost.objects.get_or_create(
            slug=item["slug"],
            defaults={
                "title": item["title"],
                "excerpt": item["excerpt"],
                "body": item["body"],
                "category_id": category.id,
                "meta_title": item["meta_title"],
                "meta_description": item["meta_description"],
                "published_at": now,
            },
        )


def unseed_home_tutor_posts(apps, schema_editor):
    BlogPost = apps.get_model("blog", "BlogPost")
    BlogCategory = apps.get_model("blog", "BlogCategory")
    BlogPost.objects.filter(slug__in=SLUGS).delete()
    cat = BlogCategory.objects.filter(slug="home-tutors").first()
    if cat and not BlogPost.objects.filter(category_id=cat.id).exists():
        cat.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0003_seed_more_blog_posts"),
    ]

    operations = [
        migrations.RunPython(seed_home_tutor_posts, unseed_home_tutor_posts),
    ]
