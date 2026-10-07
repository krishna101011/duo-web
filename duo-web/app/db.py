"""SQLAlchemy setup and helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _clean_database_url(url: str) -> str:
    """Make a copy-pasted Postgres address (e.g. from Neon) work as-is."""
    url = url.strip().strip("'\"")
    if url.startswith("psql "):
        url = url[5:].strip().strip("'\"")
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg2://" + url[len(prefix):]
    return url.replace("&channel_binding=require", "").replace("?channel_binding=require&", "?")


DATABASE_URL = _clean_database_url(settings.DATABASE_URL)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith(
    "sqlite") else {}
engine = create_engine(
    DATABASE_URL, connect_args=connect_args, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    """Create all database tables."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional session for service-layer code."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
