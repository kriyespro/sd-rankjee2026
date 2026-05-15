"""
Management command: seed 20 flagship courses across 5 domains.

Usage:
    python manage.py seed_courses              # skip existing slugs
    python manage.py seed_courses --overwrite  # update all fields on existing
"""

from django.core.management.base import BaseCommand
from django.utils.text import slugify


COURSES = [
    # ──────────────── DIGITAL MARKETING (4) ────────────────
    {
        "title": "Digital Marketing Fundamentals",
        "short_description": "Master SEO, social media, content, and paid ads — a complete starter blueprint for modern digital marketers.",
        "description": (
            "## What you'll learn\n"
            "- Core digital marketing channels: SEO, SEM, Social, Email, Content\n"
            "- Building a brand online from scratch\n"
            "- Setting up Google Analytics 4 and Search Console\n"
            "- Running your first Facebook/Instagram ad campaign\n"
            "- Writing copy that converts\n\n"
            "## Who is this for\n"
            "Beginners, small business owners, or anyone looking to build a career in digital marketing.\n\n"
            "## What's included\n"
            "12 video modules · Live Q&A sessions · Practical assignments · Certificate on completion"
        ),
        "price_inr": "999",
        "duration_weeks": 4,
        "level": "Beginner",
        "is_featured": True,
    },
    {
        "title": "Social Media Marketing Mastery",
        "short_description": "Build engaged audiences on Instagram, LinkedIn, and YouTube with proven organic and paid growth strategies.",
        "description": (
            "## What you'll learn\n"
            "- Platform algorithms: Instagram Reels, LinkedIn newsletters, YouTube Shorts\n"
            "- Content calendar planning and batch creation\n"
            "- Community management and DM funnels\n"
            "- Influencer collaboration and UGC strategies\n"
            "- Analytics: tracking reach, engagement, and ROI\n\n"
            "## Who is this for\n"
            "Brand managers, freelancers, and entrepreneurs scaling on social media.\n\n"
            "## What's included\n"
            "16 video modules · Platform templates · Content calendar toolkit · Certificate"
        ),
        "price_inr": "1499",
        "duration_weeks": 6,
        "level": "Intermediate",
        "is_featured": False,
    },
    {
        "title": "Performance Marketing & Paid Ads",
        "short_description": "Run profitable Google, Meta, and YouTube ad campaigns — from audience research to ROAS optimization.",
        "description": (
            "## What you'll learn\n"
            "- Google Search, Display, Shopping, and Performance Max campaigns\n"
            "- Meta Ads: campaign structure, retargeting, lookalike audiences\n"
            "- YouTube TrueView and skippable ad formats\n"
            "- Conversion tracking with GTM and GA4\n"
            "- Budget allocation, bid strategies, and scaling winners\n\n"
            "## Who is this for\n"
            "Marketers who want to manage ₹1 lakh+ ad budgets profitably.\n\n"
            "## What's included\n"
            "20 video modules · Live campaign walkthroughs · Ad swipe file · Certificate"
        ),
        "price_inr": "1999",
        "duration_weeks": 8,
        "level": "Intermediate",
        "is_featured": True,
    },
    {
        "title": "Email Marketing & Automation",
        "short_description": "Build automated email sequences that nurture leads, recover abandoned carts, and generate recurring revenue.",
        "description": (
            "## What you'll learn\n"
            "- List building strategies and lead magnet design\n"
            "- Welcome sequences, drip campaigns, and re-engagement flows\n"
            "- Segmentation and personalisation at scale\n"
            "- A/B testing subject lines, CTAs, and send times\n"
            "- Tools: Mailchimp, Klaviyo, ConvertKit workflows\n\n"
            "## Who is this for\n"
            "Ecommerce store owners, SaaS founders, and digital marketers.\n\n"
            "## What's included\n"
            "14 video modules · Email swipe file (50+ templates) · Automation flowcharts · Certificate"
        ),
        "price_inr": "1299",
        "duration_weeks": 5,
        "level": "Intermediate",
        "is_featured": False,
    },

    # ──────────────── PROMPT ENGINEERING (4) ────────────────
    {
        "title": "Prompt Engineering for ChatGPT & Claude",
        "short_description": "Write prompts that get exceptional results from ChatGPT, Claude, and Gemini — for work, content, and business.",
        "description": (
            "## What you'll learn\n"
            "- Prompt anatomy: role, context, format, and constraints\n"
            "- Chain-of-thought, few-shot, and zero-shot prompting\n"
            "- Prompts for writing, coding, analysis, and research\n"
            "- System prompts and custom GPT creation\n"
            "- Prompt debugging and iterative refinement\n\n"
            "## Who is this for\n"
            "Professionals, students, and anyone who uses AI tools daily.\n\n"
            "## What's included\n"
            "10 video modules · 100+ prompt templates · Cheat sheet PDF · Certificate"
        ),
        "price_inr": "799",
        "duration_weeks": 3,
        "level": "Beginner",
        "is_featured": True,
    },
    {
        "title": "Advanced Prompt Engineering for Professionals",
        "short_description": "Master multi-step reasoning, structured outputs, and tool-use prompts to automate complex workflows with LLMs.",
        "description": (
            "## What you'll learn\n"
            "- ReAct, ToT (Tree of Thought), and self-consistency prompting\n"
            "- JSON and structured output prompting for APIs\n"
            "- Function calling and tool-use patterns\n"
            "- Prompt injection risks and defensive prompting\n"
            "- Building prompt pipelines for real business workflows\n\n"
            "## Who is this for\n"
            "Developers, product managers, and AI power users.\n\n"
            "## What's included\n"
            "15 video modules · Notebook library · Workflow templates · Certificate"
        ),
        "price_inr": "1499",
        "duration_weeks": 5,
        "level": "Advanced",
        "is_featured": False,
    },
    {
        "title": "Prompt Engineering for Content & Copywriting",
        "short_description": "Use AI prompts to write blogs, ads, product descriptions, and social posts 10× faster without losing your voice.",
        "description": (
            "## What you'll learn\n"
            "- Prompts for blog posts, newsletters, and long-form content\n"
            "- Ad copy frameworks: AIDA, PAS, BAB with AI\n"
            "- Maintaining brand voice across AI outputs\n"
            "- SEO-optimised content generation workflows\n"
            "- Editing and humanising AI-generated drafts\n\n"
            "## Who is this for\n"
            "Content creators, copywriters, and marketers.\n\n"
            "## What's included\n"
            "12 video modules · Content prompt library · Editing checklist · Certificate"
        ),
        "price_inr": "999",
        "duration_weeks": 4,
        "level": "Beginner",
        "is_featured": False,
    },
    {
        "title": "Prompt Engineering for Developers",
        "short_description": "Build LLM-powered applications with production-ready prompting patterns, API integration, and evaluation frameworks.",
        "description": (
            "## What you'll learn\n"
            "- OpenAI, Anthropic, and Gemini API integration\n"
            "- System prompt design for production apps\n"
            "- Retrieval-Augmented Generation (RAG) patterns\n"
            "- Hallucination reduction and output validation\n"
            "- Prompt versioning, testing, and evaluation with LangSmith\n\n"
            "## Who is this for\n"
            "Python developers building AI-powered products.\n\n"
            "## What's included\n"
            "18 video modules · GitHub repo · Project templates · Certificate"
        ),
        "price_inr": "1999",
        "duration_weeks": 6,
        "level": "Advanced",
        "is_featured": False,
    },

    # ──────────────── SEO (4) ────────────────────────────────
    {
        "title": "SEO Fundamentals & On-Page Optimization",
        "short_description": "Rank higher on Google by mastering keyword research, on-page SEO, and content structure the right way.",
        "description": (
            "## What you'll learn\n"
            "- How Google crawls, indexes, and ranks pages\n"
            "- Keyword research with Ahrefs, Semrush, and free tools\n"
            "- On-page SEO: titles, headers, meta, internal linking\n"
            "- Content clusters and topical authority\n"
            "- Measuring SEO performance with Search Console\n\n"
            "## Who is this for\n"
            "Bloggers, business owners, and marketing beginners.\n\n"
            "## What's included\n"
            "12 video modules · Keyword research spreadsheet · On-page checklist · Certificate"
        ),
        "price_inr": "999",
        "duration_weeks": 4,
        "level": "Beginner",
        "is_featured": True,
    },
    {
        "title": "Technical SEO & Site Architecture",
        "short_description": "Fix crawl issues, improve Core Web Vitals, and build a site structure that search engines love.",
        "description": (
            "## What you'll learn\n"
            "- Crawl budget management and robots.txt\n"
            "- XML sitemaps, canonicals, and hreflang\n"
            "- Core Web Vitals: LCP, INP, CLS optimisation\n"
            "- Structured data and rich results implementation\n"
            "- Log file analysis and crawl error diagnosis\n\n"
            "## Who is this for\n"
            "SEO professionals and web developers.\n\n"
            "## What's included\n"
            "16 video modules · Technical audit template · Schema markup library · Certificate"
        ),
        "price_inr": "1499",
        "duration_weeks": 6,
        "level": "Intermediate",
        "is_featured": False,
    },
    {
        "title": "Local SEO & Google Business Profile",
        "short_description": "Dominate local search results and Google Maps for your business with proven local SEO tactics.",
        "description": (
            "## What you'll learn\n"
            "- Google Business Profile optimisation (complete setup)\n"
            "- NAP consistency and local citations\n"
            "- Review generation and reputation management\n"
            "- Local keyword targeting and landing pages\n"
            "- Hyperlocal content strategy\n\n"
            "## Who is this for\n"
            "Local businesses, agencies, and consultants.\n\n"
            "## What's included\n"
            "10 video modules · GBP audit checklist · Citation tracker sheet · Certificate"
        ),
        "price_inr": "799",
        "duration_weeks": 3,
        "level": "Beginner",
        "is_featured": False,
    },
    {
        "title": "Programmatic SEO & AI-Driven Content",
        "short_description": "Build thousands of SEO-optimised landing pages at scale using templates, data, and AI content generation.",
        "description": (
            "## What you'll learn\n"
            "- Programmatic SEO architecture: templates + data sources\n"
            "- Building landing pages at scale with Django/Next.js\n"
            "- AI content generation pipelines for bulk production\n"
            "- Quality control: avoiding thin content and duplicate penalties\n"
            "- Sitemap automation, indexing API, and monitoring\n\n"
            "## Who is this for\n"
            "Developers and SEO professionals building data-driven sites.\n\n"
            "## What's included\n"
            "18 video modules · Django page generation starter kit · SEO audit tools · Certificate"
        ),
        "price_inr": "2499",
        "duration_weeks": 7,
        "level": "Advanced",
        "is_featured": True,
    },

    # ──────────────── AGENTIC AI (4) ────────────────────────
    {
        "title": "Introduction to Agentic AI",
        "short_description": "Understand how AI agents plan, reason, and act autonomously — and how to use them in your daily work.",
        "description": (
            "## What you'll learn\n"
            "- What makes AI agentic: planning, memory, tool use\n"
            "- Overview of AutoGPT, CrewAI, and ChatGPT Agents\n"
            "- Practical agentic workflows for research and writing\n"
            "- Risks, limitations, and responsible use of AI agents\n"
            "- Setting up your first no-code AI agent\n\n"
            "## Who is this for\n"
            "Non-technical professionals curious about AI automation.\n\n"
            "## What's included\n"
            "10 video modules · Use-case library · Workflow templates · Certificate"
        ),
        "price_inr": "999",
        "duration_weeks": 4,
        "level": "Beginner",
        "is_featured": True,
    },
    {
        "title": "Build AI Agents with LangChain & LangGraph",
        "short_description": "Develop production-ready AI agents using LangChain, LangGraph, and tool-calling APIs in Python.",
        "description": (
            "## What you'll learn\n"
            "- LangChain chains, agents, and memory modules\n"
            "- LangGraph for stateful, multi-step agent workflows\n"
            "- Connecting agents to APIs, databases, and file systems\n"
            "- ReAct and plan-and-execute agent patterns\n"
            "- Deploying agents as FastAPI endpoints\n\n"
            "## Who is this for\n"
            "Python developers building AI automation tools.\n\n"
            "## What's included\n"
            "20 video modules · GitHub project repo · Docker deployment guide · Certificate"
        ),
        "price_inr": "2499",
        "duration_weeks": 8,
        "level": "Intermediate",
        "is_featured": True,
    },
    {
        "title": "Multi-Agent Systems & AI Workflow Automation",
        "short_description": "Design multi-agent pipelines where specialised AI agents collaborate to complete complex, multi-step tasks.",
        "description": (
            "## What you'll learn\n"
            "- Multi-agent architecture: orchestrators, subagents, and critics\n"
            "- CrewAI and AutoGen frameworks in depth\n"
            "- Agent communication protocols and state sharing\n"
            "- Human-in-the-loop checkpoints and safety guardrails\n"
            "- Real-world pipelines: research, report generation, and data ops\n\n"
            "## Who is this for\n"
            "AI engineers and technical product managers.\n\n"
            "## What's included\n"
            "22 video modules · Multi-agent starter templates · Evaluation framework · Certificate"
        ),
        "price_inr": "3499",
        "duration_weeks": 10,
        "level": "Advanced",
        "is_featured": False,
    },
    {
        "title": "Agentic AI for Business Process Automation",
        "short_description": "Automate sales, operations, and customer support workflows using no-code and low-code AI agent platforms.",
        "description": (
            "## What you'll learn\n"
            "- Identifying automation opportunities in your business\n"
            "- Make (Integromat), Zapier, and n8n with AI nodes\n"
            "- Building AI-powered lead qualification and follow-up agents\n"
            "- Customer support automation with Voiceflow and Botpress\n"
            "- ROI calculation and change management for AI adoption\n\n"
            "## Who is this for\n"
            "Business owners, operations managers, and consultants.\n\n"
            "## What's included\n"
            "16 video modules · Automation blueprint library · ROI calculator · Certificate"
        ),
        "price_inr": "1999",
        "duration_weeks": 6,
        "level": "Intermediate",
        "is_featured": False,
    },

    # ──────────────── ECOMMERCE MANAGER (4) ─────────────────
    {
        "title": "Ecommerce Business Setup & Launch",
        "short_description": "Launch your online store from scratch — product selection, store setup, payment gateway, and first sales.",
        "description": (
            "## What you'll learn\n"
            "- Business model selection: own store vs marketplace vs D2C\n"
            "- Shopify / WooCommerce store setup step by step\n"
            "- Product photography, listings, and pricing strategy\n"
            "- Payment gateway integration (Razorpay, PayU, Stripe)\n"
            "- Shipping, returns, and fulfilment workflow\n\n"
            "## Who is this for\n"
            "First-time entrepreneurs and small business owners going online.\n\n"
            "## What's included\n"
            "14 video modules · Store setup checklist · Product listing templates · Certificate"
        ),
        "price_inr": "999",
        "duration_weeks": 4,
        "level": "Beginner",
        "is_featured": True,
    },
    {
        "title": "Amazon & Flipkart Seller Mastery",
        "short_description": "Rank products, win the Buy Box, and scale revenue on India's top marketplaces with data-driven tactics.",
        "description": (
            "## What you'll learn\n"
            "- Seller Central setup and account health management\n"
            "- Listing optimisation: keywords, images, A+ content\n"
            "- Pricing strategies and winning the Buy Box\n"
            "- Amazon PPC and Flipkart Smart ROI campaigns\n"
            "- Inventory management and FBA/FBF logistics\n\n"
            "## Who is this for\n"
            "Sellers and brand managers on Amazon India and Flipkart.\n\n"
            "## What's included\n"
            "18 video modules · PPC bid tracker · Listing audit template · Certificate"
        ),
        "price_inr": "1499",
        "duration_weeks": 6,
        "level": "Intermediate",
        "is_featured": False,
    },
    {
        "title": "Ecommerce Marketing & Conversion Optimisation",
        "short_description": "Drive more traffic and convert visitors into buyers with CRO, retargeting, and lifecycle marketing strategies.",
        "description": (
            "## What you'll learn\n"
            "- Full-funnel ecommerce marketing: awareness to retention\n"
            "- Google Shopping and Meta Dynamic Product Ads\n"
            "- Landing page CRO: heatmaps, A/B testing, urgency triggers\n"
            "- Abandoned cart recovery via email, SMS, and WhatsApp\n"
            "- Loyalty programmes and LTV maximisation\n\n"
            "## Who is this for\n"
            "Ecommerce managers and D2C brand owners.\n\n"
            "## What's included\n"
            "18 video modules · CRO audit framework · Ad creative swipe file · Certificate"
        ),
        "price_inr": "1999",
        "duration_weeks": 7,
        "level": "Intermediate",
        "is_featured": False,
    },
    {
        "title": "Ecommerce Operations & Growth Management",
        "short_description": "Scale your ecommerce brand with systems for operations, team management, analytics, and multi-channel expansion.",
        "description": (
            "## What you'll learn\n"
            "- Building SOPs for order management and customer support\n"
            "- Ecommerce P&L: unit economics, margins, and cash flow\n"
            "- Data analytics with GA4, Looker Studio, and Klaviyo\n"
            "- Multi-channel expansion: quick commerce, B2B, exports\n"
            "- Hiring and managing a lean ecommerce team\n\n"
            "## Who is this for\n"
            "Ecommerce founders and managers ready to scale past ₹10L/month.\n\n"
            "## What's included\n"
            "20 video modules · SOP library · Financial model template · Certificate"
        ),
        "price_inr": "2999",
        "duration_weeks": 8,
        "level": "Advanced",
        "is_featured": False,
    },
]


