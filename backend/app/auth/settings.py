"""認証の構成値（バックエンド）。

Entra ID のアプリ登録が発行する **テナント ID / クライアント ID** から、
トークン検証に必要な派生値（issuer・JWKS エンドポイント・audience・要求スコープ）を
すべて導く。フロントの ``environment.ts`` と対になる（同一のアプリ登録を共有する）。

値は環境変数から読む。B-02（Entra ID にアプリを登録する）が発行する実値を
``ENTRA_TENANT_ID`` / ``ENTRA_CLIENT_ID`` に入れると、そのまま検証が通る。
それまでは未設定で、実トークンは来ない（フロントもサインインできない）。
テストは実テナントに繋がず、この ``AuthSettings`` を直接組み立てて差し込む。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# 提案書 08章・B-04 V-4。自作 API を呼ぶアクセストークンが持つべきスコープ。
ACCESS_SCOPE = "access_as_user"


@dataclass(frozen=True)
class AuthSettings:
    """トークン検証に必要な値の一式（テナント/クライアントIDから導出済み）。"""

    tenant_id: str
    client_id: str

    @property
    def issuer(self) -> str:
        """V-3。v2 トークンの発行者 URL。"""
        return f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"

    @property
    def jwks_uri(self) -> str:
        """V-1。テナントの署名公開鍵（JWKS）エンドポイント（v2）。"""
        return f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"

    @property
    def audience(self) -> str:
        """V-2。``requestedAccessTokenVersion: 2`` の自作 API では aud = クライアント ID。"""
        return self.client_id

    @property
    def required_scope(self) -> str:
        """V-4。``scp`` に含まれていなければならないスコープ。"""
        return ACCESS_SCOPE

    @property
    def is_configured(self) -> bool:
        """B-02 の実値が入っているか（両方が非空か）。"""
        return bool(self.tenant_id) and bool(self.client_id)


def auth_settings_from_env() -> AuthSettings:
    """環境変数から ``AuthSettings`` を作る。未設定なら空文字（fail closed）。

    未設定のまま起動した場合、issuer/audience が空になるため実トークンは
    すべて検証に失敗する（安全側に倒れる）。設定漏れであることが分かるよう、
    利用側（``dependencies``）が起動時に警告する。
    """
    return AuthSettings(
        tenant_id=os.environ.get("ENTRA_TENANT_ID", ""),
        client_id=os.environ.get("ENTRA_CLIENT_ID", ""),
    )
