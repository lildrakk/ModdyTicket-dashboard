"""
utils/db.py — Conexión y operaciones MongoDB Atlas para ModdyDashboard
"""
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
import os
from typing import Optional

_client: Optional[AsyncIOMotorClient] = None
_db = None

def get_db():
    global _client, _db
    if _db is None:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI no configurado en .env")
        _client = AsyncIOMotorClient(uri)
        _db = _client[os.getenv("MONGODB_DB", "moddyticket")]
    return _db

# ── Colecciones ───────────────────────────────
def configs():   return get_db()["configs"]
def tickets():   return get_db()["tickets"]
def stats():     return get_db()["stats"]
def blacklists():return get_db()["blacklists"]

# ══════════════════════════════════════════════
#   CONFIG
# ══════════════════════════════════════════════
DEFAULT_CONFIG = {
    "staff_roles": [],
    "admin_roles": [],
    "log_channel": None,
    "transcript_channel": None,
    "max_tickets_per_user": 3,
    "ticket_category": None,
    "closed_category": None,
    "ping_staff_on_open": True,
    "auto_close_hours": 0,
    "welcome_message": "¡Gracias por abrir un ticket! El staff te atenderá pronto.",
    "close_message": "Este ticket ha sido cerrado. ¡Hasta pronto!",
    "feedback_enabled": True,
    "dm_on_close": True,
    "ticket_counter": 0,
    "rename_on_claim": True,
    "panels": {},
}

async def get_config(guild_id: str) -> dict:
    doc = await configs().find_one({"guild_id": guild_id})
    if not doc:
        return {**DEFAULT_CONFIG, "guild_id": guild_id}
    doc.pop("_id", None)
    return doc

async def save_config(guild_id: str, data: dict) -> dict:
    data["guild_id"] = guild_id
    data.pop("_id", None)
    result = await configs().find_one_and_replace(
        {"guild_id": guild_id}, data,
        upsert=True, return_document=ReturnDocument.AFTER
    )
    result.pop("_id", None)
    return result

async def update_config_field(guild_id: str, field: str, value) -> None:
    await configs().update_one(
        {"guild_id": guild_id},
        {"$set": {field: value}},
        upsert=True
    )

# ══════════════════════════════════════════════
#   TICKETS
# ══════════════════════════════════════════════
async def get_tickets(guild_id: str) -> list:
    cursor = tickets().find({"guild_id": guild_id})
    result = []
    async for doc in cursor:
        doc.pop("_id", None)
        result.append(doc)
    return result

async def get_open_tickets(guild_id: str) -> list:
    cursor = tickets().find({"guild_id": guild_id, "status": "open"})
    result = []
    async for doc in cursor:
        doc.pop("_id", None)
        result.append(doc)
    return result

async def get_ticket_by_id(guild_id: str, ticket_id: str) -> Optional[dict]:
    doc = await tickets().find_one({"guild_id": guild_id, "ticket_id": ticket_id})
    if doc:
        doc.pop("_id", None)
    return doc

# ══════════════════════════════════════════════
#   STATS
# ══════════════════════════════════════════════
async def get_stats(guild_id: str) -> dict:
    doc = await stats().find_one({"guild_id": guild_id})
    if not doc:
        return {
            "guild_id": guild_id,
            "total_opened": 0,
            "total_closed": 0,
            "staff_claims": {},
            "feedback_scores": [],
            "categories": {},
        }
    doc.pop("_id", None)
    return doc

# ══════════════════════════════════════════════
#   BLACKLIST
# ══════════════════════════════════════════════
async def get_blacklist(guild_id: str) -> list:
    doc = await blacklists().find_one({"guild_id": guild_id})
    return doc.get("users", []) if doc else []

async def save_blacklist(guild_id: str, users: list) -> None:
    await blacklists().update_one(
        {"guild_id": guild_id},
        {"$set": {"users": users}},
        upsert=True
    )
