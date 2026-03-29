import os, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from assessment.models import Skill, Question
from learning.models import ConceptVideo

# Data to seed
SEED_DATA = {
    "SSC Exams": {
        "videos": [
            {"title": "Quantitative Aptitude Basics for SSC", "concept_tag": "Quant", "url": "https://www.youtube.com/watch?v=S0TzIEh_2jQ", "duration": 600},
            {"title": "Reasoning Tricks for SSC CGL", "concept_tag": "Reasoning", "url": "https://www.youtube.com/watch?v=vVj4w8rW6x4", "duration": 480},
        ],
        "questions": [
            {"text": "If A completes a work in 10 days and B in 15 days, how long will they take together?", "concept_tag": "Quant", "difficulty": "MEDIUM", "a": "5 days", "b": "6 days", "c": "8 days", "d": "12 days", "ans": "B"},
            {"text": "Find the missing number in the series: 2, 6, 12, 20, ?", "concept_tag": "Reasoning", "difficulty": "EASY", "a": "28", "b": "30", "c": "32", "d": "36", "ans": "B"},
            {"text": "What is the synonym of 'Abundant'?", "concept_tag": "English", "difficulty": "EASY", "a": "Scarce", "b": "Plentiful", "c": "Rare", "d": "Short", "ans": "B"},
            {"text": "Calculate the simple interest on Rs. 1000 at 5% for 2 years.", "concept_tag": "Quant", "difficulty": "EASY", "a": "50", "b": "100", "c": "150", "d": "200", "ans": "B"},
            {"text": "Which of the following is a prime number?", "concept_tag": "Quant", "difficulty": "EASY", "a": "9", "b": "15", "c": "17", "d": "21", "ans": "C"}
        ]
    },
    "Banking Exams": {
        "videos": [
            {"title": "Data Interpretation for Bank PO", "concept_tag": "DI", "url": "https://www.youtube.com/watch?v=zJvV2-c6j8E", "duration": 540},
            {"title": "Banking Awareness 2024", "concept_tag": "General Awareness", "url": "https://www.youtube.com/watch?v=8b5p2m6Lfkg", "duration": 720},
        ],
        "questions": [
            {"text": "What does UPI stand for?", "concept_tag": "General Awareness", "difficulty": "EASY", "a": "United Payments Interface", "b": "Unified Payments Interface", "c": "Universal Payment Integration", "d": "Unique Payment Identity", "ans": "B"},
            {"text": "Which bank is known as the banker's bank in India?", "concept_tag": "General Awareness", "difficulty": "EASY", "a": "SBI", "b": "HDFC", "c": "RBI", "d": "ICICI", "ans": "C"},
            {"text": "A shopkeeper sells an item at 20% profit. If cost price is 500, what is selling price?", "concept_tag": "DI", "difficulty": "MEDIUM", "a": "550", "b": "600", "c": "620", "d": "650", "ans": "B"},
            {"text": "What is the full form of CRR?", "concept_tag": "General Awareness", "difficulty": "MEDIUM", "a": "Cash Reserve Ratio", "b": "Capital Reserve Ratio", "c": "Current Rate Ratio", "d": "Cash Return Ratio", "ans": "A"},
            {"text": "Solve: 25% of 400 + 10% of 200 = ?", "concept_tag": "DI", "difficulty": "EASY", "a": "100", "b": "120", "c": "150", "d": "200", "ans": "B"}
        ]
    },
    "Railway Exams": {
        "videos": [
            {"title": "General Science for RRB NTPC", "concept_tag": "General Science", "url": "https://www.youtube.com/watch?v=-yIRzBqI1q4", "duration": 450},
            {"title": "Static GK for Railway Exams", "concept_tag": "GK", "url": "https://www.youtube.com/watch?v=LVV_93mBfSU", "duration": 500},
        ],
        "questions": [
            {"text": "What is the chemical symbol for Gold?", "concept_tag": "General Science", "difficulty": "EASY", "a": "Ag", "b": "Fe", "c": "Au", "d": "Cu", "ans": "C"},
            {"text": "Who is the longest-serving Railway Minister of India?", "concept_tag": "GK", "difficulty": "HARD", "a": "Lalu Prasad Yadav", "b": "Babu Jagjivan Ram", "c": "Nitish Kumar", "d": "Mamata Banerjee", "ans": "B"},
            {"text": "What is the SI unit of Force?", "concept_tag": "General Science", "difficulty": "EASY", "a": "Joule", "b": "Newton", "c": "Watt", "d": "Pascal", "ans": "B"},
            {"text": "Where is the headquarters of Indian Railways located?", "concept_tag": "GK", "difficulty": "EASY", "a": "Mumbai", "b": "Kolkata", "c": "New Delhi", "d": "Chennai", "ans": "C"},
            {"text": "Which vitamin deficiency causes scurvy?", "concept_tag": "General Science", "difficulty": "MEDIUM", "a": "Vitamin A", "b": "Vitamin B", "c": "Vitamin C", "d": "Vitamin D", "ans": "C"}
        ]
    }
}

for skill_name, data in SEED_DATA.items():
    try:
        skill = Skill.objects.get(name=skill_name)
    except Skill.DoesNotExist:
        print(f"Skill '{skill_name}' not found. Skipping...")
        continue
        
    print(f"Seeding '{skill_name}'...")
    
    # Create Videos
    for v_data in data["videos"]:
        ConceptVideo.objects.get_or_create(
            title=v_data["title"],
            skill=skill,
            defaults={
                "concept_tag": v_data["concept_tag"],
                "video_url": v_data["url"],
                "duration_seconds": v_data["duration"]
            }
        )
        
    # Create Questions
    for q_data in data["questions"]:
        Question.objects.get_or_create(
            text=q_data["text"],
            skill=skill,
            defaults={
                "concept_tag": q_data["concept_tag"],
                "difficulty": q_data["difficulty"],
                "option_a": q_data["a"],
                "option_b": q_data["b"],
                "option_c": q_data["c"],
                "option_d": q_data["d"],
                "correct_option": q_data["ans"],
            }
        )

print("✅ Finished seeding MCQs and Videos for new topics!")
