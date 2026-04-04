from django.core.management.base import BaseCommand

from payments.models import SubscriptionPlan


class Command(BaseCommand):
    help = "Create default Monthly / Annual Pro plans if missing."

    def handle(self, *args, **options):
        plans = [
            {
                "name": "Monthly Pro",
                "description": "Short-term intense learning and quick certification.",
                "price": 99.00,
                "duration_days": 30,
                "features": [
                    "Unlimited Tests",
                    "Verified PDF Certificates",
                    "Advanced Speed Analytics",
                    "Ad-Free Experience",
                    "Priority Support",
                ],
            },
            {
                "name": "Annual Pro",
                "description": "Best for serious career builders. Save over monthly.",
                "price": 799.00,
                "duration_days": 365,
                "features": [
                    "Everything in Monthly",
                    "33% Discount over monthly",
                    "Exclusive Founder Sessions",
                    "Early Access to new Skill Paths",
                ],
            },
        ]
        for p in plans:
            _, created = SubscriptionPlan.objects.get_or_create(
                name=p["name"],
                defaults={
                    "description": p["description"],
                    "price": p["price"],
                    "duration_days": p["duration_days"],
                    "features": p["features"],
                },
            )
            self.stdout.write(
                self.style.SUCCESS("Created " + p["name"])
                if created
                else ("Exists: " + p["name"])
            )
