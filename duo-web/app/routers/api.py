"""JSON API routes consumed by the vanilla-JS frontend."""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..auth import current_tracker_id, current_user_id
from ..config import settings
from ..db import SessionLocal, engine
from ..models import (
    AIKeySlot,
    ActivityLog,
    BackgroundSetting,
    CustomTab,
    CustomTabEntry,
    DailyStats,
    Player,
    PointsEvent,
    Project,
    ProjectNote,
    ProjectTask,
    StudyEntry,
    User,
)
from ..schemas import (
    AIKeyUpdate,
    ActivityCreate,
    BackgroundUpdate,
    ConfirmReset,
    CustomEntryCreate,
    CustomTabCreate,
    CustomTabUpdate,
    PlayerUpdate,
    ProjectCreate,
    ProjectNoteCreate,
    StudyCreate,
    StudyMinutesUpdate,
    TaskCreate,
    TaskToggle,
)
from ..services.ai_client import AIClientManager
from ..services.backup import create_backup, delete_backup, list_backups, restore_backup
from ..services.data_management import (
    clear_history,
    delete_activity_entry,
    delete_study_entry,
    delete_tab,
    rename_tab,
    reset_all_data,
    reset_player_score,
    reset_scores,
    export_json,
)
from ..services.rivalry import fallback_rivalry
from ..services.scoring import TASK_POINTS, get_daily_stats, streak_days, total_points, add_points
from ..services.security import decrypt_secret, mask_secret
from ..services.tenant import require_player, require_tracker

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# Resolve the DB file path from DATABASE_URL (works for sqlite:///./path style)
def _db_file_path() -> Path:
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///./"):
        return settings.BACKUP_DIR / url[len("sqlite:///./"):]
    if url.startswith("sqlite:///"):
        return Path(url[len("sqlite:///"):])
    return settings.BACKUP_DIR / "duo_tracker.db"


def get_db() -> Session:
    return SessionLocal()


def tracker_id_or_401() -> int:
    tracker_id = current_tracker_id()
    if tracker_id is None:
        raise HTTPException(401, "Please log in first.")
    return tracker_id


def players_payload(db: Session) -> list[dict]:
    rows = db.scalars(select(Player).where(Player.tracker_id == tracker_id_or_401()).order_by(Player.id)).all()
    return [{"id": p.id, "name": p.name, "emoji": p.emoji, "avatar_path": p.avatar_path, "accent": p.accent} for p in rows]


def safe_commit(db: Session) -> None:
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Database operation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Something went wrong while saving that change.") from exc