class Command(BaseCommand):
    help = "Seed 20 flagship courses across Digital Marketing, Prompt Engineering, SEO, Agentic AI, and Ecommerce."

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Update all fields for courses that already exist (matched by slug).",
        )

    def handle(self, *args, **options):
        from core.models import Course
        from decimal import Decimal

        overwrite = options["overwrite"]
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for data in COURSES:
            slug = slugify(data["title"])
            existing = Course.objects.filter(slug=slug).first()

            if existing and not overwrite:
                self.stdout.write(self.style.WARNING(f"  skip  {data['title']}"))
                skipped_count += 1
                continue

            course = existing or Course(slug=slug)
            course.title = data["title"]
            course.short_description = data["short_description"]
            course.description = data["description"]
            course.price_inr = Decimal(data["price_inr"])
            course.duration_weeks = data["duration_weeks"]
            course.level = data["level"]
            course.is_featured = data.get("is_featured", False)
            course.is_active = True
            course.save()

            if existing:
                self.stdout.write(self.style.SUCCESS(f"updated {course.title}"))
                updated_count += 1
            else:
                self.stdout.write(self.style.SUCCESS(f"created {course.title}"))
                created_count += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done — created: {created_count}, updated: {updated_count}, skipped: {skipped_count}"
            )
        )
        self.stdout.write(
            f"Total courses in DB: {Course.objects.count()}"
        )
        self.stdout.write(
            "Edit them at: /sd/core/course/"
        )
