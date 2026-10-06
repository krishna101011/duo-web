"""HTML page routes."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import BackgroundSetting, CustomTab, Player, Project

router = APIRouter()
templates = Jinja2Templates(directory=str(settings.TEMPLATE_DIR))


def context(request: Request, db: Session, **extra: object) -> dict:
    players = db.scalars(select(Player).order_by(Player.id)).all()
    projects = db.scalars(select(Project).order_by(Project.id.desc())).all()
    custom_tabs = db.scalars(select(CustomTab).order_by(CustomTab.id)).all()
    background = db.get(BackgroundSetting, 1)
    from datetime import date
    return {
        "request": request,
        "current_date": date.today().strftime("%d %b %Y"),
        "players": players,
        "projects": projects,
        "custom_tabs": custom_tabs,
        "background": background,
        **extra,
    }


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    with SessionLocal() as db:
        return templates.TemplateResponse(request=request, name="home.html", context=context(request, db, page="home"))


@router.get("/education", response_class=HTMLResponse)
def education(request: Request):
    with SessionLocal() as db:
        return templates.TemplateResponse(request=request, name="education.html", context=context(request, db, page="education"))


@router.get("/fitness", response_class=HTMLResponse)
def fitness(request: Request):
    with SessionLocal() as db:
        return templates.TemplateResponse(request=request, name="fitness.html", context=context(request, db, page="fitness"))


@router.get("/projects", response_class=HTMLResponse)
def projects(request: Request):
    with SessionLocal() as db:
        return templates.TemplateResponse(request=request, name="projects.html", context=context(request, db, page="projects"))


@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_detail(request: Request, project_id: int):
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if not project:
            return templates.TemplateResponse(request=request, name="error.html", context=context(request, db, code=404, message="Project not found."), status_code=404)
        return templates.TemplateResponse(request=request, name="project_detail.html", context=context(request, db, page="projects", project=project))


@router.get("/leaderboard", response_class=HTMLResponse)
def leaderboard(request: Request):
    with SessionLocal() as db:
        return templates.TemplateResponse(request=request, name="leaderboard.html", context=context(request, db, page="leaderboard"))


@router.get("/graph", response_class=HTMLResponse)
def graph(request: Request):
    with SessionLocal() as db:
        return templates.TemplateResponse(request=request, name="graph.html", context=context(request, db, page="graph"))


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    with SessionLocal() as db:
        return templates.TemplateResponse(request=request, name="settings.html", context=context(request, db, page="settings"))


@router.get("/tabs/{tab_id}", response_class=HTMLResponse)
def custom_tab(request: Request, tab_id: int):
    with SessionLocal() as db:
        tab = db.get(CustomTab, tab_id)
        if not tab:
            return templates.TemplateResponse(request=request, name="error.html", context=context(request, db, code=404, message="Custom tab not found."), status_code=404)
        return templates.TemplateResponse(request=request, name="custom_tab.html", context=context(request, db, page="custom", active_tab_id=tab.id, tab=tab))
