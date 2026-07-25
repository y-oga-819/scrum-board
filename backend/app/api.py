"""API routes.

Everything the frontend talks to lives under ``/api``.

* ``GET /api/health`` — 公開。フロントとAPIが同一オリジンで配信されている
  （CORS 不要）ことを SPA が示すための疎通確認（B-01）。
* ``GET /api/me`` — 認証必須。MSAL のアクセストークンを検証（V-1〜V-4）し、
  **API が確かめた ``oid``** を返す。B-04 の「端から端まで通ったことの可視化」。
  所属プロダクト一覧（D-21 の完全な ``/api/me``）はデータ層が要るため B-10 で足す。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .auth import AuthenticatedUser, current_user
from .config import SERVICE_NAME

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


class MeResponse(BaseModel):
    """認証済みユーザーの最小表現。B-10 で ``products`` 等が加わる。"""

    oid: str
    displayName: str | None = None


@router.get("/me")
async def me(user: AuthenticatedUser = Depends(current_user)) -> MeResponse:
    # ここに来た時点でトークンは検証済み（current_user が 401 を投げる）。
    # 画面には API が検証した oid を返す（フロントの表示名クレームではなく、
    # サーバーが署名・aud・iss・scp を確かめた値であることに意味がある）。
    return MeResponse(oid=user.oid, displayName=user.display_name)
