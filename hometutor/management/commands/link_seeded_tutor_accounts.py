"""Link seeded TutorProfile rows to real tutor user accounts."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from hometutor.models import TutorProfile


class Command(BaseCommand):
    help = (
        "Create/link tutor user accounts for approved TutorProfile rows so demo requests are enabled."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            default="",
            help="Optional single tutor slug to link (example: ahmedabad-ananya-kulkarni-011).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Optional cap for batch linking (0 = no limit).",
        )
        parser.add_argument(
            "--password",
            default="Tutor@1234",
            help="Initial password for newly created tutor accounts.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        slug = (options.get("slug") or "").strip()
        limit = max(0, int(options.get("limit") or 0))
        password = str(options.get("password") or "Tutor@1234")

        qs = TutorProfile.objects.filter(
            verification_status=TutorProfile.VerificationStatus.APPROVED,
            user__isnull=True,
        ).order_by("id")
        if slug:
            qs = qs.filter(slug=slug)
        if limit:
            qs = qs[:limit]

        created_users = 0
        linked_profiles = 0

        for profile in qs:
            base_username = f"tutor_{(profile.slug or profile.pk)[:20].replace('-', '_')}"
            username = base_username
            n = 2
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{n}"
                n += 1

            email = f"{profile.slug or username}@tutor.rankjee.local"
            while User.objects.filter(email=email).exists():
                email = f"{username}@tutor.rankjee.local"

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=(profile.display_name.split(" ")[0] if profile.display_name else "Tutor"),
                last_name=(" ".join(profile.display_name.split(" ")[1:]) if profile.display_name else ""),
            )
            if hasattr(user, "role"):
                user.role = User.Role.TUTOR
                user.save(update_fields=["role"])

            profile.user = user
            profile.save(update_fields=["user", "updated_at"])

            created_users += 1
            linked_profiles += 1

        if slug and linked_profiles == 0:
            self.stdout.write(
                self.style.WARNING(
                    f"No unlinked approved tutor found for slug={slug!r}. "
                    "It may already be linked or not approved."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Linked tutor profiles: {linked_profiles}. Created tutor users: {created_users}."
            )
        )
