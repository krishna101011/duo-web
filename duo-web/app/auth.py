"""Login helpers: password hashing, signed session cookies and invite codes.

Uses only the Python standard library, so no new packages are needed.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings

SESSION_COOKIE = "duo_session"
SESSION_SECONDS = 60 * 60 * 24 * 30  # stay logged in for 30 days
# No 0/O or 1/I/L so codes are easy to read out loud.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


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
    """Return the user id inside a valid, unexpired token, otherwise None."""
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


def generate_invite_code(db: Session) -> str:
    """Make a random 6-character code that no other user has."""
    from .models import User

    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if db.scalar(select(User.id).where(User.invite_code == code)) is None:
            return code
