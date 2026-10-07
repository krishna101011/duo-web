"""Password, signed session cookies, invite/tracker codes, and request context."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from contextvars import ContextVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings

SESSION_COOKIE = "duo_session"
SESSION_SECONDS = 60 * 60 * 24 * 30
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6

_current_user_id: ContextVar[int | None] = ContextVar("duo_current_user_id", default=None)
_current_tracker_id: ContextVar[int | None] = ContextVar("duo_current_tracker_id", default=None)


def set_request_context(user_id: int, tracker_id: int):
    return (_current_user_id.set(user_id), _current_tracker_id.set(tracker_id))


def reset_request_context(tokens) -> None:
    user_token, tracker_token = tokens
    _current_user_id.reset(user_token)
    _current_tracker_id.reset(tracker_token)


def current_user_id() -> int | None:
    return _current_user_id.get()


def current_tracker_id() -> int | None:
    return _current_tracker_id.get()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def _sign(payload: str) -> str:
    return hmac.new(settings.APP_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_session_token(user_id: int) -> str:
    payload = f"{user_id}.{int(time.time()) + SESSION_SECONDS}"
    return f"{payload}.{_sign(payload)}"


def read_session_token(token: str | None) -> int | None:
    if not token:
        return None
    try:
        user_id, expires, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(f"{user_id}.{expires}")):
            return None
        if int(expires) < time.time():
            return None
        return int(user_id)
    except Exception:
        return None


def generate_code(db: Session, model, field_name: str = "code") -> str:
    """Generate a readable random code unique in the supplied table/field."""
    field = getattr(model, field_name)
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if db.scalar(select(model.id).where(field == code)) is None:
            return code


def generate_invite_code(db: Session) -> str:
    """Backward-compatible personal code generator."""
    from .models import User
    return generate_code(db, User, "invite_code")
