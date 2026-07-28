#!/usr/bin/env python3
"""開発用の使い捨てハーネス（``make dev-fake``）。

**サインインも Cosmos も無しで API を叩くための開発専用サーバー。** 本番の入口は
:mod:`app.main`（``make run`` / ``make dev``）であり、これはそれとは別物の**スモーク
確認用**エントリポイント。本番のルータ・エラーハンドラ・OpenAPI をそのまま組むので、
ハンドラ・認可・problem+json の挙動は実物と同じものを通る。差し替えるのは2点だけ:

* **データ層** — :class:`~app.data.fake.InMemoryRepository` を ``app.state`` に置く
  （プロセス内・非永続。**再起動で消える**）。起動時に実マイグレーションを流して
  ``prd_sandbox`` / ``prd_scrum_board`` を用意し、開発ユーザーを両方の member にする。
* **認証** — ``get_current_user_resolver`` を固定 oid を返すスタブに差し替える
  （``dependency_overrides``。テストと同じ手法）。

.. warning::

   これは **B-14（ゲストログイン）ではない**。B-14 は本番アプリ内の
   env で制御される resolver 実装（既定 OFF）で、実データ経路をそのまま使う正式な
   仕組み。こちらは ``dependency_overrides`` に頼る**開発機だけの近道**で、本番の入口
   （:mod:`app.main`）には一切影響しない。永続確認や本番同等の検証は B-14＋Cosmos で行う。

    make dev-fake                      # 127.0.0.1:8000 で起動
    DEV_FAKE_OID=oid-x PORT=9000 make dev-fake

起動後は member 済みユーザーとして即座に叩ける::

    curl -X POST localhost:8000/api/products/prd_sandbox/pbis \
      -H 'Content-Type: application/json' -d '{"title":"ためし"}'
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ``app`` を import できるよう backend/ を sys.path に載せる（実行時の cwd に依存しない）。
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi import FastAPI, Request  # noqa: E402

from app.api import routers  # noqa: E402
from app.auth import get_current_user_resolver  # noqa: E402
from app.auth.resolver import AuthenticatedUser  # noqa: E402
from app.data.fake import InMemoryRepository  # noqa: E402
from app.data.members import Role, create_member  # noqa: E402
from app.data.migrations import run_migrations  # noqa: E402
from app.data.products import SANDBOX_PRODUCT_ID, SCRUM_BOARD_PRODUCT_ID  # noqa: E402
from app.data.repository import Repository  # noqa: E402
from app.http import install_error_handlers, install_openapi  # noqa: E402

# 開発ユーザーの identity。実 Entra oid の代わりに使う固定値（env で上書き可）。
DEV_OID = os.environ.get("DEV_FAKE_OID", "oid-dev-local")
DEV_DISPLAY_NAME = os.environ.get("DEV_FAKE_NAME", "Dev User")

# member を仕込むプロダクト（マイグレーションが作る2つ）。両方 admin にして、
# 将来の管理操作（B-33）まで手元で試せるようにする。
_DEV_PRODUCTS = (SANDBOX_PRODUCT_ID, SCRUM_BOARD_PRODUCT_ID)


class _StubResolver:
    """トークン検証を通さず固定の開発ユーザーを返す（テストと同じ差し替え手法）。"""

    async def resolve(self, request: Request) -> AuthenticatedUser:
        return AuthenticatedUser(oid=DEV_OID, display_name=DEV_DISPLAY_NAME)


def build_repository() -> InMemoryRepository:
    """本番同様にマイグレーション済みの、開発ユーザーが member のフェイク DB を作る。

    実の :func:`~app.data.migrations.run_migrations` を流すので、プロダクトは本番と同じ
    ``prd_sandbox`` / ``prd_scrum_board`` になる（設定値がずれない）。そこへ開発ユーザーを
    admin として登録し、両プロダクトを触れる状態にする。
    """
    repo = InMemoryRepository()
    run_migrations(repo)
    for product_id in _DEV_PRODUCTS:
        create_member(repo, product_id=product_id, oid=DEV_OID, role=Role.ADMIN, actor=DEV_OID)
    return repo


def build_app(repo: Repository | None = None) -> FastAPI:
    """本番の部品（ルータ・エラーハンドラ・OpenAPI）で組んだ開発用アプリを返す。

    :mod:`app.main` と**同じ組み立てブロック**を使うので、ルート集合や problem+json の
    挙動が実物からずれにくい。違いはデータ層（フェイク）と認証（スタブ）の2点だけ。
    """
    if repo is None:
        repo = build_repository()
    app = FastAPI(title="Scrum Board (dev-fake)")
    install_error_handlers(app)
    install_openapi(app)
    for router in routers:
        app.include_router(router)
    app.state.repository = repo
    app.dependency_overrides[get_current_user_resolver] = lambda: _StubResolver()
    return app


def _banner(host: str, port: int) -> str:
    return (
        "\n".join(
            [
                "── dev-fake（開発用・非永続・認証なし）─────────────────────────",
                f"  URL       : http://{host}:{port}",
                f"  user oid  : {DEV_OID}（{DEV_DISPLAY_NAME}・両プロダクトの admin）",
                f"  products  : {', '.join(_DEV_PRODUCTS)}",
                "  例        : "
                f"curl -X POST http://{host}:{port}/api/products/{SANDBOX_PRODUCT_ID}/pbis "
                "-H 'Content-Type: application/json' -d '{\"title\":\"ためし\"}'",
                "  ※ データはメモリ上。停止で消える。本番の入口は make run / make dev。",
                "────────────────────────────────────────────────────────────",
            ]
        )
        + "\n"
    )


def main() -> int:
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(_banner(host, port))
    uvicorn.run(build_app(), host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
