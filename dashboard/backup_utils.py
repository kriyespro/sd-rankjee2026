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
    apply_backup_retention_policy()
    return created


def delete_backup_artifact(item: BackupArtifact) -> bool:
    removed_file = False
    if item.file_path:
        p = Path(item.file_path)
        if p.exists() and p.is_file():
            p.unlink()
            removed_file = True
    item.delete()
    return removed_file


def apply_backup_retention_policy(*, keep_full=None, keep_db=None):
    keep_full = int(
        keep_full
        if keep_full is not None
        else getattr(settings, "BACKUP_KEEP_FULL_COUNT", 14)
    )
    keep_db = int(
        keep_db
        if keep_db is not None
        else getattr(settings, "BACKUP_KEEP_DB_COUNT", 30)
    )

    deleted = []
    policy = [
        (BackupArtifact.BackupType.FULL, keep_full),
        (BackupArtifact.BackupType.DB, keep_db),
    ]
    for backup_type, keep_count in policy:
        if keep_count < 0:
            keep_count = 0
        ids_to_keep = list(
            BackupArtifact.objects.filter(backup_type=backup_type)
            .order_by("-created_at", "-id")
            .values_list("id", flat=True)[:keep_count]
        )
        stale_qs = BackupArtifact.objects.filter(backup_type=backup_type).exclude(id__in=ids_to_keep)
        for artifact in stale_qs:
            delete_backup_artifact(artifact)
            deleted.append(artifact.file_name)
    return deleted


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
