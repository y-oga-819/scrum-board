"""テスト用の RSA 鍵ペアとトークン発行ヘルパー。

**実テナントには一切繋がない**（B-04 完了条件・D-19）。テスト鍵で自前に署名した
トークンと、その公開鍵を返す JWKS スタブで V-1〜V-4 を検証する。ここに Entra を
模した最小の道具立てを閉じ込め、各テストは「どのクレームが欠けると弾かれるか」に集中する。
"""

from __future__ import annotations

import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.jwks import JwksProvider
from app.auth.settings import ACCESS_SCOPE, AuthSettings

TEST_TENANT_ID = "11111111-1111-1111-1111-111111111111"
TEST_CLIENT_ID = "22222222-2222-2222-2222-222222222222"
TEST_KID = "test-key-1"
TEST_OID = "00000000-aaaa-bbbb-cccc-000000000001"

TEST_SETTINGS = AuthSettings(tenant_id=TEST_TENANT_ID, client_id=TEST_CLIENT_ID)


class SigningKeypair:
    """1 つの RSA 鍵ペア。トークン署名（秘密鍵）と JWKS 提供（公開鍵）を担う。"""

    def __init__(self, kid: str = TEST_KID) -> None:
        self.kid = kid
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    @property
    def public_key(self) -> Any:
        return self._private_key.public_key()

    def mint(
        self,
        *,
        oid: str | None = TEST_OID,
        audience: str | None = TEST_CLIENT_ID,
        issuer: str | None = TEST_SETTINGS.issuer,
        scope: str | None = ACCESS_SCOPE,
        name: str | None = "テスト ユーザー",
        preferred_username: str | None = "test.user@example.com",
        expires_in: int | None = 3600,
        extra_claims: dict[str, Any] | None = None,
        kid: str | None = None,
    ) -> str:
        """指定のクレームでトークンを署名して返す。省略時は「妥当なトークン」。

        個々の引数を ``None`` にすると、そのクレームを落として検証失敗を作れる
        （例: ``scope=None`` で V-4、``audience="other"`` で V-2、
        ``expires_in=None`` で exp なし）。
        """
        now = int(time.time())
        claims: dict[str, Any] = {"iat": now, "nbf": now}
        if expires_in is not None:
            claims["exp"] = now + expires_in
        if oid is not None:
            claims["oid"] = oid
        if audience is not None:
            claims["aud"] = audience
        if issuer is not None:
            claims["iss"] = issuer
        if scope is not None:
            claims["scp"] = scope
        if name is not None:
            claims["name"] = name
        if preferred_username is not None:
            claims["preferred_username"] = preferred_username
        if extra_claims:
            claims.update(extra_claims)
        return jwt.encode(
            claims,
            self._private_key,
            algorithm="RS256",
            headers={"kid": kid or self.kid},
        )


class StaticJwksProvider(JwksProvider):
    """固定の公開鍵だけを返す JWKS スタブ。"""

    def __init__(self, keys: dict[str, Any]) -> None:
        self._keys = keys

    def get_signing_key(self, kid: str) -> Any:
        return self._keys[kid]  # 未知なら KeyError（本番と同じ契約）


def static_jwks(keypair: SigningKeypair) -> StaticJwksProvider:
    return StaticJwksProvider({keypair.kid: keypair.public_key})
