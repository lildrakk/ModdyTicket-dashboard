from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import os

from utils.db import get_config, get_tickets, get_open_tickets, get_stats, get_blacklist
from utils.discord_oauth import get_guild_channels, get_guild_roles

router = APIRouter()
templates = Jinja2Templates(directory="templates")
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

def _session(request: Request) -> dict:
    from routers.auth import get_session
    return get_session(request)

def _user(request: Request):
    return _session(request).get("user")

def _guilds(request: Request):
    return _session(request).get("admin_guilds", [])

def _check_auth(request: Request):
    if not _user(request):
        return RedirectResponse("/")
    return None

def _check_guild(request: Request, guild_id: str):
    if not any(g["id"] == guild_id for g in _guilds(request)):
        return RedirectResponse("/dashboard/servers?error=no_access")
    return None

@router.get("/servers")
async def servers(request: Request):
    r = _check_auth(request)
    if r: return r
    return templates.TemplateResponse("servers.html", {
        "request": request,
        "user": _user(request),
        "guilds": _guilds(request),
    })

@router.get("/select/{guild_id}")
async def select_guild(request: Request, guild_id: str):
    r = _check_auth(request)
    if r: return r
    guilds = _guilds(request)
    current = next((g for g in guilds if g["id"] == guild_id), None)
    if not current:
        return RedirectResponse("/dashboard/servers?error=no_access")

    from routers.auth import get_session, encode_session, make_session_cookie, COOKIE_MAX_AGE
    session = get_session(request)
    session["current_guild"]      = guild_id
    session["current_guild_name"] = current.get("name", "Servidor")
    session["current_guild_icon"] = current.get("icon_url")

    response = RedirectResponse(f"/dashboard/{guild_id}/overview", status_code=302)
    make_session_cookie(response, session)
    return response

@router.get("/{guild_id}/overview")
async def overview(request: Request, guild_id: str):
    r = _check_auth(request) or _check_guild(request, guild_id)
    if r: return r
    session = _session(request)

    config = await get_config(guild_id)
    st     = await get_stats(guild_id)
    open_t = await get_open_tickets(guild_id)
    all_t  = await get_tickets(guild_id)
    closed = [t for t in all_t if t.get("status") == "closed"]
    scores = st.get("feedback_scores", [])
    avg_fb = round(sum(s["score"] for s in scores) / len(scores), 1) if scores else 0

    from datetime import datetime, timedelta
    days_data = []
    for i in range(6, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).strftime("%d/%m")
        d_str = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        count = sum(1 for t in all_t if t.get("opened_at_iso", "").startswith(d_str))
        days_data.append({"day": day, "count": count})

    return templates.TemplateResponse("overview.html", {
        "request":      request,
        "user":         _user(request),
        "guild_id":     guild_id,
        "guild_name":   session.get("current_guild_name"),
        "guild_icon":   session.get("current_guild_icon"),
        "config":       config,
        "open_count":   len(open_t),
        "closed_count": len(closed),
        "total_count":  st.get("total_opened", 0),
        "avg_feedback": avg_fb,
        "categories":   st.get("categories", {}),
        "days_data":    days_data,
        "open_tickets": open_t[:10],
        "top_staff":    sorted(st.get("staff_claims", {}).items(), key=lambda x: x[1], reverse=True)[:5],
        "active_page":  "overview",
    })

@router.get("/{guild_id}/settings")
async def settings(request: Request, guild_id: str):
    r = _check_auth(request) or _check_guild(request, guild_id)
    if r: return r
    session = _session(request)
    config   = await get_config(guild_id)
    channels = await get_guild_channels(guild_id, BOT_TOKEN)
    roles    = await get_guild_roles(guild_id, BOT_TOKEN)
    return templates.TemplateResponse("settings.html", {
        "request":       request,
        "user":          _user(request),
        "guild_id":      guild_id,
        "guild_name":    session.get("current_guild_name"),
        "guild_icon":    session.get("current_guild_icon"),
        "config":        config,
        "text_channels": [c for c in channels if c.get("type") == 0],
        "categories":    [c for c in channels if c.get("type") == 4],
        "roles":         [r for r in roles if r["name"] != "@everyone"],
        "active_page":   "settings",
    })

