"""Points and streak calculations."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import DailyStats, PointsEvent, ProjectTask


STUDY_POINTS_PER_MINUTE = 1
WORKOUT_POINTS_PER_MINUTE = 1
TASK_POINTS = 25
STREAK_DAY_BONUS = 5


def get_daily_stats(db: Session, player_id: int, day: date | None = None) -> DailyStats:
    day = day or date.today()
    stats = db.scalar(select(DailyStats).where(DailyStats.player_id == player_id, DailyStats.day == day))
    if stats is None:
        stats = DailyStats(player_id=player_id, day=day)
        db.add(stats)
        db.flush()
    return stats


def add_points(db: Session, player_id: int, kind: str, points: int, amount: float = 0,
               reference_type: str | None = None, reference_id: int | None = None) -> None:
    db.add(PointsEvent(
        player_id=player_id,
        kind=kind,
        points=points,
        amount=amount,
        reference_type=reference_type,
        reference_id=reference_id,
    ))


def event_points(db: Session, player_id: int, start: date | None = None, end: date | None = None) -> int:
    stmt = select(func.coalesce(func.sum(PointsEvent.points), 0)).where(PointsEvent.player_id == player_id)
    if start:
        stmt = stmt.where(func.date(PointsEvent.created_at) >= start.isoformat())
    if end:
        stmt = stmt.where(func.date(PointsEvent.created_at) <= end.isoformat())
    return int(db.scalar(stmt) or 0)


def streak_days(db: Session, player_id: int, reference_day: date | None = None) -> int:
    """Count consecutive recent days with positive points events."""
    day = reference_day or date.today()
    count = 0
    while True:
        points = db.scalar(
            select(func.coalesce(func.sum(PointsEvent.points), 0)).where(
                PointsEvent.player_id == player_id,
                func.date(PointsEvent.created_at) == day.isoformat(),
            )
        )
        if int(points or 0) <= 0:
            break
        count += 1
        day -= timedelta(days=1)
        if count > 365:
            break
    return count


def streak_bonus(db: Session, player_id: int, reference_day: date | None = None) -> int:
    return max(streak_days(db, player_id, reference_day) - 1, 0) * STREAK_DAY_BONUS


def total_points(db: Session, player_id: int, start: date | None = None, end: date | None = None) -> int:
    base = event_points(db, player_id, start, end)
    # Streak bonus is shown as a lightweight derived score instead of creating
    # duplicate events every day.
    return base + streak_bonus(db, player_id) if start is None and end is None else base


def project_progress(project: ProjectTask | object) -> int:
    """Compatibility helper; actual project progress is calculated in routes."""
    return 0
