"""認証（トークン検証）とユーザー解決ポート。

主題は「Easy Auth を使わない Entra ID の認証」（D-21）。MSAL が発行した
アクセストークンを FastAPI 側で検証し（V-1〜V-4）、現在のユーザーを解決する。
"""

from __future__ import annotations

from .dependencies import current_user, get_current_user_resolver
from .errors import InvalidTokenError
from .resolver import (
    AuthenticatedUser,
    CurrentUserResolver,
    EntraCurrentUserResolver,
)
from .settings import AuthSettings, auth_settings_from_env
from .token import VerifiedToken, verify_token

__all__ = [
    "AuthSettings",
    "AuthenticatedUser",
    "CurrentUserResolver",
    "EntraCurrentUserResolver",
    "InvalidTokenError",
    "VerifiedToken",
    "auth_settings_from_env",
    "current_user",
    "get_current_user_resolver",
    "verify_token",
]