@router.get("/{guild_id}/panels")
async def panels(request: Request, guild_id: str):
    r = _check_auth(request) or _check_guild(request, guild_id)
    if r: return r
    session = _session(request)
    config = await get_config(guild_id)
    return templates.TemplateResponse("panels.html", {
        "request":     request,
        "user":        _user(request),
        "guild_id":    guild_id,
        "guild_name":  session.get("current_guild_name"),
        "guild_icon":  session.get("current_guild_icon"),
        "panels":      config.get("panels", {}),
        "active_page": "panels",
    })

@router.get("/{guild_id}/tickets")
async def tickets_page(request: Request, guild_id: str, status: str = "all"):
    r = _check_auth(request) or _check_guild(request, guild_id)
    if r: return r
    session = _session(request)
    all_t = await get_tickets(guild_id)
    if status == "open":   filtered = [t for t in all_t if t.get("status") == "open"]
    elif status == "closed": filtered = [t for t in all_t if t.get("status") == "closed"]
    else: filtered = all_t
    return templates.TemplateResponse("tickets.html", {
        "request":      request,
        "user":         _user(request),
        "guild_id":     guild_id,
        "guild_name":   session.get("current_guild_name"),
        "guild_icon":   session.get("current_guild_icon"),
        "tickets":      list(reversed(filtered)),
        "status":       status,
        "total":        len(all_t),
        "open_count":   sum(1 for t in all_t if t.get("status") == "open"),
        "closed_count": sum(1 for t in all_t if t.get("status") == "closed"),
        "active_page":  "tickets",
    })

@router.get("/{guild_id}/stats")
async def stats_page(request: Request, guild_id: str):
    r = _check_auth(request) or _check_guild(request, guild_id)
    if r: return r
    session = _session(request)
    st    = await get_stats(guild_id)
    all_t = await get_tickets(guild_id)
    scores = st.get("feedback_scores", [])
    avg_fb = round(sum(s["score"] for s in scores) / len(scores), 1) if scores else 0
    return templates.TemplateResponse("stats.html", {
        "request":       request,
        "user":          _user(request),
        "guild_id":      guild_id,
        "guild_name":    session.get("current_guild_name"),
        "guild_icon":    session.get("current_guild_icon"),
        "stats":         st,
        "avg_feedback":  avg_fb,
        "feedback_dist": {str(i): sum(1 for s in scores if s["score"] == i) for i in range(1, 6)},
        "categories":    st.get("categories", {}),
        "top_staff":     sorted(st.get("staff_claims", {}).items(), key=lambda x: x[1], reverse=True)[:10],
        "total_tickets": len(all_t),
        "active_page":   "stats",
    })

@router.get("/{guild_id}/blacklist")
async def blacklist_page(request: Request, guild_id: str):
    r = _check_auth(request) or _check_guild(request, guild_id)
    if r: return r
    session = _session(request)
    bl = await get_blacklist(guild_id)
    return templates.TemplateResponse("blacklist.html", {
        "request":     request,
        "user":        _user(request),
        "guild_id":    guild_id,
        "guild_name":  session.get("current_guild_name"),
        "guild_icon":  session.get("current_guild_icon"),
        "blacklist":   bl,
        "active_page": "blacklist",
    })

@router.get("/{guild_id}/logs")
async def logs_page(request: Request, guild_id: str):
    r = _check_auth(request) or _check_guild(request, guild_id)
    if r: return r
    session = _session(request)
    all_t  = await get_tickets(guild_id)
    closed = [t for t in all_t if t.get("status") == "closed"]
    return templates.TemplateResponse("logs.html", {
        "request":     request,
        "user":        _user(request),
        "guild_id":    guild_id,
        "guild_name":  session.get("current_guild_name"),
        "guild_icon":  session.get("current_guild_icon"),
        "logs":        list(reversed(closed)),
        "active_page": "logs",
    })
