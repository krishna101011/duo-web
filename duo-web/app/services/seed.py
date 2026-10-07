"""Idempotent demo data for a first-run experience."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    AIKeySlot,
    Tracker,
    ActivityLog,
    BackgroundSetting,
    DailyStats,
    Player,
    Project,
    ProjectNote,
    ProjectTask,
    StudyEntry,
)
from .scoring import STUDY_POINTS_PER_MINUTE, TASK_POINTS, WORKOUT_POINTS_PER_MINUTE, add_points
from .security import encrypt_secret


def seed_demo(db: Session) -> None:
    existing_tracker = db.scalar(select(Tracker.id).limit(1))
    if db.scalar(select(Player.id).limit(1)):
        tracker = db.query(Tracker).order_by(Tracker.id).first()
        if tracker:
            _ensure_ai_rows(db, tracker.id)
        return

    tracker = db.get(Tracker, existing_tracker) if existing_tracker else None
    if tracker is None:
        from ..services.tracker import generate_tracker_code
        tracker = Tracker(code=generate_tracker_code(db), name="Demo Duo")
        db.add(tracker)
        db.flush()

    alex = Player(tracker_id=tracker_id, name="Alex", emoji="🧠", accent="accent")
    sam = Player(tracker_id=tracker_id, name="Sam", emoji="⚡", accent="hot")
    db.add_all([alex, sam])
    db.flush()

    db.add(BackgroundSetting(tracker_id=tracker_id, theme="glass", background_type="gradient", background_value="aurora"))

    study_samples = [
        (alex, 4, "Economics", "Microeconomics notes", 75),
        (alex, 2, "Python", "List comprehensions", 55),
        (alex, 1, "Finance", "Portfolio chapter", 80),
        (sam, 4, "Economics", "Inflation revision", 60),
        (sam, 2, "English", "Speaking practice", 45),
        (sam, 0, "Finance", "Ratio analysis", 70),
    ]
    for player, days_ago, subject, notes, minutes in study_samples:
        day = date.today() - timedelta(days=days_ago)
        db.add(StudyEntry(player_id=player.id, day=day, subject=subject, notes=notes, minutes=minutes))
        stats = _stats(db, player.id, day)
        stats.study_minutes += minutes
        add_points(db, player.id, "study", minutes * STUDY_POINTS_PER_MINUTE, minutes)

    for player, minutes in ((alex, 220), (sam, 175)):
        stats = _stats(db, player.id, date.today())
        stats.study_minutes = minutes
        add_points(db, player.id, "study", minutes, minutes)

    activity_samples = [
        (alex, 4, "Swimming", 40),
        (alex, 2, "Mobility", 25),
        (alex, 0, "Strength", 52),
        (sam, 4, "Walking", 30),
        (sam, 1, "Swimming", 35),
        (sam, 0, "Cycling", 41),
    ]
    for player, days_ago, activity, minutes in activity_samples:
        day = date.today() - timedelta(days=days_ago)
        db.add(ActivityLog(player_id=player.id, day=day, activity=activity, duration_minutes=minutes))
        stats = _stats(db, player.id, day)
        stats.workout_minutes += minutes
        add_points(db, player.id, "workout", minutes * WORKOUT_POINTS_PER_MINUTE, minutes)

    p1 = Project(tracker_id=tracker_id, name="Duo Tracker MVP", icon="🖥️", aim="Build a polished two-person self-improvement command center.", owner_id=alex.id)
    p2 = Project(tracker_id=tracker_id, name="Debate Channel · E20", icon="🎬", aim="Research, storyboard, record, and publish the E20 debate.", owner_id=sam.id)
    p3 = Project(tracker_id=tracker_id, name="Finance Learning Sprint", icon="📈", aim="Turn the reading backlog into a repeatable weekly learning sprint.", owner_id=alex.id)
    db.add_all([p1, p2, p3])
    db.flush()

    tasks = [
        (p1, "Finish mobile layout", alex, True),
        (p1, "Wire project detail page", alex, True),
        (p1, "Add graph view", sam, True),
        (p1, "Connect AI settings", alex, False),
        (p1, "Polish empty states", sam, False),
        (p1, "Test CSV export", sam, True),
        (p2, "Research E20 fuel policy", sam, True),
        (p2, "Draft debate outline", sam, True),
        (p2, "Collect counterarguments", alex, False),
        (p2, "Storyboard visual beats", sam, False),
        (p3, "Finish current chapter", alex, True),
        (p3, "Review accounting terms", alex, False),
        (p3, "Create quant mini-sheet", sam, False),
        (p3, "Write weekly recap", alex, False),
    ]
    for project, title, assignee, completed in tasks:
        task = ProjectTask(
            project_id=project.id,
            title=title,
            assignee_id=assignee.id,
            completed=completed,
            completed_at=datetime.now(timezone.utc) if completed else None,
        )
        db.add(task)
        db.flush()
        if completed:
            add_points(db, assignee.id, "task", TASK_POINTS, 1, "project_task", task.id)

    db.add_all([
        ProjectNote(project_id=p1.id, player_id=alex.id, note="Soft Glass theme looks clean. Next: finish key storage UI."),
        ProjectNote(project_id=p1.id, player_id=sam.id, note="Graph needs clearer relationship labels on mobile."),
        ProjectNote(project_id=p2.id, player_id=sam.id, note="The strongest debate frame is fuel economics vs emissions trade-offs."),
    ])

    _ensure_ai_rows(db, tracker.id)


def _stats(db: Session, player_id: int, day: date) -> DailyStats:
    row = db.scalar(select(DailyStats).where(DailyStats.player_id == player_id, DailyStats.day == day))
    if row is None:
        row = DailyStats(player_id=player_id, day=day)
        db.add(row)
        db.flush()
    return row


def _ensure_ai_rows(db: Session, tracker_id: int) -> None:
    for slot in range(1, 4):
        row = db.scalar(select(AIKeySlot).where(AIKeySlot.tracker_id == tracker_id, AIKeySlot.slot == slot))
        if row is None:
            row = AIKeySlot(
                tracker_id=tracker_id,
                slot=slot,
                provider=settings.AI_DEFAULT_PROVIDER,
                base_url=settings.AI_DEFAULT_BASE_URL,
                model=settings.AI_DEFAULT_MODEL,
                enabled=False,
            )
            if slot == 1 and settings.AI_DEFAULT_KEY:
                row.encrypted_key = encrypt_secret(settings.AI_DEFAULT_KEY)
                row.enabled = True
            db.add(row)
