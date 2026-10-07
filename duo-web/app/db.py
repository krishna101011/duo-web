"""SQLAlchemy setup, tenant filtering, and backward-compatible migrations."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, with_loader_criteria

from .auth import current_tracker_id
from .config import settings


class Base(DeclarativeBase):
    pass


def _clean_database_url(url: str) -> str:
    url = url.strip().strip("'\"")
    if url.startswith("psql "):
        url = url[5:].strip().strip("'\"")
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg2://" + url[len(prefix):]
    return url.replace("&channel_binding=require", "").replace("?channel_binding=require&", "?")


DATABASE_URL = _clean_database_url(settings.DATABASE_URL)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@event.listens_for(Session, "do_orm_execute")
def _apply_tracker_scope(execute_state):
    """Automatically scope tenant-owned ORM models to the logged-in tracker."""
    if not execute_state.is_select:
        return
    tracker_id = current_tracker_id()
    if tracker_id is None:
        return

    from .models import AIKeySlot, BackgroundSetting, CustomTab, Player, Project

    statement = execute_state.statement
    for model in (Player, Project, CustomTab, BackgroundSetting, AIKeySlot):
        statement = statement.options(
            with_loader_criteria(
                model,
                lambda cls: cls.tracker_id == tracker_id,
                include_aliases=True,
            )
        )
    execute_state.statement = statement


def _column_names(connection, table_name: str) -> set[str]:
    return {col["name"] for col in inspect(connection).get_columns(table_name)}


def _add_column_if_missing(connection, table_name: str, column_sql: str, column_name: str) -> None:
    if column_name not in _column_names(connection, table_name):
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))


def _rebuild_sqlite_ai_table(connection) -> None:
    """Convert old global UNIQUE(slot) AI rows to UNIQUE(tracker_id, slot)."""
    inspector = inspect(connection)
    columns = _column_names(connection, "ai_key_slots")
    if "tracker_id" in columns:
        return

    connection.execute(text("PRAGMA foreign_keys=OFF"))
    connection.execute(text("""
        CREATE TABLE ai_key_slots_new (
            id INTEGER NOT NULL PRIMARY KEY,
            tracker_id INTEGER,
            slot INTEGER NOT NULL,
            provider VARCHAR(50) NOT NULL,
            base_url VARCHAR(255) NOT NULL,
            model VARCHAR(120) NOT NULL,
            encrypted_key TEXT,
            enabled BOOLEAN NOT NULL,
            last_status VARCHAR(30) NOT NULL,
            last_error TEXT,
            updated_at DATETIME,
            CONSTRAINT uq_ai_tracker_slot UNIQUE (tracker_id, slot),
            FOREIGN KEY(tracker_id) REFERENCES trackers (id)
        )
    """))
    connection.execute(text("""
        INSERT INTO ai_key_slots_new
        (id, tracker_id, slot, provider, base_url, model, encrypted_key, enabled, last_status, last_error, updated_at)
        SELECT id, NULL, slot, provider, base_url, model, encrypted_key, enabled, last_status, last_error, updated_at
        FROM ai_key_slots
    """))
    connection.execute(text("DROP TABLE ai_key_slots"))
    connection.execute(text("ALTER TABLE ai_key_slots_new RENAME TO ai_key_slots"))
    connection.execute(text("CREATE INDEX ix_ai_key_slots_tracker_id ON ai_key_slots (tracker_id)"))
    connection.execute(text("PRAGMA foreign_keys=ON"))


def _postgres_ai_constraints(connection) -> None:
    """Drop old UNIQUE(slot) before creating the new composite unique constraint."""
    inspector = inspect(connection)
    existing = inspector.get_unique_constraints("ai_key_slots")
    for item in existing:
        cols = item.get("column_names") or []
        if cols == ["slot"]:
            name = item.get("name")
            if name:
                connection.execute(text(f'ALTER TABLE ai_key_slots DROP CONSTRAINT IF EXISTS "{name}"'))
    # A named composite constraint is represented by the new SQLAlchemy model on fresh DBs.
    connection.execute(text(
        "ALTER TABLE ai_key_slots ADD CONSTRAINT uq_ai_tracker_slot UNIQUE (tracker_id, slot)"
    ))


def _seed_legacy_tracker(db: Session) -> None:
    """Attach an existing pre-multitracker database to one tracker without deleting data."""
    from .auth import CODE_ALPHABET, CODE_LENGTH
    from .models import AIKeySlot, BackgroundSetting, CustomTab, Player, Project, Tracker, User
    import secrets

    tracker = db.query(Tracker).order_by(Tracker.id).first()
    if tracker is None:
        # Reuse the first account's old personal code when possible, so existing
        # installs can keep a familiar code. Fall back to a new code.
        old_user = db.query(User).order_by(User.id).first()
        preferred = old_user.invite_code if old_user else None
        code = preferred
        if not code or db.scalar(text("SELECT id FROM trackers WHERE code = :code"), {"code": code}) is not None:
            while True:
                code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
                if db.query(Tracker).filter(Tracker.code == code).first() is None:
                    break
        tracker = Tracker(code=code, name="My Duo Tracker")
        db.add(tracker)
        db.flush()

    # Backfill old tenant-owned rows.
    db.execute(text("UPDATE players SET tracker_id = :tid WHERE tracker_id IS NULL"), {"tid": tracker.id})
    db.execute(text("UPDATE projects SET tracker_id = :tid WHERE tracker_id IS NULL"), {"tid": tracker.id})
    db.execute(text("UPDATE custom_tabs SET tracker_id = :tid WHERE tracker_id IS NULL"), {"tid": tracker.id})
    db.execute(text("UPDATE users SET tracker_id = :tid WHERE tracker_id IS NULL"), {"tid": tracker.id})
    db.execute(text("UPDATE background_settings SET tracker_id = :tid WHERE tracker_id IS NULL"), {"tid": tracker.id})
    db.execute(text("UPDATE ai_key_slots SET tracker_id = :tid WHERE tracker_id IS NULL"), {"tid": tracker.id})

    # Keep the current two-player layout. Any old orphaned player data belongs
    # to this legacy tracker, so it remains available after upgrading.
    for player in db.query(Player).order_by(Player.id).all():
        if player.tracker_id is None:
            player.tracker_id = tracker.id
    for project in db.query(Project).order_by(Project.id).all():
        if project.tracker_id is None:
            project.tracker_id = tracker.id
    for tab in db.query(CustomTab).order_by(CustomTab.id).all():
        if tab.tracker_id is None:
            tab.tracker_id = tracker.id

    # Ensure there is one background record for the existing tracker.
    bg = db.query(BackgroundSetting).filter(BackgroundSetting.tracker_id == tracker.id).first()
    if bg is None:
        old_bg = db.query(BackgroundSetting).order_by(BackgroundSetting.id).first()
        if old_bg:
            old_bg.tracker_id = tracker.id
        else:
            db.add(BackgroundSetting(tracker_id=tracker.id))

    # Ensure all users point at their player's tracker where possible.
    for user in db.query(User).order_by(User.id).all():
        if user.player_id:
            player = db.get(Player, user.player_id)
            if player and player.tracker_id:
                user.tracker_id = player.tracker_id
        if user.tracker_id is None:
            user.tracker_id = tracker.id

    db.flush()


def init_db() -> None:
    """Create new tables and migrate the previous two-player schema in place."""
    from . import models  # noqa: F401

    # Create brand-new tables first. Existing tables are untouched by create_all.
    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        existing_tables = set(inspect(connection).get_table_names())
        if "users" not in existing_tables:
            return

        # Add the tenant columns needed by existing installs.
        for table, column_sql, column_name in (
            ("users", "tracker_id INTEGER", "tracker_id"),
            ("players", "tracker_id INTEGER", "tracker_id"),
            ("projects", "tracker_id INTEGER", "tracker_id"),
            ("custom_tabs", "tracker_id INTEGER", "tracker_id"),
            ("background_settings", "tracker_id INTEGER", "tracker_id"),
        ):
            _add_column_if_missing(connection, table, column_sql, column_name)

        if "ai_key_slots" in existing_tables:
            if connection.dialect.name == "sqlite":
                _rebuild_sqlite_ai_table(connection)
            else:
                if "tracker_id" not in _column_names(connection, "ai_key_slots"):
                    connection.execute(text("ALTER TABLE ai_key_slots ADD COLUMN tracker_id INTEGER"))
                    try:
                        connection.execute(text("ALTER TABLE ai_key_slots ADD CONSTRAINT fk_ai_tracker FOREIGN KEY (tracker_id) REFERENCES trackers(id)"))
                    except Exception:
                        pass
                    _postgres_ai_constraints(connection)

    # Backfill data using normal ORM operations after DDL is complete.
    with SessionLocal() as db:
        _seed_legacy_tracker(db)
        db.commit()

        # The original database did not have a tenant key on background settings.
        # Keep the one-background-per-tracker invariant after migration as well.
        with engine.begin() as connection:
            if connection.dialect.name == "sqlite":
                connection.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_background_tracker_id ON background_settings(tracker_id)"
                ))
            else:
                connection.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_background_tracker_id ON background_settings(tracker_id)"
                ))

        # A fresh migration may need the relationships to be fully created on
        # engines where CREATE TABLE ordering differs. create_all is idempotent.
        Base.metadata.create_all(bind=engine)
