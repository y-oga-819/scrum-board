"""Runtime configuration for the backend.

The single App Service co-hosts the API and the built Angular SPA (see the
design proposal, ch. 09). In production the SPA lives next to the backend as a
build artifact; locally it is produced by `ng build` into
``frontend/dist/frontend/browser``. The location can be overridden with the
``SPA_DIST_DIR`` environment variable so deployment layouts stay flexible.
"""

from __future__ import annotations

import os
from pathlib import Path

SERVICE_NAME = "scrum-board"

# backend/app/config.py -> repo root is three levels up.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SPA_DIST = _REPO_ROOT / "frontend" / "dist" / "frontend" / "browser"


def spa_dist_dir() -> Path:
    """Directory holding the built Angular SPA (index.html + assets)."""
    override = os.environ.get("SPA_DIST_DIR")
    return Path(override).resolve() if override else _DEFAULT_SPA_DIST
