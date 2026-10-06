"""JSON API routes consumed by the vanilla-JS frontend."""
from __future__ import annotations

import csv
import io
import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
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
)
from ..schemas import (
    AIKeyUpdate,
    ActivityCreate,
    BackgroundUpdate,
    CustomEntryCreate,
    CustomTabCreate,
    PlayerUpdate,
    ProjectCreate,
    ProjectNoteCreate,
    StudyCreate,
    StudyMinutesUpdate,
    TaskCreate,
    TaskToggle,
)
from ..services.ai_client import AIClientManager
from ..services.rivalry import fallback_rivalry
from ..services.scoring import TASK_POINTS, get_daily_stats, streak_days, total_points, add_points
from ..services.security import decrypt_secret, mask_secret

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def get_db() -> Session:
    return SessionLocal()


def players_payload(db: Session) -> list[dict]:
    rows = db.scalars(select(Player).order_by(Player.id)).all()
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
    players = {p.id: p for p in db.scalars(select(Player)).all()}
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


@router.get("/state")
def state():
    with get_db() as db:
        today = date.today()
        rows = []
        for player in db.scalars(select(Player).order_by(Player.id)).all():
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
        background = db.get(BackgroundSetting, 1)
        projects = db.scalars(select(Project).order_by(Project.id.desc())).all()
        custom_tabs = db.scalars(select(CustomTab).order_by(CustomTab.id)).all()
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


@router.patch("/players/{player_id}")
def update_player(player_id: int, payload: PlayerUpdate):
    with get_db() as db:
        player = db.get(Player, player_id)
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
        player = db.get(Player, player_id)
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


@router.post("/background")
def update_background(payload: BackgroundUpdate):
    with get_db() as db:
        bg = db.get(BackgroundSetting, 1)
        if bg is None:
            bg = BackgroundSetting(id=1)
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
        bg = db.get(BackgroundSetting, 1) or BackgroundSetting(id=1)
        db.add(bg)
        bg.background_type = "image"
        bg.background_value = f"/uploads/{filename}"
        safe_commit(db)
    return {"ok": True, "background_value": f"/uploads/{filename}"}


@router.get("/education")
def education_data():
    with get_db() as db:
        players = db.scalars(select(Player).order_by(Player.id)).all()
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
        if not db.get(Player, payload.player_id):
            raise HTTPException(404, "Player not found.")
        entry = StudyEntry(player_id=payload.player_id, subject=payload.subject.strip(), notes=payload.notes.strip(), minutes=0)
        db.add(entry)
        safe_commit(db)
        return {"ok": True, "entry_id": entry.id}


@router.put("/education/today")
def update_study_minutes(payload: StudyMinutesUpdate):
    with get_db() as db:
        if not db.get(Player, payload.player_id):
            raise HTTPException(404, "Player not found.")
        stats = get_daily_stats(db, payload.player_id)
        delta = payload.minutes - stats.study_minutes
        stats.study_minutes = payload.minutes
        if delta > 0:
            add_points(db, payload.player_id, "study_adjustment", delta, delta)
        safe_commit(db)
        return {"ok": True, "today_minutes": stats.study_minutes}


@router.get("/fitness")
def fitness_data():
    with get_db() as db:
        result = []
        for p in db.scalars(select(Player).order_by(Player.id)).all():
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
        if not db.get(Player, payload.player_id):
            raise HTTPException(404, "Player not found.")
        log = ActivityLog(player_id=payload.player_id, activity=payload.activity.strip(), duration_minutes=payload.duration_minutes)
        db.add(log)
        stats = get_daily_stats(db, payload.player_id)
        stats.workout_minutes += payload.duration_minutes
        add_points(db, payload.player_id, "workout", payload.duration_minutes, payload.duration_minutes, "activity", log.id)
        safe_commit(db)
        return {"ok": True, "entry_id": log.id}


@router.get("/projects")
def project_list():
    with get_db() as db:
        return {"projects": [project_payload(db, p) for p in db.scalars(select(Project).order_by(Project.id.desc()).all())]}


