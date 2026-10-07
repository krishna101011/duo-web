"""Duo Tracker FastAPI entry point."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .auth import SESSION_COOKIE, read_session_token, reset_request_context, set_request_context
from .config import settings
from .db import SessionLocal, init_db
from .models import User
from .routers import api, auth_routes, pages
from .services.seed import seed_demo

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

app = FastAPI(title="Duo Tracker", version="1.1.0", docs_url="/docs", redoc_url="/redoc")
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
app.include_router(auth_routes.router)
app.include_router(pages.router)
app.include_router(api.router)

PUBLIC_PREFIXES = ("/login", "/signup", "/static", "/favicon.ico")


@app.middleware("http")
async def require_login(request, call_next):
    path = request.url.path
    if path.startswith(PUBLIC_PREFIXES):
        return await call_next(request)

    user_id = read_session_token(request.cookies.get(SESSION_COOKIE))
    tracker_id = None
    if user_id is not None:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if user is None or user.tracker_id is None:
                user_id = None
            else:
                tracker_id = user.tracker_id

    if user_id is None or tracker_id is None:
        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"detail": "Please log in first."})
        return RedirectResponse(url="/login", status_code=303)

    tokens = set_request_context(user_id, tracker_id)
    try:
        return await call_next(request)
    finally:
        reset_request_context(tokens)


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
