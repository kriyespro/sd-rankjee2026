import gzip
import os
import tarfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import transaction

from users.models import Notification

from .models import BackupArtifact


def _backup_dir() -> Path:
    path = Path(settings.MEDIA_ROOT) / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _human_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _project_file_filter(path: Path, backups_root: Path) -> bool:
    parts = set(path.parts)
    blocked = {".git", ".venv", "venv", "__pycache__", "node_modules", "staticfiles"}
    if parts & blocked:
        return False
    if path.suffix in {".pyc", ".pyo"}:
        return False
    # Never recurse into previously-created backup archives.
    try:
        path.relative_to(backups_root)
        return False
    except ValueError:
        return True


def create_db_backup(*, created_by=None) -> BackupArtifact:
    stamp = _human_stamp()
    backup_root = _backup_dir()
    out_path = backup_root / f"db_backup_{stamp}.json.gz"

    with gzip.open(out_path, "wt", encoding="utf-8") as gz_out:
        call_command("dumpdata", stdout=gz_out)

    return BackupArtifact.objects.create(
        backup_type=BackupArtifact.BackupType.DB,
        file_path=str(out_path),
        file_name=out_path.name,
        file_size_bytes=out_path.stat().st_size if out_path.exists() else 0,
        created_by=created_by,
    )


def create_full_backup(*, created_by=None) -> BackupArtifact:
    stamp = _human_stamp()
    backup_root = _backup_dir()
    out_path = backup_root / f"full_backup_{stamp}.tar.gz"
    base_dir = Path(settings.BASE_DIR).resolve()

    with tarfile.open(out_path, "w:gz") as tar:
        for path in base_dir.rglob("*"):
            if not path.is_file():
                continue
            if not _project_file_filter(path, backup_root):
                continue
            arcname = str(path.relative_to(base_dir))
            tar.add(path, arcname=arcname, recursive=False)

    return BackupArtifact.objects.create(
        backup_type=BackupArtifact.BackupType.FULL,
        file_path=str(out_path),
        file_name=out_path.name,
        file_size_bytes=out_path.stat().st_size if out_path.exists() else 0,
        created_by=created_by,
    )


@transaction.atomic
def create_backups(*, include_full=True, include_db=True, created_by=None):
    created = []
    if include_full:
        created.append(create_full_backup(created_by=created_by))
    if include_db:
        created.append(create_db_backup(created_by=created_by))
    return created


def notify_superusers_for_backups(backups):
    if not backups:
        return
    from django.contrib.auth import get_user_model

    User = get_user_model()
    superusers = User.objects.filter(is_superuser=True, is_active=True)
    count = len(backups)
    names = ", ".join(b.file_name for b in backups[:2])
    if count > 2:
        names += f" +{count - 2} more"
    message = f"Daily backup completed: {names}"
    for user in superusers:
        Notification.objects.create(
            user=user,
            message=message[:300],
            link="/admin/backups/",
        )
