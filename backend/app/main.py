"""FastAPI application entrypoint.

The same process serves two things from one origin:

* the JSON API under ``/api`` (see :mod:`app.api`), and
* the built Angular SPA (everything else), with a client-side-routing
  fallback so deep links resolve to ``index.html``.

Co-hosting keeps the deployment to a single App Service and avoids CORS
entirely (design proposal, ch. 09).
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .api import router as api_router
from .config import spa_dist_dir

app = FastAPI(title="Scrum Board")
app.include_router(api_router)


def _mount_spa(application: FastAPI) -> None:
    """Serve the built SPA, falling back to index.html for client routes.

    If the SPA has not been built yet (fresh checkout, no ``ng build``), we
    respond with a clear 503 instead of a bare 404 so the developer knows to
    build the frontend rather than assuming the backend is broken.
    """
    dist = spa_dist_dir()
    index = dist / "index.html"

    @application.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:
        # /api belongs to the backend. An unknown API path must 404, not fall
        # through to index.html (which would make typo'd endpoints look 200 OK).
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        if not index.is_file():
            raise HTTPException(
                status_code=503,
                detail="SPA is not built yet. Run `make build-frontend` (or `ng build`).",
            )
        candidate = (dist / full_path).resolve()
        # Only serve files that exist inside dist; otherwise fall back to the
        # SPA entrypoint so Angular's router handles the path.
        if full_path and candidate.is_file() and dist in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


_mount_spa(app)
