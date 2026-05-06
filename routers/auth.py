from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
import secrets, os, time

from utils.discord_oauth import (
    get_oauth_url, exchange_code, get_user,
    get_user_guilds, avatar_url, is_admin_in_guild, guild_icon_url
)
from utils.db import get_db

router = APIRouter()
COOKIE_NAME = "moddysid"
SESSION_TTL = 86400 * 7  # 7 días

# ── Helpers MongoDB sesiones ──────────────────────
async def _sessions():
    return get_db()["sessions"]

async def save_session(session_id: str, data: dict):
    col = await _sessions()
    await col.update_one(
        {"_id": session_id},
        {"$set": {"data": data, "expires": time.time() + SESSION_TTL}},
        upsert=True
    )

async def load_session(session_id: str) -> dict:
    col = await _sessions()
    doc = await col.find_one({"_id": session_id})
    if not doc:
        return {}
    if doc.get("expires", 0) < time.time():
        await col.delete_one({"_id": session_id})
        return {}
    return doc.get("data", {})

async def delete_session(session_id: str):
    col = await _sessions()
    await col.delete_one({"_id": session_id})

def get_session_id(request: Request) -> str | None:
    return request.cookies.get(COOKIE_NAME)

async def get_session(request: Request) -> dict:
    sid = get_session_id(request)
    if not sid:
        return {}
    return await load_session(sid)

# ── Rutas ─────────────────────────────────────────
@router.get("/login")
async def login(request: Request):
    state = secrets.token_urlsafe(16)
    # Guardar state en MongoDB también
    sid = secrets.token_urlsafe(32)
    await save_session(f"state_{sid}", {"oauth_state": state})
    response = RedirectResponse(get_oauth_url(state))
    response.set_cookie("oauth_state_id", sid, max_age=300, httponly=True, samesite="lax")
    return response

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

    # Crear sesión en MongoDB
    sid = secrets.token_urlsafe(32)
    session_data = {
        "user": {
            "id":            user["id"],
            "username":      user["username"],
            "discriminator": user.get("discriminator", "0"),
            "avatar_url":    avatar_url(user),
            "global_name":   user.get("global_name") or user["username"],
        },
        "access_token":  access_token,
        "admin_guilds":  admin_guilds,
        "logged_in":     True,
        "current_guild": None,
        "current_guild_name": None,
        "current_guild_icon": None,
    }
    await save_session(sid, session_data)

    response = RedirectResponse("/dashboard/servers", status_code=302)
    response.set_cookie(
        key=COOKIE_NAME,
        value=sid,
        max_age=SESSION_TTL,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response

@router.get("/logout")
async def logout(request: Request):
    sid = get_session_id(request)
    if sid:
        await delete_session(sid)
    response = RedirectResponse("/")
    response.delete_cookie(COOKIE_NAME)
    return response

@router.get("/check")
async def check(request: Request):
    session = await get_session(request)
    return {
        "user":         session.get("user"),
        "logged_in":    session.get("logged_in"),
        "guilds_count": len(session.get("admin_guilds", [])),
        "sid":          get_session_id(request),
    }
