"""Static featured tutors fallback for home (HT-0) when no approved DB rows exist. Prefer `hometutor.services.featured_home_tutors`."""

PILOT_CITY = "Ahmedabad"

# Single-segment URLs like `/surat/` redirect to `/hometutor/city/<slug>/`. Only these slugs (plus DB-backed tutor cities in `city_tutor_redirect`) are allowed so `/earn/` etc. do not become fake city pages.
SHORT_LINK_CITY_SLUGS = frozenset(
    {
        "ranchi",
        "patna",
        "kolkata",
        "lucknow",
        "guwahati",
        "bhopal",
        "chandigarh",
        "delhi",
        "surat",
        "ahmedabad",
        "mumbai",
        "pune",
        "indore",
        "nagpur",
        "rajkot",
        "nashik",
        "vadodara",
        "aurangabad",
        "hyderabad",
        "chennai",
        "bengaluru",
        "bangalore",
        "coimbatore",
        "kochi",
        "visakhapatnam",
        "mangaluru",
        "jaipur",
        "noida",
        "gurugram",
        "gurgaon",
    }
)

# Seeded display rows — not persisted until TutorProfile exists.
FEATURED_HOME_TUTORS = [
    {
        "name": "Priya S.",
        "subjects": "Math, Physics",
        "classes": "Class 9–12 · CBSE",
        "fee_label": "from ₹6,000/mo",
        "area": "Satellite",
        "rating": "4.9",
        "reviews": 24,
        "verified": True,
    },
    {
        "name": "Rajesh K.",
        "subjects": "Chemistry, Biology",
        "classes": "Class 10–12",
        "fee_label": "from ₹5,500/mo",
        "area": "Bodakdev",
        "rating": "4.7",
        "reviews": 18,
        "verified": True,
    },
    {
        "name": "Anjali P.",
        "subjects": "English, Hindi",
        "classes": "Class 6–10",
        "fee_label": "from ₹4,800/mo",
        "area": "Vastrapur",
        "rating": "4.9",
        "reviews": 31,
        "verified": True,
    },
]
