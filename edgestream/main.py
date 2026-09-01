"""
Project:   edgestream-api
File:      edgestream/main.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, Request, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from starlette.templating import _TemplateResponse
import jwt

from edgestream.api.v1.api_router import api_router
from edgestream.core.config import settings, Logger
from edgestream.db import base  # noqa: F401
from edgestream.db.session import SessionLocal
from edgestream.services.background.audit_tasks import enqueue_audit
from edgestream.services.middleware import CorrelationIdMiddleware

BASE_PATH = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_PATH / "core/templates"))

root_router = APIRouter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup/shutdown. DB init is handled externally by systemd
    to avoid multi-worker race conditions.
    """
    Logger.logger.info(f"Starting EdgeStream Hub API v{settings.VERSION}")

    if settings.SECRETS_READ_DENIED:
        Logger.logger.error("CRITICAL: Secrets file unreadable.")
    yield


app = FastAPI(
    title="EdgeStream Hub API",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(o) for o in settings.BACKEND_CORS_ORIGINS],
    allow_origin_regex=settings.BACKEND_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id", "x-correlation-id"],
)


@root_router.get("/", status_code=200)
def root(request: Request) -> _TemplateResponse:
    return TEMPLATES.TemplateResponse(
        "index.html",
        {"request": request, "collector": "edgestream-node"},
    )


app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(root_router)


def _maybe_actor_from_request(request: Request) -> str | None:
    """
    Safely extracts the user identity for audit logs.
    Fixes Semgrep findings:
    1. verify_signature=False is removed.
    2. Directly returned f-string (XSS risk) is removed.
    """
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None

    token = auth.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(
            token,
            key=settings.JWT_SECRET,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False, "verify_aud": False}
        )

        return str(payload.get("sub", "unknown"))

    except jwt.PyJWTError:
        # Token is tampered with or malformed.
        return "invalid-token"
    except Exception:
        return None


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
        bg = BackgroundTasks()
        enqueue_audit(
            bg,
            SessionLocal,
            request,
            event_type="access_denied",
            result="failure",
            actor_id=_maybe_actor_from_request(request),
            status_code=exc.status_code,
            details={"path": request.url.path, "detail": str(exc.detail)},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            background=bg,
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("edgestream.main:app", host="127.0.0.1", port=8001, reload=True)