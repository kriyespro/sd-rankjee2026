import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from payments.models import SubscriptionPlan

def seed_plans():
    plans = [
        {
            "name": "Monthly Pro",
            "description": "Perfect for short-term intense learning and quick certification.",
            "price": 99.00,
            "duration_days": 30,
            "features": [
                "Unlimited Tests",
                "Verified PDF Certificates",
                "Advanced Speed Analytics",
                "Ad-Free Experience",
                "Priority Support"
            ]
        },
        {
            "name": "Annual Pro",
            "description": "Best for serious career builders. Save big over the long term.",
            "price": 799.00,
            "duration_days": 365,
            "features": [
                "Everything in Monthly",
                "33% Discount over monthly",
                "Exclusive Founder Sessions",
                "Lifetime Access to Basic Certificates",
                "Early Access to new Skill Paths"
            ]
        }
    ]

    for plan_data in plans:
        plan, created = SubscriptionPlan.objects.get_or_create(
            name=plan_data["name"],
            defaults={
                "description": plan_data["description"],
                "price": plan_data["price"],
                "duration_days": plan_data["duration_days"],
                "features": plan_data["features"]
            }
        )
        if created:
            print(f"Created plan: {plan.name}")
        else:
            print(f"Plan already exists: {plan.name}")

if __name__ == "__main__":
    seed_plans()
