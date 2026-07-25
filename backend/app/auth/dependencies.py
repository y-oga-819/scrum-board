"""FastAPI への配線。

ルートは ``current_user`` に依存するだけで認証が掛かる。ポートの差し替えは
``get_current_user_resolver`` を通して行う（テストは ``app.dependency_overrides``
で固定ユーザーを返す実装に差し替える。ゲスト経路 B-14 も同じ差し替えで足りる）。
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request, status

from .errors import InvalidTokenError
from .jwks import CachingJwksProvider, JwksProvider
from .resolver import AuthenticatedUser, CurrentUserResolver, EntraCurrentUserResolver
from .settings import AuthSettings, auth_settings_from_env

logger = logging.getLogger(__name__)

# JWKS プロバイダは鍵をキャッシュするため、プロセス内で使い回す（jwks_uri 単位）。
_jwks_providers: dict[str, JwksProvider] = {}


def _jwks_for(settings: AuthSettings) -> JwksProvider:
    provider = _jwks_providers.get(settings.jwks_uri)
    if provider is None:
        provider = CachingJwksProvider(settings.jwks_uri)
        _jwks_providers[settings.jwks_uri] = provider
    return provider


def get_current_user_resolver() -> CurrentUserResolver:
    """既定は Entra 実装。テスト／ゲストは ``dependency_overrides`` で差し替える。"""
    settings = auth_settings_from_env()
    if not settings.is_configured:
        # B-02 の実値待ち。黙って全 401 にせず、設定漏れだと分かるよう警告する
        # （フロントの environment.ts と対になる挙動）。
        logger.warning(
            "Entra ID の TENANT/CLIENT ID が未設定です。ENTRA_TENANT_ID / "
            "ENTRA_CLIENT_ID を B-02 の実値に設定するまで /api/me は 401 になります。",
        )
    return EntraCurrentUserResolver(settings, _jwks_for(settings))


async def current_user(
    request: Request,
    resolver: CurrentUserResolver = Depends(get_current_user_resolver),
) -> AuthenticatedUser:
    """認証必須エンドポイントの依存。失敗は 401（D-20）。"""
    try:
        return await resolver.resolve(request)
    except InvalidTokenError:
        # 原因（署名不正・aud 不一致・スコープ欠落…）は応答に出さない。ログには
        # resolver 側で必要に応じて残す。利用者には汎用の 401 を返す。
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
