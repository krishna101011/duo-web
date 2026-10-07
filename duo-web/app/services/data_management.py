"""Tenant-scoped data management for Duo Tracker."""
from __future__ import annotations

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


def _player_ids(db: Session, tracker_id: int) -> list[int]:
    return list(db.scalars(select(Player.id).where(Player.tracker_id == tracker_id)).all())


def _project_ids(db: Session, tracker_id: int) -> list[int]:
    return list(db.scalars(select(Project.id).where(Project.tracker_id == tracker_id)).all())


def _tab_ids(db: Session, tracker_id: int) -> list[int]:
    return list(db.scalars(select(CustomTab.id).where(CustomTab.tracker_id == tracker_id)).all())


def delete_study_entry(db: Session, entry_id: int, tracker_id: int) -> None:
    entry = db.scalar(
        select(StudyEntry).join(Player, StudyEntry.player_id == Player.id).where(
            StudyEntry.id == entry_id, Player.tracker_id == tracker_id
        )
    )
    if entry is None:
        raise ValueError(f"Study entry {entry_id} not found in this tracker.")
    db.execute(delete(PointsEvent).where(PointsEvent.player_id == entry.player_id, PointsEvent.reference_type == "study_entry", PointsEvent.reference_id == entry_id))
    stats = db.scalar(select(DailyStats).where(DailyStats.player_id == entry.player_id, DailyStats.day == entry.day))
    if stats:
        stats.study_minutes = max(0, stats.study_minutes - entry.minutes)
    db.delete(entry)
    db.flush()


def delete_activity_entry(db: Session, entry_id: int, tracker_id: int) -> None:
    entry = db.scalar(
        select(ActivityLog).join(Player, ActivityLog.player_id == Player.id).where(
            ActivityLog.id == entry_id, Player.tracker_id == tracker_id
        )
    )
    if entry is None:
        raise ValueError(f"Activity entry {entry_id} not found in this tracker.")
    db.execute(delete(PointsEvent).where(PointsEvent.player_id == entry.player_id, PointsEvent.reference_type == "activity", PointsEvent.reference_id == entry_id))
    stats = db.scalar(select(DailyStats).where(DailyStats.player_id == entry.player_id, DailyStats.day == entry.day))
    if stats:
        stats.workout_minutes = max(0, stats.workout_minutes - entry.duration_minutes)
    db.delete(entry)
    db.flush()


def delete_tab(db: Session, tab_id: int, tracker_id: int) -> str:
    tab = db.scalar(select(CustomTab).where(CustomTab.id == tab_id, CustomTab.tracker_id == tracker_id))
    if tab is None:
        raise ValueError(f"Custom tab {tab_id} not found in this tracker.")
    name = tab.name
    db.delete(tab)
    db.flush()
    return name


def rename_tab(db: Session, tab_id: int, new_name: str, new_icon: str | None, tracker_id: int) -> None:
    tab = db.scalar(select(CustomTab).where(CustomTab.id == tab_id, CustomTab.tracker_id == tracker_id))
    if tab is None:
        raise ValueError(f"Custom tab {tab_id} not found in this tracker.")
    tab.name = new_name.strip()
    if new_icon is not None:
        tab.icon = new_icon.strip() or tab.icon
    db.flush()


def reset_player_score(db: Session, player_id: int, tracker_id: int) -> None:
    player = db.scalar(select(Player).where(Player.id == player_id, Player.tracker_id == tracker_id))
    if player is None:
        raise ValueError(f"Player {player_id} not found in this tracker.")
    db.execute(delete(PointsEvent).where(PointsEvent.player_id == player_id))
    db.execute(delete(DailyStats).where(DailyStats.player_id == player_id))
    db.flush()


def reset_scores(db: Session, tracker_id: int) -> None:
    pids = _player_ids(db, tracker_id)
    if not pids:
        return
    db.execute(delete(PointsEvent).where(PointsEvent.player_id.in_(pids)))
    db.execute(delete(DailyStats).where(DailyStats.player_id.in_(pids)))
    db.flush()


def clear_history(db: Session, tracker_id: int) -> None:
    pids = _player_ids(db, tracker_id)
    tids = _tab_ids(db, tracker_id)
    prids = _project_ids(db, tracker_id)
    if pids:
        db.execute(delete(StudyEntry).where(StudyEntry.player_id.in_(pids)))
        db.execute(delete(ActivityLog).where(ActivityLog.player_id.in_(pids)))
        db.execute(delete(PointsEvent).where(PointsEvent.player_id.in_(pids)))
        db.execute(delete(DailyStats).where(DailyStats.player_id.in_(pids)))
        db.execute(delete(ProjectNote).where(ProjectNote.player_id.in_(pids)))
    if tids:
        db.execute(delete(CustomTabEntry).where(CustomTabEntry.tab_id.in_(tids)))
    if prids:
        db.execute(delete(ProjectNote).where(ProjectNote.project_id.in_(prids)))
        for task in db.scalars(select(ProjectTask).where(ProjectTask.project_id.in_(prids))).all():
            task.completed = False
            task.completed_at = None
    db.flush()


