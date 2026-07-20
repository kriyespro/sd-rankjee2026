from django.core.management.base import BaseCommand

from users.models import CustomUser


class Command(BaseCommand):
    help = (
        "Reset exam free-trial counters for all users "
        "(trial_tests_left=3, trial_tests_used=0). "
        "Use when re-enabling EXAM_PAYWALL_ENABLED later."
    )

    def handle(self, *args, **options):
        updated = CustomUser.objects.update(trial_tests_left=3, trial_tests_used=0)
        self.stdout.write(self.style.SUCCESS(f"Reset exam trial counters for {updated} users."))
