from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import uvicorn, os
from dotenv import load_dotenv

load_dotenv()

from routers import auth, dashboard, api

app = FastAPI(title="ModdyTicket Dashboard", docs_url=None, redoc_url=None)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(auth.router,      prefix="/auth",      tags=["auth"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(api.router,       prefix="/api",       tags=["api"])

@app.get("/")
async def root(request: Request):
    from routers.auth import get_session
    user = get_session(request).get("user")
    if user:
        return RedirectResponse("/dashboard/servers")
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
