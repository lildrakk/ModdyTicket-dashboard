from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
import secrets, os, json, base64, hmac, hashlib, time

from utils.discord_oauth import (
    get_oauth_url, exchange_code, get_user,
    get_user_guilds, avatar_url, is_admin_in_guild, guild_icon_url
)

router = APIRouter()
SECRET = os.getenv("SECRET_KEY", "clave_cambiar")
COOKIE_NAME = "moddysession"
COOKIE_MAX_AGE = 86400 * 7  # 7 días

def _sign(data: str) -> str:
    sig = hmac.new(SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
    return sig

def encode_session(payload: dict) -> str:
    data = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = _sign(data)
    return f"{data}.{sig}"

def decode_session(token: str) -> dict | None:
    try:
        data, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(_sign(data), sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(data.encode()).decode())
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None

def get_session(request: Request) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return {}
    return decode_session(token) or {}

def make_session_cookie(response: RedirectResponse, payload: dict):
    payload["exp"] = time.time() + COOKIE_MAX_AGE
    token = encode_session(payload)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return response

@router.get("/login")
async def login(request: Request):
    state = secrets.token_urlsafe(16)
    response = RedirectResponse(get_oauth_url(state))
    response.set_cookie("oauth_state", state, max_age=300, httponly=True, secure=True, samesite="lax")
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

    payload = {
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
    }

    response = RedirectResponse("/dashboard/servers", status_code=302)
    make_session_cookie(response, payload)
    return response

@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse("/")
    response.delete_cookie(COOKIE_NAME)
    return response

@router.get("/check")
async def check(request: Request):
    session = get_session(request)
    return {
        "user":         session.get("user"),
        "logged_in":    session.get("logged_in"),
        "guilds_count": len(session.get("admin_guilds", [])),
    }
