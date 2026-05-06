from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import secrets, os

from utils.discord_oauth import (
    get_oauth_url, exchange_code, get_user,
    get_user_guilds, avatar_url, is_admin_in_guild, guild_icon_url
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/login")
async def login(request: Request):
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    return RedirectResponse(get_oauth_url(state))

@router.get("/callback")
async def callback(request: Request, code: str = None, state: str = None, error: str = None):
    if error or not code:
        return RedirectResponse("/?error=access_denied")

    token_data = await exchange_code(code)
    if not token_data:
        return RedirectResponse("/?error=token_failed")

    access_token = token_data["access_token"]
    user = await get_user(access_token)
    if not user:
        return RedirectResponse("/?error=user_failed")

    guilds = await get_user_guilds(access_token)
    admin_guilds = [g for g in guilds if is_admin_in_guild(g)]
    for g in admin_guilds:
        g["icon_url"] = guild_icon_url(g)

    # Guardar en sesión
    request.session["user"] = {
        "id":            user["id"],
        "username":      user["username"],
        "discriminator": user.get("discriminator", "0"),
        "avatar_url":    avatar_url(user),
        "global_name":   user.get("global_name") or user["username"],
    }
    request.session["access_token"]  = access_token
    request.session["admin_guilds"]  = admin_guilds
    request.session["logged_in"]     = True

    # Forzar que la sesión se escriba antes de redirigir
    response = RedirectResponse("/dashboard/servers", status_code=302)
    return response

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

@router.get("/check")
async def check(request: Request):
    """Debug: ver qué hay en la sesión"""
    return {
        "user": request.session.get("user"),
        "logged_in": request.session.get("logged_in"),
        "guilds_count": len(request.session.get("admin_guilds", [])),
    }
