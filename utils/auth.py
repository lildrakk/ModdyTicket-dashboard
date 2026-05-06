"""
utils/auth.py — Dependencias de autenticación para FastAPI
"""
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse

def get_session_user(request: Request) -> dict:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")
    return user

def require_login(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/")
    return user

def get_current_guild(request: Request) -> str:
    guild_id = request.session.get("current_guild")
    if not guild_id:
        raise HTTPException(status_code=400, detail="No hay servidor seleccionado")
    return guild_id