def reset_all_data(db: Session, tracker_id: int) -> None:
    pids = _player_ids(db, tracker_id)
    tids = _tab_ids(db, tracker_id)
    prids = _project_ids(db, tracker_id)
    if pids:
        db.execute(delete(PointsEvent).where(PointsEvent.player_id.in_(pids)))
        db.execute(delete(DailyStats).where(DailyStats.player_id.in_(pids)))
        db.execute(delete(StudyEntry).where(StudyEntry.player_id.in_(pids)))
        db.execute(delete(ActivityLog).where(ActivityLog.player_id.in_(pids)))
        db.execute(delete(ProjectNote).where(ProjectNote.player_id.in_(pids)))
        db.execute(delete(ProjectTask).where(ProjectTask.project_id.in_(prids))) if prids else None
    if tids:
        db.execute(delete(CustomTabEntry).where(CustomTabEntry.tab_id.in_(tids)))
        db.execute(delete(CustomTab).where(CustomTab.id.in_(tids)))
    if prids:
        db.execute(delete(ProjectNote).where(ProjectNote.project_id.in_(prids)))
        db.execute(delete(Project).where(Project.id.in_(prids)))
    db.flush()


def export_json(db: Session, tracker_id: int) -> dict[str, Any]:
    players = db.scalars(select(Player).where(Player.tracker_id == tracker_id).order_by(Player.id)).all()
    player_map = {p.id: p.name for p in players}
    pids = [p.id for p in players]
    projects = db.scalars(select(Project).where(Project.tracker_id == tracker_id).order_by(Project.id)).all()
    tabs = db.scalars(select(CustomTab).where(CustomTab.tracker_id == tracker_id).order_by(CustomTab.id)).all()
    prids = [p.id for p in projects]
    tids = [t.id for t in tabs]

    def d(val: date | datetime | None) -> str | None:
        return val.isoformat() if val is not None and hasattr(val, "isoformat") else (str(val) if val is not None else None)

    return {
        "export_version": 2,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "players": [
            {"id": p.id, "name": p.name, "emoji": p.emoji, "accent": p.accent, "created_at": d(p.created_at)}
            for p in players
        ],
        "study_entries": [
            {"id": e.id, "player_name": player_map.get(e.player_id, ""), "day": d(e.day), "subject": e.subject, "notes": e.notes, "minutes": e.minutes, "created_at": d(e.created_at)}
            for e in db.scalars(select(StudyEntry).where(StudyEntry.player_id.in_(pids)) if pids else select(StudyEntry).where(StudyEntry.id == -1)).all()
        ],
        "activity_logs": [
            {"id": e.id, "player_name": player_map.get(e.player_id, ""), "day": d(e.day), "activity": e.activity, "duration_minutes": e.duration_minutes, "created_at": d(e.created_at)}
            for e in db.scalars(select(ActivityLog).where(ActivityLog.player_id.in_(pids)) if pids else select(ActivityLog).where(ActivityLog.id == -1)).all()
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
                    {"id": t.id, "title": t.title, "completed": t.completed, "assignee_name": player_map.get(t.assignee_id, ""), "completed_at": d(t.completed_at)}
                    for t in db.scalars(select(ProjectTask).where(ProjectTask.project_id == p.id)).all()
                ],
            }
            for p in projects
        ],
        "custom_tabs": [
            {
                "id": t.id,
                "name": t.name,
                "icon": t.icon,
                "tracking_type": t.tracking_type,
                "entries": [
                    {"player_name": player_map.get(e.player_id, ""), "day": d(e.day), "label": e.label, "value": e.value, "note": e.note}
                    for e in db.scalars(select(CustomTabEntry).where(CustomTabEntry.tab_id == t.id)).all()
                ],
            }
            for t in tabs
        ],
        "points_events": [
            {"player_name": player_map.get(e.player_id, ""), "kind": e.kind, "points": e.points, "amount": e.amount, "created_at": d(e.created_at)}
            for e in db.scalars(select(PointsEvent).where(PointsEvent.player_id.in_(pids)) if pids else select(PointsEvent).where(PointsEvent.id == -1)).all()
        ],
    }
