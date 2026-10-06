"""Duo Tracker FastAPI entry point."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import SessionLocal, init_db
from .routers import api, pages
from .services.seed import seed_demo

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO), format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

app = FastAPI(title="Duo Tracker", version="1.0.0", docs_url="/docs", redoc_url="/redoc")
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
app.include_router(pages.router)
app.include_router(api.router)


@app.get("/favicon.ico", include_in_schema=False)
def favicon_root():
    return RedirectResponse(url="/static/favicon.svg", status_code=301)


@app.on_event("startup")
def startup() -> None:
    init_db()
    with SessionLocal() as db:
        seed_demo(db)
        db.commit()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logging.getLogger(__name__).exception("Unhandled application error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Duo Tracker hit an unexpected error. Check the terminal for details."})
