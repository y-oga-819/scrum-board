"""「現在のユーザーは誰か」を解決するポート（D-21）。

責務を単一の依存として切り出す。実装を **差し替え** で表現し、``if guest:`` の
分岐をハンドラに撒かない（D-21「分岐ではなく差し替えで表現すること」）。

  ├─ Entra ID 実装 : トークンを検証（V-1〜V-4）し oid から user を引く   ← 本番
  ├─ テスト用実装  : テスト鍵で署名したトークン／固定ユーザー            ← 層2テスト
  └─ ゲスト実装    : 固定の usr_guest を返す                            ← 任意（B-14）

B-04 時点ではデータ層が無い（認可は B-09 以降）。したがって解決結果は
トークンのクレームから組み立てた identity のみで、Cosmos の ``user`` 参照は
まだ行わない。B-09/B-10 で「oid から user/member を引く」処理がこの実装の中に増える。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import Request

from .errors import InvalidTokenError
from .jwks import JwksProvider
from .settings import AuthSettings
from .token import verify_token

_BEARER_PREFIX = "bearer "


@dataclass(frozen=True)
class AuthenticatedUser:
    """検証済みトークンから得た、現在のユーザーの identity。

    ``is_guest`` は ``GET /api/me`` が「ゲストと実ユーザーで同じ形」を返すための旗
    （D-21）。Entra 実装では常に ``False``。ゲスト経路（B-14・任意）を採るなら、
    その resolver 実装だけがここを ``True`` にする（``if guest:`` をハンドラに撒かない）。
    """

    oid: str
    display_name: str | None = None
    email: str | None = None
    tenant_id: str | None = None
    scopes: tuple[str, ...] = ()
    is_guest: bool = False


class CurrentUserResolver(Protocol):
    """リクエストから現在のユーザーを解決するポート。"""

    async def resolve(self, request: Request) -> AuthenticatedUser:
        """解決できなければ :class:`InvalidTokenError`。"""
        ...


class EntraCurrentUserResolver:
    """本番実装。``Authorization: Bearer`` を検証して identity を組み立てる。"""

    def __init__(self, settings: AuthSettings, jwks: JwksProvider) -> None:
        self._settings = settings
        self._jwks = jwks

    async def resolve(self, request: Request) -> AuthenticatedUser:
        token = _bearer_token(request)
        verified = verify_token(token, settings=self._settings, jwks=self._jwks)
        claims = verified.claims
        return AuthenticatedUser(
            oid=str(claims["oid"]),  # verify_token が存在を保証している
            display_name=claims.get("name"),
            # v2 の access token では preferred_username にサインイン名（多くはメール）。
            email=claims.get("preferred_username") or claims.get("email"),
            tenant_id=claims.get("tid"),
            scopes=tuple(str(claims.get("scp", "")).split()),
        )


def _bearer_token(request: Request) -> str:
    """``Authorization: Bearer <token>`` からトークンを取り出す。"""
    header = request.headers.get("Authorization")
    if not header:
        raise InvalidTokenError("missing Authorization header")
    if not header.lower().startswith(_BEARER_PREFIX):
        raise InvalidTokenError("Authorization header is not a Bearer token")
    token = header[len(_BEARER_PREFIX) :].strip()
    if not token:
        raise InvalidTokenError("empty Bearer token")
    return token
