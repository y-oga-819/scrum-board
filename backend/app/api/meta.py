"""横断的な API ルート（health / me）。

プロダクトスコープに属さない、アプリ全体の入口となるルートを持つ。個々のリソース
（PBI・タスク・スプリント…）の CRUD は :mod:`app.api.pbis` のように**リソースごとの
モジュール**へ分ける（:mod:`app.api` パッケージが束ねる）。

* ``GET /api/health`` — 公開。フロントとAPIが同一オリジンで配信されている
  （CORS 不要）ことを SPA が示すための疎通確認（B-01）。
* ``GET /api/me`` — 認証必須。MSAL のアクセストークンを検証（V-1〜V-4）し、
  **API が確かめた ``oid``** と、初回サインインのブートストラップ（user 作成・
  サンドボックスへの自動参加）を経た **所属プロダクト一覧**を返す（B-10・D-21）。
  フロントはこの ``products`` を使い、``productId`` をハードコードしない。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..auth import AuthenticatedUser, current_user, e2e_bypass_from_env
from ..config import SERVICE_NAME
from ..data import Repository
from ..onboarding import ensure_bootstrapped, list_products

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


class ProductSummary(BaseModel):
    """所属一覧の1要素。フロントのプロダクトセレクタが並べる（D-21）。"""

    productId: str
    name: str
    role: str


class MeResponse(BaseModel):
    """認証済みユーザーと所属プロダクト一覧（B-10・D-21）。

    ``products`` が空＝どのプロダクトにも属していない（未招待ユーザーに見せる画面の
    判定に使える）。``isGuest`` はゲストと実ユーザーで同じ形を保つための旗。
    """

    oid: str
    displayName: str | None = None
    isGuest: bool = False
    products: list[ProductSummary] = []


def _optional_repository(request: Request) -> Repository | None:
    """lifespan が ``app.state`` に置いたリポジトリを取り出す（無ければ ``None``）。

    認可（:func:`app.authz.get_repository`）は DB 無しを 503 にするが、``/api/me`` は
    **DB 無しでも認証だけは成立させたい**（M1 の認証 PoC は Cosmos を要さない — D-21）。
    そのため 503 にせず ``None`` を返し、所属は空一覧にする。
    """
    return getattr(request.app.state, "repository", None)


@router.get("/me")
def me(
    request: Request,
    user: AuthenticatedUser = Depends(current_user),
) -> MeResponse:
    # ここに来た時点でトークンは検証済み（current_user が 401 を投げる）。
    # 所属一覧はデータ層を要する。DB を触るため async ではなく def で書き、
    # ブロッキング I/O をスレッドプールに逃がす（repository.py の方針）。
    repository = _optional_repository(request)
    products: list[ProductSummary] = []
    if repository is not None:
        # 初回サインインなら user とサンドボックス member を作る（冪等・409 は握りつぶす）。
        # これで「サインインできた人には必ず居場所がある」＝ 403 で詰まらない（D-21）。
        # E2E では隔離のためサンドボックス自動参加をスキップし、prd_test_<runId> の
        # member だけにする（products を 1 件に絞る — D-22）。
        ensure_bootstrapped(repository, user, skip_sandbox=e2e_bypass_from_env().is_active)
        products = [
            ProductSummary(productId=p.product_id, name=p.name, role=p.role.value)
            for p in list_products(repository, user.oid)
        ]
    # 画面には API が検証した oid を返す（フロントの表示名クレームではなく、
    # サーバーが署名・aud・iss・scp を確かめた値であることに意味がある）。
    return MeResponse(
        oid=user.oid,
        displayName=user.display_name,
        isGuest=user.is_guest,
        products=products,
    )
