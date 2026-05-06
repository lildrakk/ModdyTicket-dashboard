"""
utils/discord_oauth.py — Helpers OAuth2 Discord
"""
import httpx, os
from typing import Optional

DISCORD_API = "https://discord.com/api/v10"
DISCORD_CDN = "https://cdn.discordapp.com"

CLIENT_ID     = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("DISCORD_REDIRECT_URI")

SCOPES = "identify guilds"

def get_oauth_url(state: str) -> str:
    return (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={SCOPES.replace(' ', '%20')}"
        f"&state={state}"
        f"&prompt=none"
    )

async def exchange_code(code: str) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{DISCORD_API}/oauth2/token",
            data={
                "client_id":     CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type":    "authorization_code",
                "code":          code,
                "redirect_uri":  REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code != 200:
            return None
        return r.json()

async def get_user(access_token: str) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code != 200:
            return None
        return r.json()

async def get_user_guilds(access_token: str) -> list:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{DISCORD_API}/users/@me/guilds",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code != 200:
            return []
        return r.json()

async def get_guild(guild_id: str, bot_token: str) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{DISCORD_API}/guilds/{guild_id}?with_counts=true",
            headers={"Authorization": f"Bot {bot_token}"},
        )
        if r.status_code != 200:
            return None
        return r.json()

async def get_guild_channels(guild_id: str, bot_token: str) -> list:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{DISCORD_API}/guilds/{guild_id}/channels",
            headers={"Authorization": f"Bot {bot_token}"},
        )
        if r.status_code != 200:
            return []
        return r.json()

async def get_guild_roles(guild_id: str, bot_token: str) -> list:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{DISCORD_API}/guilds/{guild_id}/roles",
            headers={"Authorization": f"Bot {bot_token}"},
        )
        if r.status_code != 200:
            return []
        return r.json()

def avatar_url(user: dict) -> str:
    uid  = user.get("id")
    av   = user.get("avatar")
    disc = int(user.get("discriminator", "0") or "0")
    if av:
        ext = "gif" if av.startswith("a_") else "png"
        return f"{DISCORD_CDN}/avatars/{uid}/{av}.{ext}?size=128"
    default_idx = (int(uid) >> 22) % 6
    return f"{DISCORD_CDN}/embed/avatars/{default_idx}.png"

def guild_icon_url(guild: dict) -> Optional[str]:
    gid  = guild.get("id")
    icon = guild.get("icon")
    if not icon:
        return None
    ext = "gif" if icon.startswith("a_") else "png"
    return f"{DISCORD_CDN}/icons/{gid}/{icon}.{ext}?size=128"

def is_admin_in_guild(guild: dict) -> bool:
    """Verifica si el usuario tiene ADMINISTRATOR en ese servidor."""
    ADMIN_PERM = 0x8
    permissions = int(guild.get("permissions", 0))
    return bool(permissions & ADMIN_PERM) or guild.get("owner", False)
