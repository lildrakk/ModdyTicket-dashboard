"""
routers/api.py — API REST para acciones de la dashboard (AJAX + formularios)
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import os

from utils.db import (
    get_config, save_config,
    get_blacklist, save_blacklist, get_stats, get_tickets
)

router = APIRouter()

async def _check_auth(request: Request):
    from routers.auth import get_session
    session = await get_session(request)
    if not session.get("user"):
        raise HTTPException(status_code=401, detail="No autenticado")
    return session

async def _check_guild(session: dict, guild_id: str):
    admin_guilds = session.get("admin_guilds", [])
    if not any(g["id"] == guild_id for g in admin_guilds):
        raise HTTPException(status_code=403, detail="Sin acceso a este servidor")

# ══════════════════════════════════════════════
#   SETTINGS
# ══════════════════════════════════════════════
class GeneralSettingsPayload(BaseModel):
    max_tickets_per_user: int = 3
    ping_staff_on_open: bool = True
    dm_on_close: bool = True
    feedback_enabled: bool = True
    rename_on_claim: bool = True
    auto_close_hours: int = 0
    welcome_message: str = ""
    close_message: str = ""
    log_channel: Optional[str] = None
    transcript_channel: Optional[str] = None
    ticket_category: Optional[str] = None
    closed_category: Optional[str] = None

@router.post("/{guild_id}/settings/general")
async def save_general_settings(request: Request, guild_id: str, payload: GeneralSettingsPayload):
    session = await _check_auth(request)
    await _check_guild(session, guild_id)
    config = await get_config(guild_id)
    config.update({
        "max_tickets_per_user": max(1, min(10, payload.max_tickets_per_user)),
        "ping_staff_on_open":   payload.ping_staff_on_open,
        "dm_on_close":          payload.dm_on_close,
        "feedback_enabled":     payload.feedback_enabled,
        "rename_on_claim":      payload.rename_on_claim,
        "auto_close_hours":     max(0, payload.auto_close_hours),
        "welcome_message":      payload.welcome_message[:500],
        "close_message":        payload.close_message[:500],
        "log_channel":          payload.log_channel or None,
        "transcript_channel":   payload.transcript_channel or None,
        "ticket_category":      payload.ticket_category or None,
        "closed_category":      payload.closed_category or None,
    })
    await save_config(guild_id, config)
    return {"ok": True, "message": "Configuración guardada ✅"}

class RolesPayload(BaseModel):
    staff_roles: List[str] = []
    admin_roles: List[str] = []

@router.post("/{guild_id}/settings/roles")
async def save_roles(request: Request, guild_id: str, payload: RolesPayload):
    session = await _check_auth(request)
    await _check_guild(session, guild_id)
    config = await get_config(guild_id)
    config["staff_roles"] = payload.staff_roles
    config["admin_roles"] = payload.admin_roles
    await save_config(guild_id, config)
    return {"ok": True, "message": "Roles actualizados ✅"}

# ══════════════════════════════════════════════
#   PANELES
# ══════════════════════════════════════════════
class PanelPayload(BaseModel):
    panel_id: str
    title: str
    description: str
    color: str = "5865F2"
    tipo: str = "buttons"
    footer: str = "ModdyTicket • Abre un ticket para recibir ayuda"
    thumbnail: Optional[str] = None
    image: Optional[str] = None
    select_placeholder: str = "📋 Selecciona una categoría..."

@router.post("/{guild_id}/panels/create")
async def create_panel(request: Request, guild_id: str, payload: PanelPayload):
    session = await _check_auth(request)
    await _check_guild(session, guild_id)
    config = await get_config(guild_id)
    panels = config.get("panels", {})
    pid = payload.panel_id.lower().replace(" ", "_")
    if pid in panels:
        raise HTTPException(400, f"Ya existe un panel con ID '{pid}'")
    try:
        color_int = int(payload.color.strip("#"), 16)
    except ValueError:
        color_int = 0x5865F2
    panels[pid] = {
        "panel_id":           pid,
        "title":              payload.title,
        "description":        payload.description,
        "color":              color_int,
        "image":              payload.image,
        "thumbnail":          payload.thumbnail,
        "type":               payload.tipo,
        "buttons":            [],
        "select_placeholder": payload.select_placeholder,
        "footer":             payload.footer,
    }
    config["panels"] = panels
    await save_config(guild_id, config)
    return {"ok": True, "message": f"Panel '{pid}' creado ✅", "panel_id": pid}

@router.put("/{guild_id}/panels/{panel_id}")
async def update_panel(request: Request, guild_id: str, panel_id: str, payload: PanelPayload):
    session = await _check_auth(request)
    await _check_guild(session, guild_id)
    config = await get_config(guild_id)
    panels = config.get("panels", {})
    if panel_id not in panels:
        raise HTTPException(404, "Panel no encontrado")
    p = panels[panel_id]
    try:
        color_int = int(payload.color.strip("#"), 16)
    except ValueError:
        color_int = p.get("color", 0x5865F2)
    p.update({
        "title":              payload.title,
        "description":        payload.description,
        "color":              color_int,
        "image":              payload.image,
        "thumbnail":          payload.thumbnail,
        "type":               payload.tipo,
        "select_placeholder": payload.select_placeholder,
        "footer":             payload.footer,
    })
    panels[panel_id] = p
    config["panels"] = panels
    await save_config(guild_id, config)
    return {"ok": True, "message": "Panel actualizado ✅"}

@router.delete("/{guild_id}/panels/{panel_id}")
async def delete_panel(request: Request, guild_id: str, panel_id: str):
    session = await _check_auth(request)
    await _check_guild(session, guild_id)
    config = await get_config(guild_id)
    panels = config.get("panels", {})
    if panel_id not in panels:
        raise HTTPException(404, "Panel no encontrado")
    del panels[panel_id]
    config["panels"] = panels
    await save_config(guild_id, config)
    return {"ok": True, "message": f"Panel '{panel_id}' eliminado ✅"}

class CategoryPayload(BaseModel):
    category_id: str
    label: str
    description: str = ""
    emoji: Optional[str] = None
    color: str = "blurple"
    ping_roles: List[str] = []
    channel_name: str = ""
    welcome_override: str = ""

@router.post("/{guild_id}/panels/{panel_id}/categories")
async def add_category(request: Request, guild_id: str, panel_id: str, payload: CategoryPayload):
    session = await _check_auth(request)
    await _check_guild(session, guild_id)
    config = await get_config(guild_id)
    panels = config.get("panels", {})
    if panel_id not in panels:
        raise HTTPException(404, "Panel no encontrado")
    buttons = panels[panel_id].get("buttons", [])
    if len(buttons) >= 5:
        raise HTTPException(400, "Máximo 5 categorías por panel")
    cid = payload.category_id.lower().replace(" ", "_")
    if any(b["category_id"] == cid for b in buttons):
        raise HTTPException(400, f"Categoría '{cid}' ya existe")
    buttons.append({
        "category_id":      cid,
        "label":            payload.label,
        "description":      payload.description,
        "emoji":            payload.emoji,
        "color":            payload.color,
        "ping_roles":       payload.ping_roles,
        "channel_name":     payload.channel_name or f"ticket-{cid}-{{id}}",
        "welcome_override": payload.welcome_override,
    })
    panels[panel_id]["buttons"] = buttons
    config["panels"] = panels
    await save_config(guild_id, config)
    return {"ok": True, "message": f"Categoría '{cid}' añadida ✅"}

@router.delete("/{guild_id}/panels/{panel_id}/categories/{category_id}")
async def delete_category(request: Request, guild_id: str, panel_id: str, category_id: str):
    session = await _check_auth(request)
    await _check_guild(session, guild_id)
    config = await get_config(guild_id)
    panels = config.get("panels", {})
    if panel_id not in panels:
        raise HTTPException(404, "Panel no encontrado")
    panels[panel_id]["buttons"] = [
        b for b in panels[panel_id].get("buttons", [])
        if b["category_id"] != category_id
    ]
    config["panels"] = panels
    await save_config(guild_id, config)
    return {"ok": True, "message": "Categoría eliminada ✅"}

# ══════════════════════════════════════════════
#   BLACKLIST
# ══════════════════════════════════════════════
class BlacklistPayload(BaseModel):
    user_id: str
    reason: str = "Sin razón"

@router.post("/{guild_id}/blacklist/add")
async def blacklist_add(request: Request, guild_id: str, payload: BlacklistPayload):
    session = await _check_auth(request)
    await _check_guild(session, guild_id)
    bl = await get_blacklist(guild_id)
    if payload.user_id in bl:
        raise HTTPException(400, "Usuario ya está en la lista negra")
    bl.append(payload.user_id)
    await save_blacklist(guild_id, bl)
    return {"ok": True, "message": f"Usuario {payload.user_id} bloqueado ✅"}

@router.delete("/{guild_id}/blacklist/{user_id}")
async def blacklist_remove(request: Request, guild_id: str, user_id: str):
    session = await _check_auth(request)
    await _check_guild(session, guild_id)
    bl = await get_blacklist(guild_id)
    if user_id not in bl:
        raise HTTPException(404, "Usuario no estaba en la lista negra")
    bl.remove(user_id)
    await save_blacklist(guild_id, bl)
    return {"ok": True, "message": "Usuario desbloqueado ✅"}

# ══════════════════════════════════════════════
#   STATS / DATA
# ══════════════════════════════════════════════
@router.get("/{guild_id}/data/stats")
async def get_stats_data(request: Request, guild_id: str):
    session = await _check_auth(request)
    await _check_guild(session, guild_id)
    st    = await get_stats(guild_id)
    all_t = await get_tickets(guild_id)
    scores = st.get("feedback_scores", [])
    return {
        "total_opened":  st.get("total_opened", 0),
        "total_closed":  st.get("total_closed", 0),
        "open_now":      sum(1 for t in all_t if t.get("status") == "open"),
        "avg_feedback":  round(sum(s["score"] for s in scores) / len(scores), 1) if scores else 0,
        "categories":    st.get("categories", {}),
        "staff_claims":  st.get("staff_claims", {}),
        "feedback_dist": {str(i): sum(1 for s in scores if s["score"] == i) for i in range(1, 6)},
    }

@router.get("/{guild_id}/data/tickets")
async def get_tickets_data(request: Request, guild_id: str):
    session = await _check_auth(request)
    await _check_guild(session, guild_id)
    all_t = await get_tickets(guild_id)
    return {
        "tickets": list(reversed(all_t[-50:])),
        "total":   len(all_t),
        "open":    sum(1 for t in all_t if t.get("status") == "open"),
        "closed":  sum(1 for t in all_t if t.get("status") == "closed"),
    }
