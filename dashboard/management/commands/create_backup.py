from django.core.management.base import BaseCommand

from dashboard.backup_utils import create_backups, notify_superusers_for_backups


class Command(BaseCommand):
    help = "Create project backups (full project and/or database dump)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--types",
            nargs="+",
            choices=["full", "db"],
            default=["full", "db"],
            help="Backup types to create.",
        )
        parser.add_argument(
            "--no-notify",
            action="store_true",
            help="Skip superuser notification creation.",
        )

    def handle(self, *args, **options):
        types = set(options["types"] or [])
        created = create_backups(
            include_full="full" in types,
            include_db="db" in types,
            created_by=None,
        )
        if created and not options["no_notify"]:
            notify_superusers_for_backups(created)

        for item in created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{item.get_backup_type_display()}: {item.file_name} ({item.file_size_bytes} bytes)"
                )
            )
