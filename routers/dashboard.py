"""
routers/dashboard.py — Páginas principales de la dashboard
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import os

from utils.auth import require_login
from utils.db import get_config, get_tickets, get_open_tickets, get_stats, get_blacklist
from utils.discord_oauth import (
    get_guild, get_guild_channels, get_guild_roles,
    guild_icon_url, is_admin_in_guild
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

def _redirect_if_not_logged(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/")
    return None

# ── Selector de servidores ────────────────────
@router.get("/servers")
async def servers(request: Request):
    redir = _redirect_if_not_logged(request)
    if redir: return redir
    user         = request.session["user"]
    admin_guilds = request.session.get("admin_guilds", [])
    return templates.TemplateResponse("servers.html", {
        "request": request,
        "user": user,
        "guilds": admin_guilds,
    })

# ── Seleccionar servidor ──────────────────────
@router.get("/select/{guild_id}")
async def select_guild(request: Request, guild_id: str):
    redir = _redirect_if_not_logged(request)
    if redir: return redir
    admin_guilds = request.session.get("admin_guilds", [])
    if not any(g["id"] == guild_id for g in admin_guilds):
        return RedirectResponse("/dashboard/servers?error=no_access")
    request.session["current_guild"] = guild_id
    current = next((g for g in admin_guilds if g["id"] == guild_id), {})
    request.session["current_guild_name"] = current.get("name", "Servidor")
    request.session["current_guild_icon"] = current.get("icon_url")
    return RedirectResponse(f"/dashboard/{guild_id}/overview")

# ── Overview ──────────────────────────────────
@router.get("/{guild_id}/overview")
async def overview(request: Request, guild_id: str):
    redir = _redirect_if_not_logged(request)
    if redir: return redir
    _check_guild_access(request, guild_id)

    config  = await get_config(guild_id)
    st      = await get_stats(guild_id)
    open_t  = await get_open_tickets(guild_id)
    all_t   = await get_tickets(guild_id)
    closed  = [t for t in all_t if t.get("status") == "closed"]

    scores  = st.get("feedback_scores", [])
    avg_fb  = round(sum(s["score"] for s in scores) / len(scores), 1) if scores else 0

    # Últimos 7 días de actividad
    from datetime import datetime, timedelta
    days_data = []
    for i in range(6, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).strftime("%d/%m")
        count = sum(1 for t in all_t if t.get("opened_at_iso", "").startswith(
            (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")))
        days_data.append({"day": day, "count": count})

    return templates.TemplateResponse("overview.html", {
        "request":      request,
        "user":         request.session["user"],
        "guild_id":     guild_id,
        "guild_name":   request.session.get("current_guild_name"),
        "guild_icon":   request.session.get("current_guild_icon"),
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

# ── Configuración ─────────────────────────────
@router.get("/{guild_id}/settings")
async def settings(request: Request, guild_id: str):
    redir = _redirect_if_not_logged(request)
    if redir: return redir
    _check_guild_access(request, guild_id)

    config   = await get_config(guild_id)
    channels = await get_guild_channels(guild_id, BOT_TOKEN)
    roles    = await get_guild_roles(guild_id, BOT_TOKEN)

    text_channels = [c for c in channels if c.get("type") == 0]
    categories    = [c for c in channels if c.get("type") == 4]
    filtered_roles = [r for r in roles if r["name"] != "@everyone"]

    return templates.TemplateResponse("settings.html", {
        "request":       request,
        "user":          request.session["user"],
        "guild_id":      guild_id,
        "guild_name":    request.session.get("current_guild_name"),
        "guild_icon":    request.session.get("current_guild_icon"),
        "config":        config,
        "text_channels": text_channels,
        "categories":    categories,
        "roles":         filtered_roles,
        "active_page":   "settings",
    })

# ── Paneles ───────────────────────────────────
@router.get("/{guild_id}/panels")
async def panels(request: Request, guild_id: str):
    redir = _redirect_if_not_logged(request)
    if redir: return redir
    _check_guild_access(request, guild_id)

    config = await get_config(guild_id)
    return templates.TemplateResponse("panels.html", {
        "request":     request,
        "user":        request.session["user"],
        "guild_id":    guild_id,
        "guild_name":  request.session.get("current_guild_name"),
        "guild_icon":  request.session.get("current_guild_icon"),
        "panels":      config.get("panels", {}),
        "active_page": "panels",
    })

# ── Tickets ───────────────────────────────────
@router.get("/{guild_id}/tickets")
async def tickets_page(request: Request, guild_id: str, status: str = "all"):
    redir = _redirect_if_not_logged(request)
    if redir: return redir
    _check_guild_access(request, guild_id)

    all_t = await get_tickets(guild_id)
    if status == "open":
        filtered = [t for t in all_t if t.get("status") == "open"]
    elif status == "closed":
        filtered = [t for t in all_t if t.get("status") == "closed"]
    else:
        filtered = all_t

    return templates.TemplateResponse("tickets.html", {
        "request":     request,
        "user":        request.session["user"],
        "guild_id":    guild_id,
        "guild_name":  request.session.get("current_guild_name"),
        "guild_icon":  request.session.get("current_guild_icon"),
        "tickets":     list(reversed(filtered)),
        "status":      status,
        "total":       len(all_t),
        "open_count":  sum(1 for t in all_t if t.get("status") == "open"),
        "closed_count":sum(1 for t in all_t if t.get("status") == "closed"),
        "active_page": "tickets",
    })

# ── Estadísticas ──────────────────────────────
@router.get("/{guild_id}/stats")
async def stats_page(request: Request, guild_id: str):
    redir = _redirect_if_not_logged(request)
    if redir: return redir
    _check_guild_access(request, guild_id)

    st    = await get_stats(guild_id)
    all_t = await get_tickets(guild_id)

    scores = st.get("feedback_scores", [])
    avg_fb = round(sum(s["score"] for s in scores) / len(scores), 1) if scores else 0
    dist   = {str(i): sum(1 for s in scores if s["score"] == i) for i in range(1, 6)}

    return templates.TemplateResponse("stats.html", {
        "request":       request,
        "user":          request.session["user"],
        "guild_id":      guild_id,
        "guild_name":    request.session.get("current_guild_name"),
        "guild_icon":    request.session.get("current_guild_icon"),
        "stats":         st,
        "avg_feedback":  avg_fb,
        "feedback_dist": dist,
        "categories":    st.get("categories", {}),
        "top_staff":     sorted(st.get("staff_claims", {}).items(), key=lambda x: x[1], reverse=True)[:10],
        "total_tickets": len(all_t),
        "active_page":   "stats",
    })

# ── Blacklist ─────────────────────────────────
@router.get("/{guild_id}/blacklist")
async def blacklist_page(request: Request, guild_id: str):
    redir = _redirect_if_not_logged(request)
    if redir: return redir
    _check_guild_access(request, guild_id)

    bl = await get_blacklist(guild_id)
    return templates.TemplateResponse("blacklist.html", {
        "request":     request,
        "user":        request.session["user"],
        "guild_id":    guild_id,
        "guild_name":  request.session.get("current_guild_name"),
        "guild_icon":  request.session.get("current_guild_icon"),
        "blacklist":   bl,
        "active_page": "blacklist",
    })

# ── Logs ──────────────────────────────────────
@router.get("/{guild_id}/logs")
async def logs_page(request: Request, guild_id: str):
    redir = _redirect_if_not_logged(request)
    if redir: return redir
    _check_guild_access(request, guild_id)

    all_t  = await get_tickets(guild_id)
    closed = [t for t in all_t if t.get("status") == "closed"]

    return templates.TemplateResponse("logs.html", {
        "request":     request,
        "user":        request.session["user"],
        "guild_id":    guild_id,
        "guild_name":  request.session.get("current_guild_name"),
        "guild_icon":  request.session.get("current_guild_icon"),
        "logs":        list(reversed(closed)),
        "active_page": "logs",
    })

def _check_guild_access(request: Request, guild_id: str):
    admin_guilds = request.session.get("admin_guilds", [])
    if not any(g["id"] == guild_id for g in admin_guilds):
        raise RedirectResponse("/dashboard/servers?error=no_access")