@router.post("/projects")
def create_project(payload: ProjectCreate):
    with get_db() as db:
        if payload.owner_id is not None and not db.get(Player, payload.owner_id):
            raise HTTPException(400, "Project owner does not exist.")
        project = Project(name=payload.name.strip(), icon=payload.icon.strip(), aim=payload.aim.strip(), owner_id=payload.owner_id)
        db.add(project)
        safe_commit(db)
        return {"ok": True, "project": project_payload(db, project)}


@router.get("/projects/{project_id}")
def get_project(project_id: int):
    with get_db() as db:
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(404, "Project not found.")
        return project_payload(db, project)


@router.post("/projects/{project_id}/tasks")
def create_task(project_id: int, payload: TaskCreate):
    with get_db() as db:
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(404, "Project not found.")
        if payload.assignee_id is not None and not db.get(Player, payload.assignee_id):
            raise HTTPException(400, "Assignee does not exist.")
        task = ProjectTask(project_id=project_id, title=payload.title.strip(), assignee_id=payload.assignee_id)
        db.add(task)
        safe_commit(db)
        return {"ok": True, "task": {"id": task.id, "title": task.title, "completed": task.completed, "assignee_id": task.assignee_id}}


@router.patch("/projects/tasks/{task_id}")
def toggle_task(task_id: int, payload: TaskToggle):
    with get_db() as db:
        task = db.get(ProjectTask, task_id)
        if not task:
            raise HTTPException(404, "Task not found.")
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
        if not db.get(Project, project_id) or not db.get(Player, payload.player_id):
            raise HTTPException(404, "Project or player not found.")
        note = ProjectNote(project_id=project_id, player_id=payload.player_id, note=payload.note.strip())
        db.add(note)
        safe_commit(db)
        return {"ok": True, "note_id": note.id}


@router.post("/custom-tabs")
def create_custom_tab(payload: CustomTabCreate):
    with get_db() as db:
        if payload.created_by is not None and not db.get(Player, payload.created_by):
            raise HTTPException(400, "Creator does not exist.")
        tab = CustomTab(name=payload.name.strip(), icon=payload.icon.strip(), tracking_type=payload.tracking_type, created_by=payload.created_by)
        db.add(tab)
        safe_commit(db)
        return {"ok": True, "tab": {"id": tab.id, "name": tab.name, "icon": tab.icon, "tracking_type": tab.tracking_type}}


@router.get("/custom-tabs/{tab_id}")
def custom_tab_data(tab_id: int):
    with get_db() as db:
        tab = db.get(CustomTab, tab_id)
        if not tab:
            raise HTTPException(404, "Custom tab not found.")
        result = []
        for p in db.scalars(select(Player).order_by(Player.id)).all():
            entries = db.scalars(select(CustomTabEntry).where(CustomTabEntry.tab_id == tab_id, CustomTabEntry.player_id == p.id).order_by(CustomTabEntry.created_at.desc()).limit(30)).all()
            result.append({"player_id": p.id, "name": p.name, "entries": [{"id": e.id, "day": e.day.isoformat(), "label": e.label, "value": e.value, "note": e.note} for e in entries]})
        return {"tab": {"id": tab.id, "name": tab.name, "icon": tab.icon, "tracking_type": tab.tracking_type}, "players": result}


@router.post("/custom-tabs/{tab_id}/entries")
def add_custom_entry(tab_id: int, payload: CustomEntryCreate):
    with get_db() as db:
        if not db.get(CustomTab, tab_id) or not db.get(Player, payload.player_id):
            raise HTTPException(404, "Custom tab or player not found.")
        entry = CustomTabEntry(tab_id=tab_id, player_id=payload.player_id, label=payload.label.strip(), value=payload.value, note=payload.note.strip())
        db.add(entry)
        safe_commit(db)
        return {"ok": True, "entry_id": entry.id}


