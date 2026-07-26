"""Runtime configuration for the backend.

The single App Service co-hosts the API and the built Angular SPA (see the
design proposal, ch. 09). The SPA's location differs by environment, so
:func:`spa_dist_dir` tries a few known layouts in order:

* an explicit ``SPA_DIST_DIR`` override (if it actually holds the SPA);
* the **deployed** layout, where ``app/`` and ``spa/browser/`` are packaged as
  siblings (see ``.github/workflows/deploy.yml``). On App Service, Oryx compresses
  the build into ``output.tar.zst`` and extracts it to a *runtime* temp directory,
  so an absolute path like ``/home/site/wwwroot/spa/browser`` is wrong — but the
  SPA is always next to this package, so we resolve it relative to ``__file__``;
* the **local dev** layout, ``frontend/dist/frontend/browser`` from ``ng build``.
"""

from __future__ import annotations

import os
from pathlib import Path

SERVICE_NAME = "scrum-board"

# app/config.py -> the package's parent holds a sibling ``spa/browser`` when deployed.
_APP_PARENT = Path(__file__).resolve().parent.parent
_DEPLOYED_SPA_DIST = _APP_PARENT / "spa" / "browser"

# backend/app/config.py -> repo root is three levels up (local dev, `ng build`).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SPA_DIST = _REPO_ROOT / "frontend" / "dist" / "frontend" / "browser"


def spa_dist_dir() -> Path:
    """Directory holding the built Angular SPA (index.html + assets).

    Returns the first candidate that actually contains ``index.html``. Checking
    for the file (not just the path) means a stale ``SPA_DIST_DIR`` pointing at a
    location that no longer holds the SPA — e.g. the pre-compression wwwroot on
    App Service — falls through to the layout that does.
    """
    candidates: list[Path] = []
    override = os.environ.get("SPA_DIST_DIR")
    if override:
        candidates.append(Path(override).resolve())
    candidates.append(_DEPLOYED_SPA_DIST)
    candidates.append(_DEFAULT_SPA_DIST)

    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    # Nothing found yet (e.g. SPA not built locally). Return the most specific
    # candidate so the 503 in main.py points at the intended location.
    return candidates[0]
