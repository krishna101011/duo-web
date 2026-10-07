"""Tracker creation and membership helpers."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import CODE_ALPHABET, CODE_LENGTH, generate_code
from ..config import settings
from ..models import AIKeySlot, BackgroundSetting, Player, Tracker, User


def generate_tracker_code(db: Session) -> str:
    return generate_code(db, Tracker, "code")


def tracker_player_count(db: Session, tracker_id: int) -> int:
    return int(db.scalar(select(func.count(Player.id)).where(Player.tracker_id == tracker_id)) or 0)


def create_tracker_for_user(
    db: Session,
    *,
    name: str,
    email: str,
    password_hash: str,
    display_name: str,
    player_emoji: str = "🙂",
) -> User:
    tracker = Tracker(code=generate_tracker_code(db), name=f"{display_name}'s Duo")
    db.add(tracker)
    db.flush()

    player = Player(tracker_id=tracker.id, name=name, emoji=player_emoji, accent="accent")
    db.add(player)
    db.flush()

    user = User(
        email=email,
        password_hash=password_hash,
        display_name=display_name,
        invite_code=_legacy_user_code(db),
        tracker_id=tracker.id,
        player_id=player.id,
    )
    db.add(user)
    db.flush()

    provision_tracker_settings(db, tracker.id)
    return user


def _legacy_user_code(db: Session) -> str:
    """Keep the old per-user code column valid while the tracker code is canonical."""
    # Use the existing generic generator without exposing it as the sharing code.
    alphabet = CODE_ALPHABET
    import secrets
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(CODE_LENGTH))
        if db.scalar(select(User.id).where(User.invite_code == code)) is None:
            return code


def provision_tracker_settings(db: Session, tracker_id: int) -> None:
    bg = db.scalar(select(BackgroundSetting).where(BackgroundSetting.tracker_id == tracker_id))
    if bg is None:
        db.add(BackgroundSetting(tracker_id=tracker_id, theme="glass", background_type="gradient", background_value="aurora"))

    from ..config import settings
    from ..services.security import encrypt_secret

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
