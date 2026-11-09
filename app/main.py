"""PSKG Monitor 2030 — FastAPI application entry point.

Run (development):   python -m uvicorn app.main:app --reload
"""
from __future__ import annotations

import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, SessionLocal, engine  # noqa: F401  (re-exported for scripts / V2B compatibility)
from .models import User  # noqa: F401
from .security import CSRF_HEADER, CSRF_VALUE, password_hash  # noqa: F401

# Windows registries sometimes map .js to text/plain, which browsers refuse to execute.
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

log = logging.getLogger("pskg")
STATIC = Path(__file__).parent / "static"
VERSION = "2030.1.0-mvp"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_migrate:
        from .migrate import upgrade_to_head
        upgrade_to_head()
    settings.evidence_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="PSKG Monitor 2030", version=VERSION, docs_url="/api/docs", openapi_url="/api/openapi.json",
              redoc_url=None, lifespan=lifespan)

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "font-src 'self' data:; connect-src 'self'; frame-src 'self' blob:; object-src 'none'; base-uri 'self'; "
       "form-action 'self'; frame-ancestors 'self'")


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # CSRF defence for cookie-authenticated, state-changing API calls: a custom header cannot be
    # sent cross-site without a CORS pre-flight (which this API never grants). Bearer-token clients
    # are not exposed to CSRF and are exempt.
    if (request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path.startswith("/api/")
            and not request.headers.get("authorization", "").lower().startswith("bearer ")
            and request.headers.get(CSRF_HEADER) != CSRF_VALUE):
        return JSONResponse({"detail": "Permintaan ditolak (pengesahan CSRF gagal)."}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if not request.url.path.startswith("/api/docs"):
        response.headers.setdefault("Content-Security-Policy", CSP)
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    if settings.cookie_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


from .routers import accounts, admin, dashboards, public, reporting, reports  # noqa: E402

for r in (public.router, accounts.router, reporting.router, dashboards.router, reports.router, admin.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=STATIC), name="static")
