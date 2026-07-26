"""FastAPI application entrypoint.

The same process serves two things from one origin:

* the JSON API under ``/api`` (see :mod:`app.api`), and
* the built Angular SPA (everything else), with a client-side-routing
  fallback so deep links resolve to ``index.html``.

Co-hosting keeps the deployment to a single App Service and avoids CORS
entirely (design proposal, ch. 09).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .api import router as api_router
from .config import spa_dist_dir
from .data.migrations import run_migrations
from .data.settings import build_repository, cosmos_settings_from_env, create_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """アプリのライフタイムで Cosmos クライアントを **1個だけ**持つ。

    ``CosmosClient`` はリクエストごとに作るとトポロジ探索と TLS ハンドシェイクが
    毎回走る。ここで一度だけ生成して全リクエストで使い回し（コネクションプールは
    クライアントが内部で共有する）、shutdown で ``close()`` する。構築済みリポジトリは
    ``app.state.repository`` に置き、ハンドラはそこから取る（配線は B-09 以降）。

    認証だけの M1・ローカル・テストでは Cosmos が未構成のため、**何もせず DB 無しで
    起動する**（``app.state.repository`` は ``None``）。DB を要する工程で
    ``COSMOS_ENDPOINT`` / ``COSMOS_KEY`` / ``COSMOS_DATABASE`` を与えると点灯する。
    """
    settings = cosmos_settings_from_env()
    client = None
    application.state.repository = None
    if settings.is_configured:
        client = create_client(settings)
        # コンテナを冪等に用意し（B-07）、未適用のマイグレーションだけを順に適用する
        # （B-08）。適用済みバージョンは _system に記録されるため、再デプロイでは何も
        # 起きない（実データを設定値で上書きしない。D-21）。
        repository = build_repository(client, settings)
        application.state.repository = repository
        applied = run_migrations(repository)
        if applied:
            logger.info("マイグレーションを適用しました: %s", ", ".join(applied))
        logger.info("Cosmos に接続しました（リポジトリを app.state に配置）。")
    else:
        logger.info("Cosmos 未構成のため DB 無しで起動します（M1 認証のみ）。")
    try:
        yield
    finally:
        if client is not None:
            client.close()


app = FastAPI(title="Scrum Board", lifespan=lifespan)
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
