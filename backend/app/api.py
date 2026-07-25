"""API routes.

Everything the frontend talks to lives under ``/api``. For B-01 this is only a
health check; it also gives the SPA a way to show that the front and the API are
served from the same origin (no CORS), which is the co-hosting invariant this
skeleton exists to establish.
"""

from __future__ import annotations

from fastapi import APIRouter

from .config import SERVICE_NAME

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}
