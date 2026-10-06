"""Backup and restore utilities for Duo Tracker SQLite database."""
from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def backup_dir(base: Path) -> Path:
    """Return (and create if needed) the backups directory."""
    d = base / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_backup(db_path: Path, backups_base: Path) -> str:
    """Copy the SQLite database file to a timestamped backup.

    Returns the backup filename (not full path) so it can be surfaced to the frontend.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")
    directory = backup_dir(backups_base)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"duo_tracker_backup_{timestamp}.db"
    destination = directory / filename
    shutil.copy2(db_path, destination)
    logger.info("Backup created: %s", destination)
    return filename


def list_backups(backups_base: Path) -> list[dict]:
    """Return a list of available backup metadata sorted newest-first."""
    directory = backup_dir(backups_base)
    result = []
    for path in sorted(directory.glob("duo_tracker_backup_*.db"), reverse=True):
        stat = path.stat()
        result.append(
            {
                "filename": path.name,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return result


def restore_backup(filename: str, db_path: Path, backups_base: Path) -> None:
    """Overwrite the live database with the specified backup file."""
    directory = backup_dir(backups_base)
    source = directory / filename
    if not source.exists():
        raise FileNotFoundError(f"Backup file not found: {filename}")
    # Validate it looks like a SQLite file
    with open(source, "rb") as f:
        header = f.read(16)
    if not header.startswith(b"SQLite format 3"):
        raise ValueError("The selected file does not appear to be a valid SQLite database.")
    shutil.copy2(source, db_path)
    logger.info("Restored backup %s to %s", filename, db_path)


def delete_backup(filename: str, backups_base: Path) -> None:
    """Delete a backup file."""
    directory = backup_dir(backups_base)
    target = directory / filename
    if not target.exists():
        raise FileNotFoundError(f"Backup file not found: {filename}")
    # Safety: only allow deleting .db files inside the backup directory
    if target.parent != directory:
        raise PermissionError("Refusing to delete file outside backup directory.")
    target.unlink()
    logger.info("Deleted backup: %s", filename)
