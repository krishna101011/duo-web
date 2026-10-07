"""HTML page routes with tracker-scoped data and server-rendered background."""
from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_tracker_id
from ..config import settings
from ..db import SessionLocal
from ..models import BackgroundSetting, CustomTab, Player, Project
from ..services.tenant import require_tracker

router = APIRouter()


class SafeJinja2Templates(Jinja2Templates):
    """Render templates directly to HTMLResponse.

    Starlette 1.7.0's internal _TemplateResponse calls .get() on the
    request object stored in the context while handling the response. That
    is incompatible with the Request object that FastAPI/Jinja expects in
    the context. Rendering to a normal HTMLResponse avoids that framework
    regression while preserving Jinja url_for() support.
    """

    def TemplateResponse(
        self,
        request,
        name,
        context=None,
        status_code=200,
        headers=None,
        media_type=None,
        background=None,
    ):
        render_context = dict(context or {})
        render_context.setdefault("request", request)
        template = self.get_template(name)
        response = HTMLResponse(
            template.render(render_context),
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )
        # Keep the attributes that Starlette's TemplateResponse exposes, so
        # existing tests/debugging tools can still inspect the rendered template.
        response.template = template
        response.context = render_context
        return response


templates = SafeJinja2Templates(directory=str(settings.TEMPLATE_DIR))

_GRADIENTS = {
    "glass:aurora": "linear-gradient(125deg,#eef3f8 0%,#dfe7ff 48%,#d8f2ed 100%)",
    "glass:sunset": "linear-gradient(125deg,#f8e7e9 5%,#f2dff2 48%,#fff0d4 100%)",
    "glass:ocean": "linear-gradient(125deg,#e7efff 0%,#d9f3ee 60%,#f0edff 100%)",
    "dark:aurora": "linear-gradient(125deg,#0c1020 10%,#171c37 52%,#0b2928 100%)",
    "dark:sunset": "linear-gradient(125deg,#17101f 5%,#5b223f 48%,#352718 100%)",
    "dark:ocean": "linear-gradient(125deg,#0b1220 0%,#172b52 60%,#202b48 100%)",
}

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$")
_UPLOAD_RE = re.compile(r"^/uploads/[A-Za-z0-9._-]+$")


def background_css(background: BackgroundSetting | None) -> str:
    """Turn stored background settings into a safe inline style for zero-flash loading."""
    if background is None:
        return "background: #eef3f8;"
    theme = background.theme if background.theme in {"glass", "dark"} else "glass"
    value = background.background_value or "aurora"
    kind = background.background_type
    if kind == "image" and _UPLOAD_RE.fullmatch(value):
        return f"background: center / cover fixed no-repeat url('{value}');"
    if kind == "solid" and _HEX_RE.fullmatch(value):
        return f"background: {value};"
    return f"background: {_GRADIENTS.get(f'{theme}:{value}', _GRADIENTS[f'{theme}:aurora'])};"


def context(request: Request, db: Session, **extra: object) -> dict:
    tracker = require_tracker(db)
    players = db.scalars(select(Player).where(Player.tracker_id == tracker.id).order_by(Player.id)).all()
    projects = db.scalars(select(Project).where(Project.tracker_id == tracker.id).order_by(Project.id.desc())).all()
    custom_tabs = db.scalars(select(CustomTab).where(CustomTab.tracker_id == tracker.id).order_by(CustomTab.id)).all()
    background = db.scalar(select(BackgroundSetting).where(BackgroundSetting.tracker_id == tracker.id))
    return {
        "request": request,
        "current_date": date.today().strftime("%d %b %Y"),
        "players": players,
        "projects": projects,
        "custom_tabs": custom_tabs,
        "background": background,
        "background_css": background_css(background),
        "tracker": tracker,
        "global_backups_enabled": settings.ALLOW_GLOBAL_BACKUPS,
        **extra,
    }


def _render(request: Request, template: str, db: Session, **extra: object):
    return templates.TemplateResponse(request=request, name=template, context=context(request, db, **extra))


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    with SessionLocal() as db:
        return _render(request, "home.html", db, page="home")


@router.get("/education", response_class=HTMLResponse)
def education(request: Request):
    with SessionLocal() as db:
        return _render(request, "education.html", db, page="education")


@router.get("/fitness", response_class=HTMLResponse)
def fitness(request: Request):
    with SessionLocal() as db:
        return _render(request, "fitness.html", db, page="fitness")


@router.get("/projects", response_class=HTMLResponse)
def projects(request: Request):
    with SessionLocal() as db:
        return _render(request, "projects.html", db, page="projects")


@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_detail(request: Request, project_id: int):
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.id == project_id, Project.tracker_id == require_tracker(db).id))
        if not project:
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context=context(request, db, code=404, message="Project not found."),
                status_code=404,
            )
        return _render(request, "project_detail.html", db, page="projects", project=project)


@router.get("/leaderboard", response_class=HTMLResponse)
def leaderboard(request: Request):
    with SessionLocal() as db:
        return _render(request, "leaderboard.html", db, page="leaderboard")


@router.get("/graph", response_class=HTMLResponse)
def graph(request: Request):
    with SessionLocal() as db:
        return _render(request, "graph.html", db, page="graph")


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    with SessionLocal() as db:
        return _render(request, "settings.html", db, page="settings")


@router.get("/tabs/{tab_id}", response_class=HTMLResponse)
def custom_tab(request: Request, tab_id: int):
    with SessionLocal() as db:
        tab = db.scalar(select(CustomTab).where(CustomTab.id == tab_id, CustomTab.tracker_id == require_tracker(db).id))
        if not tab:
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context=context(request, db, code=404, message="Custom tab not found."),
                status_code=404,
            )
        return _render(request, "custom_tab.html", db, page="custom", active_tab_id=tab.id, tab=tab)