@router.get("/leaderboard")
def leaderboard_data():
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    with get_db() as db:
        result = []
        for p in db.scalars(select(Player).order_by(Player.id)).all():
            result.append({
                "id": p.id,
                "name": p.name,
                "emoji": p.emoji,
                "all_time": total_points(db, p.id),
                "weekly": total_points(db, p.id, week_start, today),
                "today": total_points(db, p.id, today, today),
                "streak": streak_days(db, p.id),
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
        player_rows = db.scalars(select(Player).order_by(Player.id)).all()
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
        players = db.scalars(select(Player)).all()
        nodes: list[dict] = []
        edges: list[dict] = []
        for p in players:
            user_color = "#5867ff" if p.id == players[0].id else "#ed4db6"
            nodes.append({"id": f"p{p.id}", "label": p.name, "group": "player", "title": "Player", "user_color": user_color})
        for project in db.scalars(select(Project)).all():
            pid = f"project-{project.id}"
            nodes.append({"id": pid, "label": project.name, "group": "project", "title": project.aim})
            if project.owner_id:
                edges.append({"from": f"p{project.owner_id}", "to": pid, "label": "owns"})
            for task in project.tasks:
                tid = f"task-{task.id}"
                task_color = next(("#5867ff" if p.id == task.assignee_id else "#ed4db6" for p in players if p.id == task.assignee_id), "#13c8aa")
                nodes.append({"id": tid, "label": task.title, "group": "task", "title": "Task", "user_color": task_color})
                edges.append({"from": pid, "to": tid, "label": "mission"})
                if task.assignee_id:
                    edges.append({"from": f"p{task.assignee_id}", "to": tid, "label": "assigned"})
        subjects = db.scalars(select(StudyEntry.subject).distinct()).all()
        for index, subject in enumerate(subjects, 1):
            sid = f"subject-{index}"
            nodes.append({"id": sid, "label": str(subject), "group": "subject", "title": "Study subject"})
            for entry in db.scalars(select(StudyEntry).where(StudyEntry.subject == subject).limit(3)).all():
                edges.append({"from": f"p{entry.player_id}", "to": sid, "label": "studies"})
        activities = db.scalars(select(ActivityLog.activity).distinct()).all()
        for index, activity in enumerate(activities, 1):
            aid = f"activity-{index}"
            nodes.append({"id": aid, "label": str(activity), "group": "activity", "title": "Physical activity"})
            for entry in db.scalars(select(ActivityLog).where(ActivityLog.activity == activity).limit(3)).all():
                edges.append({"from": f"p{entry.player_id}", "to": aid, "label": "does"})
        return {"nodes": nodes, "edges": edges}


@router.get("/rivalry")
def rivalry_data(ai: bool = True):
    with get_db() as db:
        players = db.scalars(select(Player).order_by(Player.id)).all()
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
        players = db.scalars(select(Player).order_by(Player.id)).all()
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


@router.get("/settings/ai")
def ai_settings():
    with get_db() as db:
        rows = db.scalars(select(AIKeySlot).order_by(AIKeySlot.slot)).all()
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


@router.get("/export.csv")
def export_csv():
    with get_db() as db:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["type", "player", "date", "label", "value", "notes"])
        players = {p.id: p.name for p in db.scalars(select(Player)).all()}
        for row in db.scalars(select(StudyEntry).order_by(StudyEntry.day)).all():
            writer.writerow(["study", players.get(row.player_id, ""), row.day, row.subject, row.minutes, row.notes])
        for row in db.scalars(select(ActivityLog).order_by(ActivityLog.day)).all():
            writer.writerow(["activity", players.get(row.player_id, ""), row.day, row.activity, row.duration_minutes, ""])
        for row in db.scalars(select(ProjectTask).order_by(ProjectTask.id)).all():
            writer.writerow(["project_task", players.get(row.assignee_id, ""), row.completed_at.date() if row.completed_at else "", row.title, int(row.completed), ""])
        output.seek(0)
        headers = {"Content-Disposition": 'attachment; filename="duo_tracker_export.csv"'}
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
