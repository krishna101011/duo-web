"""Tenant helpers for the logged-in user's two-person tracker."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_tracker_id, current_user_id
from ..models import Player, Tracker, User


def require_tracker(db: Session) -> Tracker:
    tracker_id = current_tracker_id()
    if tracker_id is None:
        raise HTTPException(401, "Please log in first.")
    tracker = db.get(Tracker, tracker_id)
    if tracker is None:
        raise HTTPException(401, "Your tracker session is no longer valid. Please log in again.")
    return tracker


def require_user(db: Session) -> User:
    user_id = current_user_id()
    if user_id is None:
        raise HTTPException(401, "Please log in first.")
    user = db.get(User, user_id)
    if user is None or user.tracker_id != current_tracker_id():
        raise HTTPException(401, "Your login session is no longer valid. Please log in again.")
    return user


def require_player(db: Session, player_id: int) -> Player:
    tracker_id = current_tracker_id()
    player = db.scalar(select(Player).where(Player.id == player_id, Player.tracker_id == tracker_id))
    if player is None:
        raise HTTPException(404, "Player not found in this tracker.")
    return player
