"""Pydantic request models used by API routes."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PlayerUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    emoji: str | None = Field(default=None, max_length=8)


class StudyCreate(BaseModel):
    player_id: int
    subject: str = Field(min_length=1, max_length=120)
    notes: str = Field(default="", max_length=4000)


class StudyMinutesUpdate(BaseModel):
    player_id: int
    minutes: int = Field(ge=0, le=1440)


class ActivityCreate(BaseModel):
    player_id: int
    activity: str = Field(min_length=1, max_length=120)
    duration_minutes: int = Field(ge=1, le=1440)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    icon: str = Field(default="🧪", max_length=8)
    aim: str = Field(default="", max_length=4000)
    owner_id: int | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    assignee_id: int | None = None


class TaskToggle(BaseModel):
    completed: bool


class ProjectNoteCreate(BaseModel):
    player_id: int
    note: str = Field(min_length=1, max_length=4000)


class CustomTabCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    icon: str = Field(default="✦", max_length=8)
    tracking_type: Literal["time log", "checklist", "notes", "numeric counter"]
    created_by: int | None = None


class CustomTabUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    icon: str | None = Field(default=None, max_length=8)


class CustomEntryCreate(BaseModel):
    player_id: int
    label: str = Field(default="Entry", max_length=160)
    value: float = Field(default=0)
    note: str = Field(default="", max_length=4000)


class BackgroundUpdate(BaseModel):
    theme: Literal["glass", "dark"] = "glass"
    background_type: Literal["gradient", "solid", "image"] = "gradient"
    background_value: str = Field(default="aurora", max_length=2000)


class AIKeyUpdate(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    base_url: str = Field(min_length=1, max_length=255)
    model: str = Field(min_length=1, max_length=120)
    key: str | None = Field(default=None, max_length=1000)
    enabled: bool = True


class ConfirmReset(BaseModel):
    """Requires the user to type RESET to confirm a destructive operation."""
    confirmation: str = Field(min_length=1, max_length=20)
