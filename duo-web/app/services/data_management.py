"""Data management service for Duo Tracker.

All operations use explicit transactions and roll back on failure.
API keys are intentionally excluded from JSON exports.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import (
    ActivityLog,
    CustomTab,
    CustomTabEntry,
    DailyStats,
    Player,
    PointsEvent,
    Project,
    ProjectNote,
    ProjectTask,
    StudyEntry,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Granular deletions
# ---------------------------------------------------------------------------

def delete_study_entry(db: Session, entry_id: int) -> None:
    """Delete a single study entry and adjust daily stats."""
    entry = db.get(StudyEntry, entry_id)
    if entry is None:
        raise ValueError(f"Study entry {entry_id} not found.")
    # Remove associated points events that reference this entry
    db.execute(
        delete(PointsEvent).where(
            PointsEvent.reference_type == "study_entry",
            PointsEvent.reference_id == entry_id,
        )
    )
    # Reduce daily stats
    stats = db.scalar(
        select(DailyStats).where(
            DailyStats.player_id == entry.player_id,
            DailyStats.day == entry.day,
        )
    )
    if stats:
        stats.study_minutes = max(0, stats.study_minutes - entry.minutes)
    db.delete(entry)
    db.flush()


def delete_activity_entry(db: Session, entry_id: int) -> None:
    """Delete a single activity log and adjust daily stats."""
    entry = db.get(ActivityLog, entry_id)
    if entry is None:
        raise ValueError(f"Activity entry {entry_id} not found.")
    db.execute(
        delete(PointsEvent).where(
            PointsEvent.reference_type == "activity",
            PointsEvent.reference_id == entry_id,
        )
    )
    stats = db.scalar(
        select(DailyStats).where(
            DailyStats.player_id == entry.player_id,
            DailyStats.day == entry.day,
        )
    )
    if stats:
        stats.workout_minutes = max(0, stats.workout_minutes - entry.duration_minutes)
    db.delete(entry)
    db.flush()


def delete_tab(db: Session, tab_id: int) -> str:
    """Delete a custom tab and all its entries. Returns tab name."""
    tab = db.get(CustomTab, tab_id)
    if tab is None:
        raise ValueError(f"Custom tab {tab_id} not found.")
    name = tab.name
    # cascade="all, delete-orphan" on entries handles CustomTabEntry rows
    db.delete(tab)
    db.flush()
    return name


def rename_tab(db: Session, tab_id: int, new_name: str, new_icon: str | None = None) -> None:
    """Rename a custom tab."""
    tab = db.get(CustomTab, tab_id)
    if tab is None:
        raise ValueError(f"Custom tab {tab_id} not found.")
    tab.name = new_name.strip()
    if new_icon is not None:
        tab.icon = new_icon.strip() or tab.icon
    db.flush()


def reset_player_score(db: Session, player_id: int) -> None:
    """Reset a single player's points and daily stats without deleting their entries."""
    player = db.get(Player, player_id)
    if player is None:
        raise ValueError(f"Player {player_id} not found.")
    db.execute(delete(PointsEvent).where(PointsEvent.player_id == player_id))
    db.execute(delete(DailyStats).where(DailyStats.player_id == player_id))
    db.flush()


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------

def reset_scores(db: Session) -> None:
    """Zero out all points and daily stats for all players.

    Preserves: players, tabs, settings, AI keys, projects, entries (study/activity/custom).
    """
    db.execute(delete(PointsEvent))
    db.execute(delete(DailyStats))
    db.flush()


def clear_history(db: Session) -> None:
    """Remove historical records while preserving configuration.

    Deletes: study_entries, activity_logs, custom_tab_entries, points_events, daily_stats.
    Preserves: players, custom_tabs, projects (structure), AI keys, background settings.
    """
    db.execute(delete(StudyEntry))
    db.execute(delete(ActivityLog))
    db.execute(delete(CustomTabEntry))
    db.execute(delete(PointsEvent))
    db.execute(delete(DailyStats))
    # Remove project notes and task completion data but keep projects/tasks structure
    db.execute(delete(ProjectNote))
    # Reset task completion state
    for task in db.scalars(select(ProjectTask)).all():
        task.completed = False
        task.completed_at = None
    db.flush()


def reset_all_data(db: Session) -> None:
    """Full reset: removes all user data except players (names/avatars preserved), AI keys, and background settings.

    This is the nuclear option. Players are preserved with their names, but all
    scores, history, projects, custom tabs, and entries are wiped.
    """
    db.execute(delete(PointsEvent))
    db.execute(delete(DailyStats))
    db.execute(delete(StudyEntry))
    db.execute(delete(ActivityLog))
    db.execute(delete(CustomTabEntry))
    db.execute(delete(CustomTab))
    db.execute(delete(ProjectNote))
    db.execute(delete(ProjectTask))
    db.execute(delete(Project))
    db.flush()


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------

def export_json(db: Session) -> dict[str, Any]:
    """Export all application data as a safe JSON-serialisable dict.

    API keys and encrypted values are intentionally excluded.
    """
    players = db.scalars(select(Player).order_by(Player.id)).all()
    player_map = {p.id: p.name for p in players}

    def d(val: date | datetime | None) -> str | None:
        if val is None:
            return None
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    return {
        "export_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "players": [
            {
                "id": p.id,
                "name": p.name,
                "emoji": p.emoji,
                "accent": p.accent,
                "created_at": d(p.created_at),
            }
            for p in players
        ],
        "study_entries": [
            {
                "id": e.id,
                "player_name": player_map.get(e.player_id, ""),
                "day": d(e.day),
                "subject": e.subject,
                "notes": e.notes,
                "minutes": e.minutes,
                "created_at": d(e.created_at),
            }
            for e in db.scalars(select(StudyEntry).order_by(StudyEntry.day)).all()
        ],
        "activity_logs": [
            {
                "id": e.id,
                "player_name": player_map.get(e.player_id, ""),
                "day": d(e.day),
                "activity": e.activity,
                "duration_minutes": e.duration_minutes,
                "created_at": d(e.created_at),
            }
            for e in db.scalars(select(ActivityLog).order_by(ActivityLog.day)).all()
        ],
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "icon": p.icon,
                "aim": p.aim,
                "owner_name": player_map.get(p.owner_id, ""),
                "created_at": d(p.created_at),
                "tasks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "completed": t.completed,
                        "assignee_name": player_map.get(t.assignee_id, ""),
                        "completed_at": d(t.completed_at),
                    }
                    for t in db.scalars(select(ProjectTask).where(ProjectTask.project_id == p.id)).all()
                ],
            }
            for p in db.scalars(select(Project).order_by(Project.id)).all()
        ],
        "custom_tabs": [
            {
                "id": t.id,
                "name": t.name,
                "icon": t.icon,
                "tracking_type": t.tracking_type,
                "entries": [
                    {
                        "player_name": player_map.get(e.player_id, ""),
                        "day": d(e.day),
                        "label": e.label,
                        "value": e.value,
                        "note": e.note,
                    }
                    for e in db.scalars(select(CustomTabEntry).where(CustomTabEntry.tab_id == t.id)).all()
                ],
            }
            for t in db.scalars(select(CustomTab).order_by(CustomTab.id)).all()
        ],
        "points_events": [
            {
                "player_name": player_map.get(e.player_id, ""),
                "kind": e.kind,
                "points": e.points,
                "amount": e.amount,
                "created_at": d(e.created_at),
            }
            for e in db.scalars(select(PointsEvent).order_by(PointsEvent.created_at)).all()
        ],
    }
