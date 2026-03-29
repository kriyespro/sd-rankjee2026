import os, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from assessment.models import SkillPath, Skill

# 1. Ensure Skill Paths exist
path_gov, _ = SkillPath.objects.get_or_create(
    name="Government Exams", 
    defaults={'description': 'Prepare for top government jobs', 'level_order': 1}
)

path_finance, _ = SkillPath.objects.get_or_create(
    name="Finance & Banking", 
    defaults={'description': 'Crack banking and financial sector exams', 'level_order': 2}
)

# 2. Add Skills
topics = [
    ("SSC Exams", "CGL, CHSL, MTS Preparation", path_gov),
    ("Railway Exams", "RRB NTPC, Group D Preparation", path_gov),
    ("Banking Exams", "IBPS, SBI PO, Clerk Preparation", path_finance),
]

for name, desc, path in topics:
    skill, created = Skill.objects.get_or_create(
        name=name,
        defaults={'description': desc, 'path': path, 'is_active': True}
    )
    if created:
        print(f"Created Topic: {name}")
    else:
        # Update path if needed
        skill.path = path
        skill.save()
        print(f"Updated Topic: {name}")

print("✅ New Topics Seeded Successfully!")
