"""
Management command: seed 20 flagship courses across 5 domains.

Usage:
    python manage.py seed_courses              # skip existing slugs
    python manage.py seed_courses --overwrite  # update all fields on existing
"""

from django.core.management.base import BaseCommand
from django.utils.text import slugify


COURSES = [
    # ══════════════ DIGITAL MARKETING (4) ══════════════
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
        "salary_after_min": "3.5",
        "salary_after_max": "7.0",
        "job_roles": "Digital Marketing Executive, Social Media Manager, Content Strategist, SEO Analyst, Marketing Coordinator",
        "curriculum": [
            {"module": "M1", "title": "Digital Marketing Landscape", "topics": ["What is digital marketing?", "Channels overview", "Setting SMART goals"]},
            {"module": "M2", "title": "SEO Basics", "topics": ["Keyword research", "On-page SEO", "Google Search Console setup"]},
            {"module": "M3", "title": "Social Media Marketing", "topics": ["Platform selection", "Content calendar", "Organic growth tactics"]},
            {"module": "M4", "title": "Paid Advertising Intro", "topics": ["Google Ads basics", "Facebook & Instagram Ads", "Budget management"]},
            {"module": "M5", "title": "Content & Email Marketing", "topics": ["Blog writing for SEO", "Email list building", "Newsletter best practices"]},
            {"module": "M6", "title": "Analytics & Reporting", "topics": ["Google Analytics 4", "KPIs and dashboards", "Campaign reporting"]},
        ],
        "testimonials": [
            {"name": "Anika Sharma", "role": "Social Media Executive", "city": "Jaipur", "text": "I landed my first marketing job within 3 weeks of finishing this course. The hands-on assignments made all the difference.", "rating": 5},
            {"name": "Rahul Verma", "role": "Freelance Digital Marketer", "city": "Pune", "text": "Super practical. No fluff — just real strategies I could apply immediately to my clients.", "rating": 5},
            {"name": "Sneha Patil", "role": "Content Strategist", "city": "Mumbai", "text": "The SEO and Analytics modules alone were worth the price. My organic traffic doubled in 2 months.", "rating": 4},
        ],
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
        "salary_after_min": "4.0",
        "salary_after_max": "9.0",
        "job_roles": "Social Media Manager, Instagram Growth Strategist, Community Manager, Brand Influencer Manager, LinkedIn Marketer",
        "curriculum": [
            {"module": "M1", "title": "Platform Deep Dives", "topics": ["Instagram algorithm 2025", "LinkedIn creator tools", "YouTube Shorts strategy"]},
            {"module": "M2", "title": "Content Creation System", "topics": ["Batch content creation", "Hook writing", "Reels scripting framework"]},
            {"module": "M3", "title": "Audience Growth", "topics": ["Hashtag research", "Engagement pods", "Collab & UGC campaigns"]},
            {"module": "M4", "title": "Paid Social Ads", "topics": ["Meta Ads Manager", "Retargeting audiences", "Ad creative testing"]},
            {"module": "M5", "title": "Influencer Marketing", "topics": ["Finding micro-influencers", "Brief writing", "ROI measurement"]},
            {"module": "M6", "title": "Analytics & Scaling", "topics": ["Platform native analytics", "Third-party tools", "Scaling what works"]},
        ],
        "testimonials": [
            {"name": "Meera Nair", "role": "Instagram Manager", "city": "Kochi", "text": "My client's Instagram went from 2K to 18K followers in 4 months using the strategies here.", "rating": 5},
            {"name": "Vikram Singh", "role": "Brand Manager", "city": "Delhi", "text": "The paid ads section was incredibly detailed. Saved ₹30K+ in wasted ad spend in my first month.", "rating": 5},
            {"name": "Priya Desai", "role": "Freelancer", "city": "Surat", "text": "Content calendar template alone saved me hours every week. Best investment I've made.", "rating": 4},
        ],
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
        "salary_after_min": "5.0",
        "salary_after_max": "14.0",
        "job_roles": "Performance Marketing Manager, PPC Specialist, Google Ads Expert, Media Buyer, Growth Marketer",
        "curriculum": [
            {"module": "M1", "title": "Paid Ads Foundations", "topics": ["Auction mechanics", "Quality Score", "Ad rank factors"]},
            {"module": "M2", "title": "Google Search Ads", "topics": ["Keyword match types", "Ad copy formulas", "Smart bidding strategies"]},
            {"module": "M3", "title": "Google Shopping & PMax", "topics": ["Feed optimisation", "Performance Max setup", "Shopping campaign structure"]},
            {"module": "M4", "title": "Meta Ads Deep Dive", "topics": ["Campaign objectives", "Audience targeting", "Creative testing at scale"]},
            {"module": "M5", "title": "YouTube Ads", "topics": ["TrueView campaigns", "Skippable vs non-skippable", "Audience sequencing"]},
            {"module": "M6", "title": "Tracking & Attribution", "topics": ["GTM setup", "GA4 conversions", "Multi-touch attribution"]},
            {"module": "M7", "title": "Budget & Scaling", "topics": ["Budget allocation frameworks", "ROAS targets", "Scaling profitable campaigns"]},
            {"module": "M8", "title": "Reporting & Client Management", "topics": ["Dashboard building", "Looker Studio reports", "Client communication templates"]},
        ],
        "testimonials": [
            {"name": "Arjun Mehta", "role": "PPC Manager", "city": "Bengaluru", "text": "I was managing ₹5L/month in ad spend and struggling. After this course I cut CPA by 40% within 6 weeks.", "rating": 5},
            {"name": "Divya Kapoor", "role": "Performance Marketer", "city": "Mumbai", "text": "The Google Shopping and PMax modules are unmatched anywhere online. Highly technical and practical.", "rating": 5},
            {"name": "Sanjay Tiwari", "role": "Media Buyer", "city": "Hyderabad", "text": "Got a 60% salary hike after completing this. Companies are desperate for people who can actually run profitable ads.", "rating": 5},
        ],
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
        "salary_after_min": "4.0",
        "salary_after_max": "10.0",
        "job_roles": "Email Marketing Specialist, CRM Manager, Marketing Automation Analyst, Lifecycle Marketer, Retention Specialist",
        "curriculum": [
            {"module": "M1", "title": "Email Marketing Basics", "topics": ["Deliverability fundamentals", "Domain warming", "List hygiene"]},
            {"module": "M2", "title": "List Building", "topics": ["Lead magnet creation", "Opt-in forms", "Landing page integrations"]},
            {"module": "M3", "title": "Automation Flows", "topics": ["Welcome series", "Abandoned cart recovery", "Win-back campaigns"]},
            {"module": "M4", "title": "Segmentation & Personalisation", "topics": ["Behaviour-based segments", "Dynamic content", "Send-time optimisation"]},
            {"module": "M5", "title": "Testing & Analytics", "topics": ["A/B testing framework", "Open & click benchmarks", "Revenue attribution"]},
        ],
        "testimonials": [
            {"name": "Kavita Rao", "role": "Ecommerce Owner", "city": "Chennai", "text": "My abandoned cart sequence generates ₹40K extra per month. This course paid for itself 40× over.", "rating": 5},
            {"name": "Nikhil Sharma", "role": "CRM Specialist", "city": "Pune", "text": "The Klaviyo walkthroughs are excellent. I implemented everything step by step and saw results immediately.", "rating": 4},
            {"name": "Ananya Joshi", "role": "Marketing Automation Analyst", "city": "Ahmedabad", "text": "Landed a job at a D2C brand at ₹6 LPA after finishing this course. The certificate helped a lot.", "rating": 5},
        ],
    },

    # ══════════════ PROMPT ENGINEERING (4) ══════════════
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
        "salary_after_min": "4.0",
        "salary_after_max": "12.0",
        "job_roles": "AI Prompt Engineer, AI Content Specialist, Automation Consultant, AI Tools Trainer, Freelance AI Consultant",
        "curriculum": [
            {"module": "M1", "title": "Prompt Anatomy", "topics": ["Role + context framework", "Constraint setting", "Output format control"]},
            {"module": "M2", "title": "Core Prompting Techniques", "topics": ["Zero-shot prompting", "Few-shot examples", "Chain-of-thought"]},
            {"module": "M3", "title": "Practical Use Cases", "topics": ["Writing & summarisation", "Data analysis prompts", "Code generation"]},
            {"module": "M4", "title": "Custom GPTs & System Prompts", "topics": ["Building custom GPTs", "System prompt design", "GPT Store publishing"]},
            {"module": "M5", "title": "Prompt Debugging", "topics": ["Diagnosing bad outputs", "Iterative refinement", "Prompt evaluation checklist"]},
        ],
        "testimonials": [
            {"name": "Rohan Gupta", "role": "Content Writer", "city": "Delhi", "text": "I produce 3× more content in the same time. This course changed how I work completely.", "rating": 5},
            {"name": "Sarita Menon", "role": "HR Manager", "city": "Bengaluru", "text": "I use prompts for job descriptions, performance reviews, and training docs. Saves me 6+ hours a week.", "rating": 5},
            {"name": "Kunal Jain", "role": "Freelance Consultant", "city": "Indore", "text": "Clients now pay me ₹15K/month just to manage their ChatGPT workflows. Best course I've done.", "rating": 5},
        ],
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
        "salary_after_min": "8.0",
        "salary_after_max": "22.0",
        "job_roles": "Prompt Engineer, LLM Product Manager, AI Workflow Architect, AI Consultant, NLP Specialist",
        "curriculum": [
            {"module": "M1", "title": "Advanced Reasoning Patterns", "topics": ["ReAct prompting", "Tree of Thought", "Self-consistency technique"]},
            {"module": "M2", "title": "Structured Outputs", "topics": ["JSON mode prompting", "Pydantic output validation", "Schema-constrained generation"]},
            {"module": "M3", "title": "Function Calling & Tool Use", "topics": ["OpenAI function calling", "Anthropic tool use", "Multi-step tool chains"]},
            {"module": "M4", "title": "Prompt Security", "topics": ["Prompt injection attacks", "Jailbreaking risks", "Defensive prompting patterns"]},
            {"module": "M5", "title": "Pipeline Automation", "topics": ["Multi-prompt chains", "Conditional routing", "LangChain LCEL basics"]},
        ],
        "testimonials": [
            {"name": "Aditya Nair", "role": "AI Product Manager", "city": "Hyderabad", "text": "This is the most technically rigorous prompt engineering course I've found. The structured output section alone is worth the price.", "rating": 5},
            {"name": "Pooja Reddy", "role": "LLM Developer", "city": "Bengaluru", "text": "Finally a course that treats prompt engineering seriously. Got a 35% salary bump after adding this to my resume.", "rating": 5},
            {"name": "Manish Kumar", "role": "AI Consultant", "city": "Gurgaon", "text": "The prompt security module opened my eyes to risks I was completely ignoring. Essential knowledge.", "rating": 4},
        ],
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
        "salary_after_min": "3.5",
        "salary_after_max": "9.0",
        "job_roles": "AI Content Writer, Copywriter, Content Strategist, Social Media Writer, Email Copywriter",
        "curriculum": [
            {"module": "M1", "title": "AI Writing Foundations", "topics": ["Choosing the right AI model", "Prompting for tone and style", "Brand voice preservation"]},
            {"module": "M2", "title": "Long-Form Content", "topics": ["Blog post structure prompts", "Research and outline generation", "SEO-optimised drafts"]},
            {"module": "M3", "title": "Ad Copywriting with AI", "topics": ["AIDA framework prompts", "PAS and BAB templates", "Facebook & Google ad copy"]},
            {"module": "M4", "title": "Social & Email Copy", "topics": ["Instagram captions", "LinkedIn posts", "Email subject lines & CTAs"]},
            {"module": "M5", "title": "Editing AI Outputs", "topics": ["Humanising AI text", "Fact-checking workflow", "Final polish checklist"]},
        ],
        "testimonials": [
            {"name": "Riya Bansal", "role": "Content Creator", "city": "Lucknow", "text": "I went from writing 2 blogs a week to 10. My freelance income doubled in 60 days.", "rating": 5},
            {"name": "Tarun Mathur", "role": "Copywriter", "city": "Jaipur", "text": "The ad copy templates are 🔥. My clients' conversion rates jumped 30% after I started using these.", "rating": 5},
            {"name": "Neha Agarwal", "role": "Social Media Manager", "city": "Ahmedabad", "text": "I can now write a month of Instagram content in one afternoon. Game changer.", "rating": 4},
        ],
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
        "salary_after_min": "10.0",
        "salary_after_max": "28.0",
        "job_roles": "AI Engineer, LLM Application Developer, Backend AI Developer, ML Ops Engineer, AI Product Builder",
        "curriculum": [
            {"module": "M1", "title": "LLM APIs in Production", "topics": ["OpenAI & Anthropic API setup", "Token management", "Rate limiting & error handling"]},
            {"module": "M2", "title": "System Prompt Engineering", "topics": ["Production system prompt patterns", "Context window optimisation", "Multi-turn conversation design"]},
            {"module": "M3", "title": "RAG Systems", "topics": ["Vector database setup", "Chunking & embedding strategies", "Retrieval quality tuning"]},
            {"module": "M4", "title": "Output Validation", "topics": ["Hallucination detection", "Pydantic output parsing", "Guardrails library"]},
            {"module": "M5", "title": "Evaluation & Testing", "topics": ["LangSmith tracing", "Automated eval pipelines", "Regression testing for prompts"]},
            {"module": "M6", "title": "Deployment", "topics": ["FastAPI LLM endpoints", "Caching LLM responses", "Cost optimisation at scale"]},
        ],
        "testimonials": [
            {"name": "Shubham Tiwari", "role": "AI Engineer", "city": "Bengaluru", "text": "Best technical AI course I've done. The RAG module alone helped me build a feature that impressed my entire team.", "rating": 5},
            {"name": "Anjali Mishra", "role": "Backend Developer", "city": "Pune", "text": "I went from zero LLM knowledge to shipping an AI feature at work in 3 weeks. The structured approach is excellent.", "rating": 5},
            {"name": "Abhishek Verma", "role": "ML Engineer", "city": "Delhi", "text": "The evaluation framework section is missing from every other AI course. Critical knowledge for production.", "rating": 5},
        ],
    },

    # ══════════════ SEO (4) ══════════════
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
        "salary_after_min": "3.5",
        "salary_after_max": "8.0",
        "job_roles": "SEO Analyst, SEO Specialist, Content Writer, Digital Marketing Executive, Blogger",
        "curriculum": [
            {"module": "M1", "title": "How Search Engines Work", "topics": ["Crawling, indexing, ranking", "E-E-A-T signals", "Core algorithm updates"]},
            {"module": "M2", "title": "Keyword Research", "topics": ["Search intent types", "Free tool research", "Ahrefs & Semrush basics"]},
            {"module": "M3", "title": "On-Page SEO", "topics": ["Title tag optimisation", "Header hierarchy", "Internal linking strategy"]},
            {"module": "M4", "title": "Content Strategy", "topics": ["Topic clusters", "Content briefs", "Topical authority building"]},
            {"module": "M5", "title": "Measurement & Iteration", "topics": ["Google Search Console", "Rank tracking tools", "Monthly SEO reporting"]},
        ],
        "testimonials": [
            {"name": "Ravi Shankar", "role": "Blogger", "city": "Varanasi", "text": "My blog went from 200 to 8,000 monthly visitors in 6 months after applying what I learned here.", "rating": 5},
            {"name": "Pooja Mehta", "role": "SEO Executive", "city": "Surat", "text": "I got my first SEO job at ₹4.5 LPA after completing this course. The certificate helped me stand out.", "rating": 5},
            {"name": "Deepak Thakur", "role": "Small Business Owner", "city": "Ahmedabad", "text": "My bakery now ranks #1 on Google locally. My walk-in customers doubled!", "rating": 5},
        ],
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
        "salary_after_min": "6.0",
        "salary_after_max": "18.0",
        "job_roles": "Technical SEO Specialist, SEO Engineer, Web Performance Analyst, Site Architecture Consultant, SEO Tech Lead",
        "curriculum": [
            {"module": "M1", "title": "Crawling & Indexation", "topics": ["Crawl budget optimisation", "robots.txt mastery", "Noindex / nofollow strategy"]},
            {"module": "M2", "title": "Site Architecture", "topics": ["URL structure", "Silo architecture", "Pagination and faceted navigation"]},
            {"module": "M3", "title": "Canonicals & Hreflang", "topics": ["Duplicate content resolution", "Canonical tag implementation", "International SEO basics"]},
            {"module": "M4", "title": "Core Web Vitals", "topics": ["LCP optimisation", "INP / CLS fixes", "PageSpeed Insights walkthroughs"]},
            {"module": "M5", "title": "Structured Data", "topics": ["Schema.org types", "FAQ & Article schema", "Rich result testing"]},
            {"module": "M6", "title": "Log File Analysis", "topics": ["Server log parsing", "Crawl error diagnosis", "Screaming Frog & Sitebulb"]},
        ],
        "testimonials": [
            {"name": "Suresh Kumar", "role": "Technical SEO Lead", "city": "Chennai", "text": "Fixed a crawl budget issue that was hiding 40% of our pages from Google. Direct impact of this course.", "rating": 5},
            {"name": "Alisha Patel", "role": "Web Developer", "city": "Ahmedabad", "text": "Improved our LCP from 4.2s to 1.8s using the Core Web Vitals module. Our rankings jumped in 2 months.", "rating": 5},
            {"name": "Vikas Yadav", "role": "SEO Manager", "city": "Noida", "text": "The structured data section is the most practical I've seen. Rich snippets are now live on 200+ of our pages.", "rating": 4},
        ],
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
        "salary_after_min": "3.0",
        "salary_after_max": "7.0",
        "job_roles": "Local SEO Specialist, Digital Marketing Executive, Agency Account Manager, GBP Consultant, Reputation Manager",
        "curriculum": [
            {"module": "M1", "title": "Google Business Profile", "topics": ["Complete GBP setup", "Category & attribute optimisation", "Photo & post strategy"]},
            {"module": "M2", "title": "Local Citations & NAP", "topics": ["NAP consistency audit", "Top citation directories", "Citation building tools"]},
            {"module": "M3", "title": "Reviews & Reputation", "topics": ["Review generation systems", "Responding to negative reviews", "Reputation monitoring"]},
            {"module": "M4", "title": "Local Landing Pages", "topics": ["City-specific page templates", "Local keyword integration", "Schema for local businesses"]},
            {"module": "M5", "title": "Tracking Local SEO", "topics": ["Local rank tracking", "Google Maps ranking factors", "Monthly reporting"]},
        ],
        "testimonials": [
            {"name": "Mohan Patel", "role": "Restaurant Owner", "city": "Surat", "text": "My restaurant now appears in Google Maps top 3 for 'restaurant near me'. Footfall up 60% in 3 months.", "rating": 5},
            {"name": "Sunita Sharma", "role": "Digital Agency Owner", "city": "Jaipur", "text": "I now offer Local SEO as a standalone service for ₹8K/month per client. This course made that possible.", "rating": 5},
            {"name": "Rajan Nair", "role": "Tuition Centre Owner", "city": "Kochi", "text": "Parents find us on Google Maps now. Enrolments increased by 40% after we optimised our GBP.", "rating": 4},
        ],
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
        "salary_after_min": "8.0",
        "salary_after_max": "20.0",
        "job_roles": "Programmatic SEO Specialist, SEO Engineer, Growth Engineer, Content Operations Manager, Technical Content Lead",
        "curriculum": [
            {"module": "M1", "title": "Programmatic SEO Foundations", "topics": ["What is programmatic SEO?", "URL pattern design", "Data source selection"]},
            {"module": "M2", "title": "Template Architecture", "topics": ["Dynamic page templates", "Variable injection patterns", "Avoiding thin content traps"]},
            {"module": "M3", "title": "Building Pages at Scale", "topics": ["Django/Next.js implementation", "Database-driven pages", "Bulk URL generation"]},
            {"module": "M4", "title": "AI Content Pipelines", "topics": ["GPT-powered content generation", "Quality control filters", "Human review workflows"]},
            {"module": "M5", "title": "Indexation & Sitemaps", "topics": ["Dynamic sitemap generation", "Google Indexing API", "Crawl budget management"]},
            {"module": "M6", "title": "Monitoring & Iteration", "topics": ["Rank tracking at scale", "Content decay detection", "Programmatic refresh cycles"]},
        ],
        "testimonials": [
            {"name": "Ankit Sharma", "role": "Growth Engineer", "city": "Bengaluru", "text": "Built 5,000 location pages using this course. Organic traffic grew 1,200% in 4 months. Unbelievable ROI.", "rating": 5},
            {"name": "Nisha Verma", "role": "SEO Manager", "city": "Mumbai", "text": "The AI content pipeline module is where this course shines. We now produce 200 quality pages a week.", "rating": 5},
            {"name": "Roshan Pillai", "role": "Technical SEO Lead", "city": "Hyderabad", "text": "This is 2025 SEO. Every SEO professional needs to understand programmatic. This course teaches it clearly.", "rating": 5},
        ],
    },

    # ══════════════ AGENTIC AI (4) ══════════════
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
        "salary_after_min": "5.0",
        "salary_after_max": "14.0",
        "job_roles": "AI Automation Specialist, Operations Analyst, AI Tools Consultant, Business Process Analyst, Digital Transformation Manager",
        "curriculum": [
            {"module": "M1", "title": "What is Agentic AI?", "topics": ["Agency vs automation", "Planning and reasoning loops", "Tool use and memory explained"]},
            {"module": "M2", "title": "Platforms Overview", "topics": ["ChatGPT Agents", "AutoGPT basics", "CrewAI no-code intro"]},
            {"module": "M3", "title": "Building Your First Agent", "topics": ["Research agent setup", "Writing assistant agent", "Multi-step task delegation"]},
            {"module": "M4", "title": "Responsible AI Use", "topics": ["Hallucination risks", "Human oversight checkpoints", "Data privacy considerations"]},
            {"module": "M5", "title": "Real-World Use Cases", "topics": ["Sales research automation", "Content pipeline agent", "Customer support bot"]},
        ],
        "testimonials": [
            {"name": "Harish Iyer", "role": "Operations Manager", "city": "Chennai", "text": "Built an AI agent that does competitor research every Monday morning. Saves my team 6 hours a week.", "rating": 5},
            {"name": "Preethi Nair", "role": "HR Professional", "city": "Bengaluru", "text": "I had zero tech background but still built useful AI workflows. The course makes it very accessible.", "rating": 5},
            {"name": "Amit Bose", "role": "Business Consultant", "city": "Kolkata", "text": "My clients now pay a premium because I deliver AI-automated reports they thought needed a developer.", "rating": 4},
        ],
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
        "salary_after_min": "12.0",
        "salary_after_max": "30.0",
        "job_roles": "AI Engineer, LangChain Developer, Agentic AI Developer, LLM Backend Engineer, AI Automation Engineer",
        "curriculum": [
            {"module": "M1", "title": "LangChain Core", "topics": ["Chains and LCEL", "Prompt templates", "Memory modules"]},
            {"module": "M2", "title": "LangChain Agents", "topics": ["ReAct agent pattern", "Tool creation", "Custom agent executors"]},
            {"module": "M3", "title": "LangGraph Fundamentals", "topics": ["State graph architecture", "Node and edge design", "Conditional routing"]},
            {"module": "M4", "title": "External Integrations", "topics": ["REST API tool calling", "Database connections", "File system access"]},
            {"module": "M5", "title": "Advanced Patterns", "topics": ["Plan-and-execute agents", "Reflection loops", "Human-in-the-loop checkpoints"]},
            {"module": "M6", "title": "Production Deployment", "topics": ["FastAPI endpoint setup", "Docker containerisation", "LangSmith monitoring"]},
        ],
        "testimonials": [
            {"name": "Vishal Gupta", "role": "Python Developer", "city": "Pune", "text": "Shipped an AI agent for document processing at my company. Got promoted as the 'AI guy' and a ₹8L hike.", "rating": 5},
            {"name": "Simran Kaur", "role": "Backend Engineer", "city": "Chandigarh", "text": "The LangGraph module is the most complete tutorial I've found anywhere. Extremely well structured.", "rating": 5},
            {"name": "Tejasvi Rao", "role": "AI Startup Founder", "city": "Hyderabad", "text": "Built an MVP AI product in 3 weeks using this course. Got into a startup accelerator. Can't thank this enough.", "rating": 5},
        ],
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
        "salary_after_min": "16.0",
        "salary_after_max": "40.0",
        "job_roles": "Senior AI Engineer, Multi-Agent Systems Architect, AI Research Engineer, AI Tech Lead, Autonomous Systems Developer",
        "curriculum": [
            {"module": "M1", "title": "Multi-Agent Architecture", "topics": ["Orchestrator-subagent pattern", "Agent role specialisation", "State sharing strategies"]},
            {"module": "M2", "title": "CrewAI Framework", "topics": ["Crew definition", "Task delegation", "Process types: sequential & hierarchical"]},
            {"module": "M3", "title": "AutoGen Framework", "topics": ["ConversableAgent setup", "GroupChat patterns", "Tool-augmented agents"]},
            {"module": "M4", "title": "Communication Protocols", "topics": ["Message passing design", "Shared memory patterns", "Context compression"]},
            {"module": "M5", "title": "Safety & Human-in-Loop", "topics": ["Approval checkpoints", "Guardrail implementation", "Observability tooling"]},
            {"module": "M6", "title": "Real-World Pipelines", "topics": ["Automated research pipelines", "Report generation agents", "Data extraction & ops"]},
        ],
        "testimonials": [
            {"name": "Karthik Subramanian", "role": "AI Architect", "city": "Bengaluru", "text": "This is PhD-level content delivered accessibly. Built a 6-agent research pipeline that replaced a 3-person team.", "rating": 5},
            {"name": "Deepa Joshi", "role": "ML Tech Lead", "city": "Pune", "text": "AutoGen section alone took me 2 weeks to process because there's so much depth. Essential for serious AI work.", "rating": 5},
            {"name": "Rohit Saxena", "role": "AI Product Manager", "city": "Gurgaon", "text": "Got a ₹25L offer after showcasing the multi-agent project I built in this course. Incredible ROI.", "rating": 5},
        ],
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
        "salary_after_min": "7.0",
        "salary_after_max": "18.0",
        "job_roles": "AI Automation Consultant, Operations Manager, Business Process Analyst, CRM Automation Specialist, No-Code AI Developer",
        "curriculum": [
            {"module": "M1", "title": "Business Automation Audit", "topics": ["Identifying automation candidates", "ROI estimation framework", "Process mapping"]},
            {"module": "M2", "title": "Make & Zapier with AI", "topics": ["Make (Integromat) AI modules", "Zapier ChatGPT integration", "Multi-step automation flows"]},
            {"module": "M3", "title": "n8n Self-Hosted Automation", "topics": ["n8n setup and deployment", "AI agent nodes", "Complex workflow design"]},
            {"module": "M4", "title": "Sales & Lead Automation", "topics": ["AI lead scoring", "Automated follow-up sequences", "CRM integration"]},
            {"module": "M5", "title": "Customer Support AI", "topics": ["Voiceflow chatbot setup", "FAQ automation", "Escalation routing"]},
            {"module": "M6", "title": "AI Adoption & ROI", "topics": ["Change management for AI", "ROI tracking dashboards", "Scaling automation safely"]},
        ],
        "testimonials": [
            {"name": "Sunil Verma", "role": "Business Owner", "city": "Ahmedabad", "text": "Automated my entire lead follow-up with n8n + AI. Conversion rate up 25%, working hours down 4 hours a day.", "rating": 5},
            {"name": "Lakshmi Rao", "role": "Operations Manager", "city": "Hyderabad", "text": "Implemented 6 automations in 3 weeks. My team now focuses on high-value work instead of repetitive tasks.", "rating": 5},
            {"name": "Gaurav Agarwal", "role": "Automation Consultant", "city": "Indore", "text": "Charging ₹20K/month per client for automation setups I learned here. Course paid back 50× in first 3 months.", "rating": 5},
        ],
    },

    # ══════════════ ECOMMERCE MANAGER (4) ══════════════
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
        "salary_after_min": "3.5",
        "salary_after_max": "8.0",
        "job_roles": "Ecommerce Executive, D2C Brand Manager, Shopify Store Manager, Online Business Owner, Digital Entrepreneur",
        "curriculum": [
            {"module": "M1", "title": "Business Model Selection", "topics": ["Own store vs marketplace", "D2C vs wholesale", "Niche selection framework"]},
            {"module": "M2", "title": "Store Setup", "topics": ["Shopify complete setup", "WooCommerce basics", "Theme customisation"]},
            {"module": "M3", "title": "Product & Pricing", "topics": ["Product photography tips", "Listing copywriting", "Competitive pricing strategy"]},
            {"module": "M4", "title": "Payments & Logistics", "topics": ["Razorpay integration", "Shipping partner setup", "Returns management"]},
            {"module": "M5", "title": "First Sales Strategy", "topics": ["Social media launch plan", "Friends & family referral", "First 100 orders playbook"]},
        ],
        "testimonials": [
            {"name": "Bhavna Shah", "role": "Jewellery Store Owner", "city": "Surat", "text": "Launched my online jewellery store in 10 days using this course. First ₹1 lakh in sales in month 2!", "rating": 5},
            {"name": "Vinod Kumar", "role": "Home Decor Seller", "city": "Jaipur", "text": "No tech background needed. The step-by-step Shopify setup is perfect. I was live in a week.", "rating": 5},
            {"name": "Meghna Trivedi", "role": "Fashion Entrepreneur", "city": "Ahmedabad", "text": "The product photography tips transformed my listings. CTR jumped from 1.2% to 4.8%.", "rating": 4},
        ],
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
        "salary_after_min": "4.0",
        "salary_after_max": "12.0",
        "job_roles": "Amazon Account Manager, Marketplace Manager, Ecommerce Catalog Specialist, PPC Analyst, Brand Manager",
        "curriculum": [
            {"module": "M1", "title": "Marketplace Fundamentals", "topics": ["Amazon vs Flipkart algorithms", "Account health management", "Seller metrics"]},
            {"module": "M2", "title": "Listing Optimisation", "topics": ["Backend keyword research", "Image guidelines", "A+ content creation"]},
            {"module": "M3", "title": "Pricing & Buy Box", "topics": ["Buy Box algorithm", "Repricing strategies", "Competitive benchmarking"]},
            {"module": "M4", "title": "PPC Advertising", "topics": ["Sponsored Products setup", "Keyword bid management", "ACOS optimisation"]},
            {"module": "M5", "title": "Inventory & Logistics", "topics": ["FBA/FBF enrolment", "Inventory forecasting", "Returns processing"]},
            {"module": "M6", "title": "Scaling Your Brand", "topics": ["Multi-marketplace expansion", "Brand Registry benefits", "International selling basics"]},
        ],
        "testimonials": [
            {"name": "Rajesh Sharma", "role": "Amazon Seller", "city": "Delhi", "text": "Revenue went from ₹3L to ₹18L per month after applying the PPC and listing strategies. Life-changing course.", "rating": 5},
            {"name": "Preeti Malhotra", "role": "Marketplace Manager", "city": "Noida", "text": "The Buy Box module is pure gold. We moved from 40% to 85% Buy Box ownership in 6 weeks.", "rating": 5},
            {"name": "Saurabh Goel", "role": "Brand Manager", "city": "Mumbai", "text": "Best marketplace course for the Indian market. Highly specific to Amazon India and Flipkart nuances.", "rating": 5},
        ],
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
        "salary_after_min": "6.0",
        "salary_after_max": "16.0",
        "job_roles": "Ecommerce Marketing Manager, CRO Specialist, Growth Marketer, D2C Brand Manager, Performance Marketing Analyst",
        "curriculum": [
            {"module": "M1", "title": "Ecommerce Funnel Strategy", "topics": ["Awareness to purchase funnel", "Channel attribution", "CAC vs LTV framework"]},
            {"module": "M2", "title": "Product Discovery Ads", "topics": ["Google Shopping campaigns", "Meta Dynamic Product Ads", "Catalog optimisation"]},
            {"module": "M3", "title": "Conversion Rate Optimisation", "topics": ["Heatmap analysis", "A/B testing with VWO", "Urgency and FOMO tactics"]},
            {"module": "M4", "title": "Cart Recovery & Retention", "topics": ["Abandoned cart email flows", "WhatsApp recovery automation", "SMS retargeting"]},
            {"module": "M5", "title": "Customer Loyalty & LTV", "topics": ["Loyalty programme design", "Repeat purchase triggers", "LTV segmentation"]},
        ],
        "testimonials": [
            {"name": "Aditi Gupta", "role": "D2C Brand Manager", "city": "Mumbai", "text": "Our ROAS improved from 2.1× to 4.7× after implementing the Meta DPA and CRO strategies. Phenomenal course.", "rating": 5},
            {"name": "Ramesh Nair", "role": "Growth Marketer", "city": "Bengaluru", "text": "Cart recovery flows we set up based on this course now recover 22% of abandoned carts. That's ₹12L extra per month.", "rating": 5},
            {"name": "Vandana Singh", "role": "Ecommerce Manager", "city": "Gurgaon", "text": "Got promoted from executive to manager after presenting the CRO audit framework from this course to leadership.", "rating": 5},
        ],
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
        "salary_after_min": "8.0",
        "salary_after_max": "22.0",
        "job_roles": "Ecommerce Head, VP Ecommerce, D2C Business Head, Ecommerce Director, Category Manager",
        "curriculum": [
            {"module": "M1", "title": "Operations Systems", "topics": ["Order management SOPs", "Customer support playbook", "Warehouse & 3PL coordination"]},
            {"module": "M2", "title": "Financial Management", "topics": ["Ecommerce P&L structure", "Unit economics breakdown", "Cash flow forecasting"]},
            {"module": "M3", "title": "Data & Analytics", "topics": ["GA4 ecommerce tracking", "Looker Studio dashboards", "Cohort analysis basics"]},
            {"module": "M4", "title": "Multi-Channel Expansion", "topics": ["Quick commerce (Blinkit, Zepto)", "B2B and institutional sales", "Export readiness basics"]},
            {"module": "M5", "title": "Team & Culture", "topics": ["Hiring for ecommerce roles", "Performance management", "Agency vs in-house trade-offs"]},
            {"module": "M6", "title": "Growth Strategy", "topics": ["Brand building at scale", "New category entry", "Fundraising readiness"]},
        ],
        "testimonials": [
            {"name": "Nitin Agarwal", "role": "D2C Founder", "city": "Ahmedabad", "text": "Crossed ₹50L/month using the expansion strategy and P&L framework from this course. Best investment in my business.", "rating": 5},
            {"name": "Sapna Mehta", "role": "Ecommerce Head", "city": "Delhi", "text": "The SOP library is worth ₹10× the course price. We went from chaos to a fully systemised operation in 8 weeks.", "rating": 5},
            {"name": "Praveen Kumar", "role": "Category Manager", "city": "Chennai", "text": "The multi-channel module helped us get onto Blinkit and add ₹8L in monthly revenue we were completely ignoring.", "rating": 5},
        ],
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

            # Career outcome fields
            salary_min = data.get("salary_after_min")
            salary_max = data.get("salary_after_max")
            course.salary_after_min = Decimal(salary_min) if salary_min else None
            course.salary_after_max = Decimal(salary_max) if salary_max else None
            course.job_roles = data.get("job_roles", "")

            # Structured data
            course.curriculum = data.get("curriculum", [])
            course.testimonials = data.get("testimonials", [])

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
        self.stdout.write(f"Total courses in DB: {Course.objects.count()}")
        self.stdout.write("Edit them at: /sd/core/course/")
