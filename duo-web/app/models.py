"""Database models for Duo Tracker."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tracker(Base):
    """A private two-person workspace. Every Duo belongs to exactly one tracker."""

    __tablename__ = "trackers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="My Duo Tracker")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    users = relationship("User", back_populates="tracker")
    players = relationship("Player", back_populates="tracker", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="tracker", cascade="all, delete-orphan")
    custom_tabs = relationship("CustomTab", back_populates="tracker", cascade="all, delete-orphan")
    background = relationship("BackgroundSetting", back_populates="tracker", uselist=False, cascade="all, delete-orphan")
    ai_slots = relationship("AIKeySlot", back_populates="tracker", cascade="all, delete-orphan")


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracker_id: Mapped[int | None] = mapped_column(ForeignKey("trackers.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, default="Player")
    avatar_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emoji: Mapped[str] = mapped_column(String(8), nullable=False, default="🙂")
    accent: Mapped[str] = mapped_column(String(20), nullable=False, default="accent")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    tracker = relationship("Tracker", back_populates="players")
    study_entries = relationship("StudyEntry", back_populates="player", cascade="all, delete-orphan")
    activities = relationship("ActivityLog", back_populates="player", cascade="all, delete-orphan")
    project_tasks = relationship("ProjectTask", back_populates="assignee")
    project_notes = relationship("ProjectNote", back_populates="player", cascade="all, delete-orphan")
    custom_entries = relationship("CustomTabEntry", back_populates="player", cascade="all, delete-orphan")
    points_events = relationship("PointsEvent", back_populates="player", cascade="all, delete-orphan")


class DailyStats(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (UniqueConstraint("player_id", "day", name="uq_daily_stats_player_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    study_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    workout_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StudyEntry(Base):
    __tablename__ = "study_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    player = relationship("Player", back_populates="study_entries")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    activity: Mapped[str] = mapped_column(String(120), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    player = relationship("Player", back_populates="activities")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracker_id: Mapped[int | None] = mapped_column(ForeignKey("trackers.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    icon: Mapped[str] = mapped_column(String(8), nullable=False, default="🧪")
    aim: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    tracker = relationship("Tracker", back_populates="projects")
    tasks = relationship("ProjectTask", back_populates="project", cascade="all, delete-orphan")
    notes = relationship("ProjectNote", back_populates="project", cascade="all, delete-orphan")


class ProjectTask(Base):
    __tablename__ = "project_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="tasks")
    assignee = relationship("Player", back_populates="project_tasks")


class ProjectNote(Base):
    __tablename__ = "project_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    project = relationship("Project", back_populates="notes")
    player = relationship("Player", back_populates="project_notes")


class CustomTab(Base):
    __tablename__ = "custom_tabs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracker_id: Mapped[int | None] = mapped_column(ForeignKey("trackers.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str] = mapped_column(String(8), nullable=False, default="✦")
    tracking_type: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    tracker = relationship("Tracker", back_populates="custom_tabs")
    entries = relationship("CustomTabEntry", back_populates="tab", cascade="all, delete-orphan")


class CustomTabEntry(Base):
    __tablename__ = "custom_tab_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tab_id: Mapped[int] = mapped_column(ForeignKey("custom_tabs.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    label: Mapped[str] = mapped_column(String(160), nullable=False, default="Entry")
    value: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    tab = relationship("CustomTab", back_populates="entries")
    player = relationship("Player", back_populates="custom_entries")


class PointsEvent(Base):
    __tablename__ = "points_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    reference_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    player = relationship("Player", back_populates="points_events")


class BackgroundSetting(Base):
    __tablename__ = "background_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tracker_id: Mapped[int | None] = mapped_column(ForeignKey("trackers.id"), nullable=True, unique=True)
    theme: Mapped[str] = mapped_column(String(20), nullable=False, default="glass")
    background_type: Mapped[str] = mapped_column(String(20), nullable=False, default="gradient")
    background_value: Mapped[str] = mapped_column(Text, nullable=False, default="aurora")

    tracker = relationship("Tracker", back_populates="background")


class AIKeySlot(Base):
    __tablename__ = "ai_key_slots"
    __table_args__ = (UniqueConstraint("tracker_id", "slot", name="uq_ai_tracker_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracker_id: Mapped[int | None] = mapped_column(ForeignKey("trackers.id"), nullable=True, index=True)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="OpenAI")
    base_url: Mapped[str] = mapped_column(String(255), nullable=False, default="https://api.openai.com/v1")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="gpt-5-mini")
    encrypted_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_status: Mapped[str] = mapped_column(String(30), nullable=False, default="untested")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    tracker = relationship("Tracker", back_populates="ai_slots")


class User(Base):
    """A login account. Each user belongs to one tracker and one player slot."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Kept for backward compatibility with the old schema. Tracker sharing now uses Tracker.code.
    invite_code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    tracker_id: Mapped[int | None] = mapped_column(ForeignKey("trackers.id"), nullable=True, index=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    tracker = relationship("Tracker", back_populates="users")
