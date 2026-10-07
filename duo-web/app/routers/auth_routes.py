"""Login, sign-up, logout and the account page (with the personal invite code)."""
from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

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
from ..models import Player, User
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
    )
    return response


def _page(request: Request, name: str, status_code: int = 200, **ctx):
    return templates.TemplateResponse(request=request, name=name, context={"request": request, **ctx}, status_code=status_code)


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
        return _set_login_cookie(RedirectResponse("/", status_code=303), user.id)


@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request, code: str = ""):
    with SessionLocal() as db:
        first_user = db.scalar(select(func.count(User.id))) == 0
    return _page(request, "signup.html", error=None, first_user=first_user, form={"code": code.upper()})


@router.post("/signup")
def signup_submit(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    code: str = Form(""),
):
    name, email, code = name.strip()[:40], email.strip().lower(), code.strip().upper()
    form = {"name": name, "email": email, "code": code}
    with SessionLocal() as db:
        first_user = db.scalar(select(func.count(User.id))) == 0

        def fail(message: str):
            return _page(request, "signup.html", 400, error=message, first_user=first_user, form=form)

        if not name:
            return fail("Please enter your name.")
        if "@" not in email or "." not in email or len(email) > 255:
            return fail("Please enter a valid email address.")
        if len(password) < 8:
            return fail("Your password needs at least 8 characters.")
        if db.scalar(select(User.id).where(User.email == email)):
            return fail("That email already has an account. Try logging in.")
        if not first_user:
            if not code:
                return fail("Enter your partner's tracker code to join.")
            if db.scalar(select(User.id).where(User.invite_code == code)) is None:
                return fail("That code doesn't match anyone. Check it and try again.")

        taken = set(db.scalars(select(User.player_id).where(User.player_id.is_not(None))).all())
        free_player = next((p for p in db.scalars(select(Player).order_by(Player.id)).all() if p.id not in taken), None)
        if free_player is None:
            return fail("This tracker already has two players, so it is full.")

        free_player.name = name
        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=name,
            invite_code=generate_invite_code(db),
            player_id=free_player.id,
        )
        db.add(user)
        db.commit()
        return _set_login_cookie(RedirectResponse("/", status_code=303), user.id)


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    user_id = read_session_token(request.cookies.get(SESSION_COOKIE))
    with SessionLocal() as db:
        me = db.get(User, user_id) if user_id else None
        if me is None:
            return RedirectResponse("/login", status_code=303)
        partner = db.scalar(select(User).where(User.id != me.id).order_by(User.id))
        ctx = context(request, db, page="account", me=me, partner=partner)
        return templates.TemplateResponse(request=request, name="account.html", context=ctx)