def project_payload(db: Session, project: Project) -> dict:
    tasks = db.scalars(select(ProjectTask).where(ProjectTask.project_id == project.id).order_by(ProjectTask.id)).all()
    notes = db.scalars(select(ProjectNote).where(ProjectNote.project_id == project.id).order_by(ProjectNote.created_at.desc())).all()
    players = {p.id: p for p in db.scalars(select(Player).where(Player.tracker_id == tracker_id_or_401())).all()}
    completed = sum(1 for task in tasks if task.completed)
    per_player = {}
    for player_id, player in players.items():
        mine = [t for t in tasks if t.assignee_id == player_id]
        per_player[player_id] = {
            "name": player.name,
            "completed": sum(t.completed for t in mine),
            "total": len(mine),
        }
    return {
        "id": project.id,
        "name": project.name,
        "icon": project.icon,
        "aim": project.aim,
        "owner_id": project.owner_id,
        "progress": round(completed / len(tasks) * 100) if tasks else 0,
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "completed": t.completed,
                "assignee_id": t.assignee_id,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ],
        "per_player": per_player,
        "notes": [
            {"id": n.id, "player_id": n.player_id, "day": n.day.isoformat(), "note": n.note}
            for n in notes
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Favicon (fixes browser 404)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse(url="/static/favicon.svg", status_code=301)


# ─────────────────────────────────────────────────────────────────────────────
# Application state
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/state")
def state():
    with get_db() as db:
        tracker_id = tracker_id_or_401()
        today = date.today()
        rows = []
        for player in db.scalars(select(Player).where(Player.tracker_id == tracker_id).order_by(Player.id)).all():
            stats = get_daily_stats(db, player.id, today)
            rows.append({
                "id": player.id,
                "name": player.name,
                "emoji": player.emoji,
                "avatar_path": player.avatar_path,
                "accent": player.accent,
                "study_minutes": stats.study_minutes,
                "workout_minutes": stats.workout_minutes,
                "points": total_points(db, player.id),
                "today_points": total_points(db, player.id, today, today),
                "streak": streak_days(db, player.id),
            })
        background = db.scalar(select(BackgroundSetting).where(BackgroundSetting.tracker_id == tracker_id))
        projects = db.scalars(select(Project).where(Project.tracker_id == tracker_id).order_by(Project.id.desc())).all()
        custom_tabs = db.scalars(select(CustomTab).where(CustomTab.tracker_id == tracker_id).order_by(CustomTab.id)).all()
        return {
            "players": rows,
            "background": {
                "theme": background.theme if background else "glass",
                "background_type": background.background_type if background else "gradient",
                "background_value": background.background_value if background else "aurora",
            },
            "projects": [project_payload(db, p) for p in projects],
            "custom_tabs": [{"id": t.id, "name": t.name, "icon": t.icon, "tracking_type": t.tracking_type} for t in custom_tabs],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Players
# ─────────────────────────────────────────────────────────────────────────────

@router.patch("/players/{player_id}")
def update_player(player_id: int, payload: PlayerUpdate):
    with get_db() as db:
        player = require_player(db, player_id)
        if not player:
            raise HTTPException(404, "Player not found.")
        player.name = payload.name.strip()
        if payload.emoji is not None:
            player.emoji = payload.emoji.strip() or player.emoji
        safe_commit(db)
        return {"ok": True, "player": {"id": player.id, "name": player.name, "emoji": player.emoji}}


@router.post("/players/{player_id}/avatar")
def upload_avatar(player_id: int, file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "Please upload a PNG, JPEG, WEBP, or GIF image.")
    with get_db() as db:
        player = require_player(db, player_id)
        if not player:
            raise HTTPException(404, "Player not found.")
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(400, "Avatar must be 5 MB or smaller.")
        extension = Path(file.filename or "avatar.png").suffix.lower() or ".png"
        filename = f"avatar-{player_id}-{uuid.uuid4().hex}{extension}"
        destination = settings.UPLOAD_DIR / filename
        destination.write_bytes(data)
        player.avatar_path = f"/uploads/{filename}"
        safe_commit(db)
        return {"ok": True, "avatar_path": player.avatar_path}


@router.get("/players/{player_id}/stats")
def player_stats(player_id: int):
    """Detailed statistics for a single player."""
    with get_db() as db:
        player = require_player(db, player_id)
        if not player:
            raise HTTPException(404, "Player not found.")
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        study_count = db.scalar(select(func.count(StudyEntry.id)).where(StudyEntry.player_id == player_id)) or 0
        activity_count = db.scalar(select(func.count(ActivityLog.id)).where(ActivityLog.player_id == player_id)) or 0
        return {
            "id": player.id,
            "name": player.name,
            "emoji": player.emoji,
            "all_time_points": total_points(db, player.id),
            "weekly_points": total_points(db, player.id, week_start, today),
            "today_points": total_points(db, player.id, today, today),
            "streak": streak_days(db, player.id),
            "study_entries": study_count,
            "activity_entries": activity_count,
            "total_activities": study_count + activity_count,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Background
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/background")
def update_background(payload: BackgroundUpdate):
    with get_db() as db:
        tracker_id = tracker_id_or_401()
        bg = db.scalar(select(BackgroundSetting).where(BackgroundSetting.tracker_id == tracker_id))
        if bg is None:
            bg = BackgroundSetting(tracker_id=tracker_id)
            db.add(bg)
        bg.theme = payload.theme
        bg.background_type = payload.background_type
        bg.background_value = payload.background_value
        safe_commit(db)
        return {"ok": True}


@router.post("/background/upload")
def upload_background(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "Please upload a PNG, JPEG, WEBP, or GIF image.")
    data = file.file.read(MAX_UPLOAD_BYTES * 2 + 1)
    if len(data) > MAX_UPLOAD_BYTES * 2:
        raise HTTPException(400, "Background image must be 10 MB or smaller.")
    extension = Path(file.filename or "background.png").suffix.lower() or ".png"
    filename = f"background-{uuid.uuid4().hex}{extension}"
    destination = settings.UPLOAD_DIR / filename
    destination.write_bytes(data)
    with get_db() as db:
        tracker_id = tracker_id_or_401()
        bg = db.scalar(select(BackgroundSetting).where(BackgroundSetting.tracker_id == tracker_id))
        if bg is None:
            bg = BackgroundSetting(tracker_id=tracker_id)
        db.add(bg)
        bg.background_type = "image"
        bg.background_value = f"/uploads/{filename}"
        safe_commit(db)
    return {"ok": True, "background_value": f"/uploads/{filename}"}


# ─────────────────────────────────────────────────────────────────────────────
# Education
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/education")
def education_data():
    with get_db() as db:
        players = db.scalars(select(Player).where(Player.tracker_id == tracker_id_or_401()).order_by(Player.id)).all()
        result = []
        for p in players:
            entries = db.scalars(select(StudyEntry).where(StudyEntry.player_id == p.id).order_by(StudyEntry.created_at.desc()).limit(15)).all()
            result.append({
                "player_id": p.id,
                "name": p.name,
                "today_minutes": get_daily_stats(db, p.id).study_minutes,
                "entries": [{"id": e.id, "day": e.day.isoformat(), "subject": e.subject, "notes": e.notes, "minutes": e.minutes} for e in entries],
            })
        return {"players": result}


@router.post("/education/entries")
def add_study(payload: StudyCreate):
    with get_db() as db:
        require_player(db, payload.player_id)
        entry = StudyEntry(player_id=payload.player_id, subject=payload.subject.strip(), notes=payload.notes.strip(), minutes=0)
        db.add(entry)
        safe_commit(db)
        return {"ok": True, "entry_id": entry.id}


@router.delete("/education/entries/{entry_id}")
def delete_study_entry_route(entry_id: int):
    with get_db() as db:
        try:
            delete_study_entry(db, entry_id, tracker_id_or_401())
            safe_commit(db)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to delete study entry %s: %s", entry_id, exc)
            raise HTTPException(500, "Unable to delete the entry. Your data was not changed.") from exc
    return {"ok": True}


@router.put("/education/today")
def update_study_minutes(payload: StudyMinutesUpdate):
    with get_db() as db:
        require_player(db, payload.player_id)
        stats = get_daily_stats(db, payload.player_id)
        delta = payload.minutes - stats.study_minutes
        stats.study_minutes = payload.minutes
        if delta > 0:
            add_points(db, payload.player_id, "study_adjustment", delta, delta)
        safe_commit(db)
        return {"ok": True, "today_minutes": stats.study_minutes}


# ─────────────────────────────────────────────────────────────────────────────
# Fitness
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/fitness")
def fitness_data():
    with get_db() as db:
        result = []
        for p in db.scalars(select(Player).where(Player.tracker_id == tracker_id_or_401()).order_by(Player.id)).all():
            logs = db.scalars(select(ActivityLog).where(ActivityLog.player_id == p.id).order_by(ActivityLog.created_at.desc()).limit(15)).all()
            result.append({
                "player_id": p.id,
                "name": p.name,
                "today_minutes": get_daily_stats(db, p.id).workout_minutes,
                "entries": [{"id": e.id, "day": e.day.isoformat(), "activity": e.activity, "duration_minutes": e.duration_minutes} for e in logs],
            })
        return {"players": result}


@router.post("/fitness")
def add_activity(payload: ActivityCreate):
    with get_db() as db:
        require_player(db, payload.player_id)
        log = ActivityLog(player_id=payload.player_id, activity=payload.activity.strip(), duration_minutes=payload.duration_minutes)
        db.add(log)
        stats = get_daily_stats(db, payload.player_id)
        stats.workout_minutes += payload.duration_minutes
        add_points(db, payload.player_id, "workout", payload.duration_minutes, payload.duration_minutes, "activity", log.id)
        safe_commit(db)
        return {"ok": True, "entry_id": log.id}


@router.delete("/fitness/{entry_id}")
def delete_activity_entry_route(entry_id: int):
    with get_db() as db:
        try:
            delete_activity_entry(db, entry_id, tracker_id_or_401())
            safe_commit(db)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to delete activity entry %s: %s", entry_id, exc)
            raise HTTPException(500, "Unable to delete the activity. Your data was not changed.") from exc
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/projects")
def project_list():
    with get_db() as db:
        projects = db.scalars(
            select(Project).where(Project.tracker_id == tracker_id_or_401()).order_by(Project.id.desc())
        ).all()
        return {"projects": [project_payload(db, p) for p in projects]}


@router.post("/projects")
def create_project(payload: ProjectCreate):
    with get_db() as db:
        tracker_id = tracker_id_or_401()
        owner_id = payload.owner_id
        if owner_id is not None:
            require_player(db, owner_id)
        else:
            owner_id = db.scalar(select(User.player_id).where(User.id == current_user_id()))
            if owner_id is not None:
                require_player(db, owner_id)
        project = Project(
            tracker_id=tracker_id,
            name=payload.name.strip(),
            icon=payload.icon.strip(),
            aim=payload.aim.strip(),
            owner_id=owner_id,
        )
        db.add(project)
        safe_commit(db)
        return {"ok": True, "project": project_payload(db, project)}


@router.get("/projects/{project_id}")
def get_project(project_id: int):
    with get_db() as db:
        project = db.scalar(select(Project).where(Project.id == project_id, Project.tracker_id == tracker_id_or_401()))
        if not project:
            raise HTTPException(404, "Project not found in this tracker.")
        return project_payload(db, project)


@router.post("/projects/{project_id}/tasks")
def create_task(project_id: int, payload: TaskCreate):
    with get_db() as db:
        project = db.scalar(select(Project).where(Project.id == project_id, Project.tracker_id == tracker_id_or_401()))
        if not project:
            raise HTTPException(404, "Project not found in this tracker.")
        if payload.assignee_id is not None:
            require_player(db, payload.assignee_id)
        task = ProjectTask(project_id=project_id, title=payload.title.strip(), assignee_id=payload.assignee_id)
        db.add(task)
        safe_commit(db)
        return {"ok": True, "task": {"id": task.id, "title": task.title, "completed": task.completed, "assignee_id": task.assignee_id}}


@router.patch("/projects/tasks/{task_id}")
def toggle_task(task_id: int, payload: TaskToggle):
    with get_db() as db:
        task = db.scalar(select(ProjectTask).join(Project, ProjectTask.project_id == Project.id).where(ProjectTask.id == task_id, Project.tracker_id == tracker_id_or_401()))
        if not task:
            raise HTTPException(404, "Task not found in this tracker.")
        was_completed = task.completed
        task.completed = payload.completed
        if payload.completed and not was_completed:
            task.completed_at = datetime.now(timezone.utc)
            if task.assignee_id:
                already_awarded = db.scalar(select(PointsEvent.id).where(PointsEvent.reference_type == "project_task", PointsEvent.reference_id == task.id).limit(1))
                if already_awarded is None:
                    add_points(db, task.assignee_id, "task", TASK_POINTS, 1, "project_task", task.id)
        safe_commit(db)
        return {"ok": True, "completed": task.completed}


@router.post("/projects/{project_id}/notes")
def add_project_note(project_id: int, payload: ProjectNoteCreate):
    with get_db() as db:
        if not db.scalar(select(Project.id).where(Project.id == project_id, Project.tracker_id == tracker_id_or_401())):
            raise HTTPException(404, "Project not found in this tracker.")
        require_player(db, payload.player_id)
        note = ProjectNote(project_id=project_id, player_id=payload.player_id, note=payload.note.strip())
        db.add(note)
        safe_commit(db)
        return {"ok": True, "note_id": note.id}


# ─────────────────────────────────────────────────────────────────────────────
# Custom Tabs
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/custom-tabs")
def create_custom_tab(payload: CustomTabCreate):
    with get_db() as db:
        tracker_id = tracker_id_or_401()
        creator_id = payload.created_by
        if creator_id is not None:
            require_player(db, creator_id)
        if creator_id is None:
            from ..auth import current_user_id
            from ..models import User
            creator_id = db.scalar(select(User.player_id).where(User.id == current_user_id())) if current_user_id() else None
        tab = CustomTab(tracker_id=tracker_id, name=payload.name.strip(), icon=payload.icon.strip(), tracking_type=payload.tracking_type, created_by=creator_id)
        db.add(tab)
        safe_commit(db)
        return {"ok": True, "tab": {"id": tab.id, "name": tab.name, "icon": tab.icon, "tracking_type": tab.tracking_type}}


@router.patch("/custom-tabs/{tab_id}")
def update_custom_tab(tab_id: int, payload: CustomTabUpdate):
    with get_db() as db:
        try:
            rename_tab(db, tab_id, payload.name, payload.icon, tracker_id_or_401())
            safe_commit(db)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        tab = db.scalar(select(CustomTab).where(CustomTab.id == tab_id, CustomTab.tracker_id == tracker_id_or_401()))
        if tab is None:
            raise HTTPException(404, "Custom tab not found in this tracker.")
        return {"ok": True, "tab": {"id": tab.id, "name": tab.name, "icon": tab.icon}}


@router.delete("/custom-tabs/{tab_id}")
def delete_custom_tab(tab_id: int):
    with get_db() as db:
        try:
            name = delete_tab(db, tab_id, tracker_id_or_401())
            safe_commit(db)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to delete custom tab %s: %s", tab_id, exc)
            raise HTTPException(500, "Unable to delete the tab. Your data was not changed.") from exc
    return {"ok": True, "name": name}


@router.get("/custom-tabs/{tab_id}")
def custom_tab_data(tab_id: int):
    with get_db() as db:
        tab = db.scalar(select(CustomTab).where(CustomTab.id == tab_id, CustomTab.tracker_id == tracker_id_or_401()))
        if not tab:
            raise HTTPException(404, "Custom tab not found in this tracker.")
        result = []
        for p in db.scalars(select(Player).where(Player.tracker_id == tracker_id_or_401()).order_by(Player.id)).all():
            entries = db.scalars(select(CustomTabEntry).where(CustomTabEntry.tab_id == tab_id, CustomTabEntry.player_id == p.id).order_by(CustomTabEntry.created_at.desc()).limit(30)).all()
            result.append({"player_id": p.id, "name": p.name, "entries": [{"id": e.id, "day": e.day.isoformat(), "label": e.label, "value": e.value, "note": e.note} for e in entries]})
        return {"tab": {"id": tab.id, "name": tab.name, "icon": tab.icon, "tracking_type": tab.tracking_type}, "players": result}


@router.post("/custom-tabs/{tab_id}/entries")
def add_custom_entry(tab_id: int, payload: CustomEntryCreate):
    with get_db() as db:
        if not db.scalar(select(CustomTab.id).where(CustomTab.id == tab_id, CustomTab.tracker_id == tracker_id_or_401())):
            raise HTTPException(404, "Custom tab not found in this tracker.")
        require_player(db, payload.player_id)
        entry = CustomTabEntry(tab_id=tab_id, player_id=payload.player_id, label=payload.label.strip(), value=payload.value, note=payload.note.strip())
        db.add(entry)
        safe_commit(db)
        return {"ok": True, "entry_id": entry.id}


# ─────────────────────────────────────────────────────────────────────────────
# Leaderboard & Charts
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/leaderboard")
def leaderboard_data():
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    with get_db() as db:
        result = []
        for p in db.scalars(select(Player).where(Player.tracker_id == tracker_id_or_401()).order_by(Player.id)).all():
            study_count = db.scalar(select(func.count(StudyEntry.id)).where(StudyEntry.player_id == p.id)) or 0
            activity_count = db.scalar(select(func.count(ActivityLog.id)).where(ActivityLog.player_id == p.id)) or 0
            result.append({
                "id": p.id,
                "name": p.name,
                "emoji": p.emoji,
                "all_time": total_points(db, p.id),
                "weekly": total_points(db, p.id, week_start, today),
                "today": total_points(db, p.id, today, today),
                "streak": streak_days(db, p.id),
                "total_activities": study_count + activity_count,
            })
        result.sort(key=lambda x: x["weekly"], reverse=True)
        for index, row in enumerate(result, 1):
            row["rank"] = index
        return {"players": result}


@router.get("/charts")
def chart_data(days: int = 14):
    days = max(7, min(days, 60))
    start = date.today() - timedelta(days=days - 1)
    labels = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    with get_db() as db:
        player_rows = db.scalars(select(Player).where(Player.tracker_id == tracker_id_or_401()).order_by(Player.id)).all()
        result = {"labels": labels, "players": []}
        for p in player_rows:
            stats = db.scalars(select(DailyStats).where(DailyStats.player_id == p.id, DailyStats.day >= start).order_by(DailyStats.day)).all()
            stat_map = {s.day.isoformat(): s for s in stats}
            daily_points = {d: 0 for d in labels}
            events = db.scalars(select(PointsEvent).where(PointsEvent.player_id == p.id, func.date(PointsEvent.created_at) >= start.isoformat())).all()
            for event in events:
                key = event.created_at.astimezone().date().isoformat() if event.created_at.tzinfo else event.created_at.date().isoformat()
                if key in daily_points:
                    daily_points[key] += event.points
            result["players"].append({
                "id": p.id,
                "name": p.name,
                "study": [stat_map[d].study_minutes if d in stat_map else 0 for d in labels],
                "workout": [stat_map[d].workout_minutes if d in stat_map else 0 for d in labels],
                "points": [daily_points[d] for d in labels],
            })
        return result


@router.get("/graph")
def graph_data():
    with get_db() as db:
        tracker_id = tracker_id_or_401()
        players = db.scalars(select(Player).where(Player.tracker_id == tracker_id).order_by(Player.id)).all()
        player_ids = [p.id for p in players]
        nodes: list[dict] = []
        edges: list[dict] = []

        for index, p in enumerate(players):
            user_color = "#5867ff" if index == 0 else "#ed4db6"
            nodes.append({"id": f"p{p.id}", "label": p.name, "group": "player", "title": "Player", "user_color": user_color})

        projects = db.scalars(select(Project).where(Project.tracker_id == tracker_id)).all()
        project_ids = [project.id for project in projects]
        for project in projects:
            pid = f"project-{project.id}"
            nodes.append({"id": pid, "label": project.name, "group": "project", "title": project.aim})
            if project.owner_id in player_ids:
                edges.append({"from": f"p{project.owner_id}", "to": pid, "label": "owns"})
            for task in project.tasks:
                tid = f"task-{task.id}"
                if task.assignee_id in player_ids:
                    task_color = "#5867ff" if players and task.assignee_id == players[0].id else "#ed4db6"
                else:
                    task_color = "#13c8aa"
                nodes.append({"id": tid, "label": task.title, "group": "task", "title": "Task", "user_color": task_color})
                edges.append({"from": pid, "to": tid, "label": "mission"})
                if task.assignee_id in player_ids:
                    edges.append({"from": f"p{task.assignee_id}", "to": tid, "label": "assigned"})

        if player_ids:
            subjects = db.scalars(
                select(StudyEntry.subject).where(StudyEntry.player_id.in_(player_ids)).distinct()
            ).all()
            for index, subject in enumerate(subjects, 1):
                sid = f"subject-{index}"
                nodes.append({"id": sid, "label": str(subject), "group": "subject", "title": "Study subject"})
                for entry in db.scalars(
                    select(StudyEntry).where(StudyEntry.player_id.in_(player_ids), StudyEntry.subject == subject).limit(3)
                ).all():
                    edges.append({"from": f"p{entry.player_id}", "to": sid, "label": "studies"})

            activities = db.scalars(
                select(ActivityLog.activity).where(ActivityLog.player_id.in_(player_ids)).distinct()
            ).all()
            for index, activity in enumerate(activities, 1):
                aid = f"activity-{index}"
                nodes.append({"id": aid, "label": str(activity), "group": "activity", "title": "Physical activity"})
                for entry in db.scalars(
                    select(ActivityLog).where(ActivityLog.player_id.in_(player_ids), ActivityLog.activity == activity).limit(3)
                ).all():
                    edges.append({"from": f"p{entry.player_id}", "to": aid, "label": "does"})

        return {"nodes": nodes, "edges": edges}


# ─────────────────────────────────────────────────────────────────────────────
# AI
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/rivalry")
def rivalry_data(ai: bool = True):
    with get_db() as db:
        players = db.scalars(select(Player).where(Player.tracker_id == tracker_id_or_401()).order_by(Player.id)).all()
        if len(players) < 2:
            return {"message": "Add two players to unlock rivalry mode.", "source": "template"}
        p1, p2 = players[:2]
        a = total_points(db, p1.id, date.today(), date.today())
        b = total_points(db, p2.id, date.today(), date.today())
        fallback = fallback_rivalry(p1.name, a, p2.name, b)
        if not ai:
            return {"message": fallback, "source": "template", "points": {"p1": a, "p2": b}}
        try:
            prompt = (
                f"Create one short playful rivalry banner for two friends. {p1.name} has {a} points today and {p2.name} has {b}. "
                "Avoid insults, keep it friendly, under 18 words."
            )
            text, slot = AIClientManager(db).generate(prompt, temperature=0.85)
            return {"message": text, "source": f"ai-slot-{slot}", "points": {"p1": a, "p2": b}}
        except Exception as exc:
            logger.info("Rivalry AI unavailable; using fallback: %s", type(exc).__name__)
            return {"message": fallback, "source": "template", "points": {"p1": a, "p2": b}}


@router.get("/ai/summary")
def ai_summary(kind: str = "summary"):
    with get_db() as db:
        players = db.scalars(select(Player).where(Player.tracker_id == tracker_id_or_401()).order_by(Player.id)).all()
        prompt = ""
        if kind == "suggestions":
            prompt = "Give three practical study suggestions for two friends tracking education, projects, and fitness. Make them concise."
        else:
            summaries = []
            for p in players:
                stats = get_daily_stats(db, p.id)
                summaries.append(f"{p.name}: {stats.study_minutes} study minutes, {stats.workout_minutes} workout minutes, {streak_days(db, p.id)} day streak")
            prompt = "Create a concise motivational daily summary from these stats: " + "; ".join(summaries)
        try:
            text, slot = AIClientManager(db).generate(prompt, temperature=0.65)
            return {"ok": True, "text": text, "source": f"ai-slot-{slot}"}
        except Exception as exc:
            return JSONResponse(status_code=503, content={"ok": False, "message": "AI is not configured or is temporarily unavailable. Configure a key in Settings.", "error_type": type(exc).__name__})


# ─────────────────────────────────────────────────────────────────────────────
# AI Settings
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/settings/ai")
def ai_settings():
    with get_db() as db:
        rows = db.scalars(select(AIKeySlot).where(AIKeySlot.tracker_id == tracker_id_or_401()).order_by(AIKeySlot.slot)).all()
        return {
            "slots": [
                {
                    "slot": r.slot,
                    "provider": r.provider,
                    "base_url": r.base_url,
                    "model": r.model,
                    "masked_key": mask_secret(decrypt_secret(r.encrypted_key)),
                    "has_key": bool(r.encrypted_key),
                    "enabled": r.enabled,
                    "last_status": r.last_status,
                    "last_error": r.last_error,
                }
                for r in rows
            ]
        }


@router.put("/settings/ai/{slot_number}")
def save_ai_slot(slot_number: int, payload: AIKeyUpdate):
    if slot_number not in {1, 2, 3}:
        raise HTTPException(400, "AI slot must be 1, 2, or 3.")
    with get_db() as db:
        manager = AIClientManager(db)
        manager.save_slot(slot_number, payload.provider, payload.base_url.rstrip("/"), payload.model, payload.key, payload.enabled)
        safe_commit(db)
        return {"ok": True}


@router.post("/settings/ai/{slot_number}/test")
def test_ai_slot(slot_number: int):
    if slot_number not in {1, 2, 3}:
        raise HTTPException(400, "AI slot must be 1, 2, or 3.")
    with get_db() as db:
        ok, message = AIClientManager(db).test_slot(slot_number)
        safe_commit(db)
        return {"ok": ok, "message": message}


@router.post("/settings/ai/test-failover")
def test_ai_failover():
    with get_db() as db:
        ok, message, used_slot = AIClientManager(db).test_failover()
        safe_commit(db)
        return {"ok": ok, "message": message, "used_slot": used_slot}


# ─────────────────────────────────────────────────────────────────────────────
# Data Management
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/data/reset-player/{player_id}")
def reset_player_score_route(player_id: int):
    with get_db() as db:
        try:
            reset_player_score(db, player_id, tracker_id_or_401())
            safe_commit(db)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to reset player score %s: %s", player_id, exc)
            raise HTTPException(500, "Unable to reset the player score. Your data was not changed.") from exc
    return {"ok": True}


@router.post("/data/clear-history")
def clear_history_route():
    with get_db() as db:
        try:
            clear_history(db, tracker_id_or_401())
            safe_commit(db)
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to clear history: %s", exc)
            raise HTTPException(500, "Unable to clear history. Your data was not changed.") from exc
    return {"ok": True}


@router.post("/data/reset-scores")
def reset_scores_route():
    with get_db() as db:
        try:
            reset_scores(db, tracker_id_or_401())
            safe_commit(db)
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to reset scores: %s", exc)
            raise HTTPException(500, "Unable to reset scores. Your data was not changed.") from exc
    return {"ok": True}


@router.post("/data/reset-all")
def reset_all_route(payload: ConfirmReset):
    if payload.confirmation != "RESET":
        raise HTTPException(400, "Confirmation text must be exactly 'RESET'.")
    # Create a backup before destroying data
    backup_filename: str | None = None
    db_path = _db_file_path()
    try:
        backup_filename = create_backup(db_path, settings.BACKUP_DIR)
        logger.info("Pre-reset backup created: %s", backup_filename)
    except Exception as exc:
        logger.warning("Could not create pre-reset backup: %s", exc)

    with get_db() as db:
        try:
            reset_all_data(db, tracker_id_or_401())
            safe_commit(db)
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to reset all data: %s", exc)
            raise HTTPException(500, "Unable to reset data. Your data was not changed.") from exc
    return {"ok": True, "backup_created": backup_filename}


# ─────────────────────────────────────────────────────────────────────────────
# Backups
# ─────────────────────────────────────────────────────────────────────────────

def _require_global_backup_access() -> None:
    if not settings.ALLOW_GLOBAL_BACKUPS:
        raise HTTPException(403, "Manual database backups are disabled in multi-tracker mode. Tracker data can be exported from Data Management.")


@router.get("/data/backups")
def list_backups_route():
    _require_global_backup_access()
    try:
        backups = list_backups(settings.BACKUP_DIR)
    except Exception as exc:
        logger.exception("Failed to list backups: %s", exc)
        raise HTTPException(500, "Unable to list backups.") from exc
    return {"backups": backups}


@router.post("/data/backup")
def create_backup_route():
    _require_global_backup_access()
    db_path = _db_file_path()
    try:
        filename = create_backup(db_path, settings.BACKUP_DIR)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Database file not found.") from exc
    except Exception as exc:
        logger.exception("Failed to create backup: %s", exc)
        raise HTTPException(500, "Unable to create backup.") from exc
    return {"ok": True, "filename": filename}


@router.post("/data/restore/{filename}")
def restore_backup_route(filename: str):
    _require_global_backup_access()
    # Prevent directory traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid backup filename.")
    db_path = _db_file_path()
    try:
        restore_backup(filename, db_path, settings.BACKUP_DIR)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Backup file not found.") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to restore backup %s: %s", filename, exc)
        raise HTTPException(500, "Unable to restore backup. The database was not modified.") from exc
    # Dispose engine connection pool so next request uses the freshly restored file
    engine.dispose()
    return {"ok": True, "message": "Backup restored. Please refresh the application."}


@router.delete("/data/backups/{filename}")
def delete_backup_route(filename: str):
    _require_global_backup_access()
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid backup filename.")
    try:
        delete_backup(filename, settings.BACKUP_DIR)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Backup file not found.") from exc
    except Exception as exc:
        logger.exception("Failed to delete backup %s: %s", filename, exc)
        raise HTTPException(500, "Unable to delete backup.") from exc
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# Export / Import
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/export.csv")
def export_csv():
    with get_db() as db:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["type", "player", "date", "label", "value", "notes"])
        players = {p.id: p.name for p in db.scalars(select(Player).where(Player.tracker_id == tracker_id_or_401())).all()}
        player_ids = list(players.keys())
        study_query = select(StudyEntry).where(StudyEntry.player_id.in_(player_ids)) if player_ids else select(StudyEntry).where(StudyEntry.id == -1)
        activity_query = select(ActivityLog).where(ActivityLog.player_id.in_(player_ids)) if player_ids else select(ActivityLog).where(ActivityLog.id == -1)
        for row in db.scalars(study_query.order_by(StudyEntry.day)).all():
            writer.writerow(["study", players.get(row.player_id, ""), row.day, row.subject, row.minutes, row.notes])
        for row in db.scalars(activity_query.order_by(ActivityLog.day)).all():
            writer.writerow(["activity", players.get(row.player_id, ""), row.day, row.activity, row.duration_minutes, ""])
        for row in db.scalars(select(ProjectTask).join(Project, ProjectTask.project_id == Project.id).where(Project.tracker_id == tracker_id_or_401()).order_by(ProjectTask.id)).all():
            writer.writerow(["project_task", players.get(row.assignee_id, ""), row.completed_at.date() if row.completed_at else "", row.title, int(row.completed), ""])
        output.seek(0)
        headers = {"Content-Disposition": 'attachment; filename="duo_tracker_export.csv"'}
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)


@router.get("/export.json")
def export_json_route():
    with get_db() as db:
        data = export_json(db, tracker_id_or_401())
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    headers = {"Content-Disposition": 'attachment; filename="duo_tracker_export.json"'}
    return StreamingResponse(iter([json_bytes]), media_type="application/json", headers=headers)
