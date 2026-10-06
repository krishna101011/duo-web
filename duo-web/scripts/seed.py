"""Reset the local database and seed Duo Tracker demo data."""
from __future__ import annotations

from pathlib import Path

from app.db import SessionLocal, init_db
from app.services.seed import seed_demo


if __name__ == "__main__":
    # This script is intentionally simple for beginners: delete the local DB,
    # recreate tables, then seed the same data used by application startup.
    db_path = Path("duo_tracker.db")
    if db_path.exists():
        db_path.unlink()
    init_db()
    with SessionLocal() as db:
        seed_demo(db)
        db.commit()
    print("Duo Tracker demo database reset and seeded.")
