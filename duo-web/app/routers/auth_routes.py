"""Login, multi-tracker sign-up, logout, and account page."""
from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from ..auth import (
    SESSION_COOKIE,
    SESSION_SECONDS,
    generate_invite_code,
    hash_password,
    make_session_token,
    read_session_token,
    verify_password,
)
from ..config import settings
from ..db import SessionLocal
from ..models import Player, Tracker, User
from ..services.tenant import require_tracker
from ..services.tracker import create_tracker_for_user, provision_tracker_settings, tracker_player_count
from .pages import context, templates

router = APIRouter()


def _set_login_cookie(response: RedirectResponse, user_id: int) -> RedirectResponse:
    response.set_cookie(
        SESSION_COOKIE,
        make_session_token(user_id),
        max_age=SESSION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=settings.APP_ENV == "production",
        path="/",
    )
    return response


def _page(request: Request, name: str, status_code: int = 200, **ctx):
    return templates.TemplateResponse(
        request=request,
        name=name,
        context={"request": request, **ctx},
        status_code=status_code,
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if read_session_token(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/", status_code=303)
    return _page(request, "login.html", error=None, email="")


@router.post("/login")
def login_submit(request: Request, email: str = Form(""), password: str = Form("")):
    email = email.strip().lower()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None or not verify_password(password, user.password_hash):
            return _page(request, "login.html", 400, error="Wrong email or password.", email=email)
        if user.tracker_id is None or user.player_id is None:
            return _page(request, "login.html", 400, error="This account is missing a tracker. Please contact the app owner.", email=email)
        return _set_login_cookie(RedirectResponse("/", status_code=303), user.id)


@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request, mode: str = "create", code: str = ""):
    mode = "join" if mode.lower() == "join" or code else "create"
    return _page(
        request,
        "signup.html",
        error=None,
        form={"name": "", "email": "", "code": code.strip().upper()},
        mode=mode,
    )


@router.post("/signup")
def signup_submit(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    mode: str = Form("create"),
    code: str = Form(""),
):
    name = name.strip()[:40]
    email = email.strip().lower()
    mode = "join" if mode.lower() == "join" else "create"
    code = code.strip().upper()
    form = {"name": name, "email": email, "code": code}

    with SessionLocal() as db:
        def fail(message: str):
            return _page(request, "signup.html", 400, error=message, form=form, mode=mode)

        if not name:
            return fail("Please enter your name.")
        if "@" not in email or "." not in email.split("@")[-1] or len(email) > 255:
            return fail("Please enter a valid email address.")
        if len(password) < 8:
            return fail("Your password needs at least 8 characters.")
        if db.scalar(select(User.id).where(User.email == email)):
            return fail("That email already has an account. Try logging in.")

        if mode == "join":
            if not code:
                return fail("Enter your partner's 6-character Tracker ID.")
            tracker = db.scalar(select(Tracker).where(Tracker.code == code))
            if tracker is None:
                return fail("That Tracker ID does not exist. Check the code and try again.")
            players = db.scalars(select(Player).where(Player.tracker_id == tracker.id).order_by(Player.id)).all()
            members = db.scalars(select(User).where(User.tracker_id == tracker.id).order_by(User.id)).all()
            if len(members) >= 2:
                return fail("That tracker already has two accounts. Create a new tracker or use a different code.")

            claimed_player_ids = {member.player_id for member in members if member.player_id is not None}
            # Upgraded legacy databases can already contain two player records even
            # when only one account exists. Claim an unclaimed slot before creating a new one.
            player = next((p for p in players if p.id not in claimed_player_ids), None)
            if player is None:
                player = Player(tracker_id=tracker.id, name=name, emoji="🙂", accent="hot")
                db.add(player)
                db.flush()
            else:
                player.name = name
                player.emoji = "🙂"
                player.accent = "hot"

            user = User(
                email=email,
                password_hash=hash_password(password),
                display_name=name,
                invite_code=generate_invite_code(db),
                tracker_id=tracker.id,
                player_id=player.id,
            )
            db.add(user)
            provision_tracker_settings(db, tracker.id)
            db.commit()
            return _set_login_cookie(RedirectResponse("/", status_code=303), user.id)

        # CREATE mode: every person may create their own independent tracker.
        user = create_tracker_for_user(
            db,
            name=name,
            email=email,
            password_hash=hash_password(password),
            display_name=name,
            player_emoji="🙂",
        )
        db.commit()
        return _set_login_cookie(RedirectResponse("/", status_code=303), user.id)


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    user_id = read_session_token(request.cookies.get(SESSION_COOKIE))
    with SessionLocal() as db:
        me = db.get(User, user_id) if user_id else None
        if me is None or me.tracker_id is None:
            return RedirectResponse("/login", status_code=303)
        tracker = db.get(Tracker, me.tracker_id)
        if tracker is None:
            return RedirectResponse("/login", status_code=303)
        partner = db.scalar(
            select(User).where(User.tracker_id == tracker.id, User.id != me.id).order_by(User.id)
        )
        provision_tracker_settings(db, tracker.id)
        db.commit()
        ctx = context(request, db, page="account", me=me, partner=partner, tracker=tracker)
        return templates.TemplateResponse(request=request, name="account.html", context=ctx)
