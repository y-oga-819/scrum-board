"""JWKS（署名公開鍵）の取得とキャッシュ。

V-1（署名検証）は Entra ID の JWKS エンドポイントが公開する RSA 公開鍵で行う。
**鍵はキャッシュする**（提案書 08章 V-1）。毎リクエストで JWKS を取りにいくと、
最頻出の処理が外部往復に律速され、F1 の 1 日 60 CPU 分を無駄に食う。

鍵のローテーション（Entra は定期的に kid を入れ替える）に追従するため、
**未知の kid を要求されたときだけ**再取得する。TTL でも定期的に失効させ、
撤去された鍵をいつまでも握り続けないようにする。
"""

from __future__ import annotations

import json
import time
from typing import Any, Protocol

import httpx
import jwt


class JwksProvider(Protocol):
    """kid から署名検証用の公開鍵を返すポート。

    本番は :class:`CachingJwksProvider`（JWKS を取得）。テストは静的な実装に
    差し替え、実テナントへ繋がずに V-1 を検証する。
    """

    def get_signing_key(self, kid: str) -> Any:
        """指定 kid の公開鍵を返す。見つからなければ :class:`KeyError`。"""
        ...


class CachingJwksProvider:
    """JWKS を取得し、kid ごとに公開鍵をキャッシュする実装。"""

    def __init__(
        self,
        jwks_uri: str,
        *,
        ttl_seconds: float = 3600.0,
        timeout_seconds: float = 5.0,
        now: Any = time.monotonic,
    ) -> None:
        self._jwks_uri = jwks_uri
        self._ttl = ttl_seconds
        self._timeout = timeout_seconds
        self._now = now
        self._keys: dict[str, Any] = {}
        self._fetched_at: float | None = None

    def get_signing_key(self, kid: str) -> Any:
        # 期限切れ、または未知の kid のときだけ取りにいく。既知の kid が
        # キャッシュにある通常経路では外部往復を発生させない（V-1: 鍵はキャッシュ）。
        if self._is_expired() or kid not in self._keys:
            self._refresh()
        key = self._keys.get(kid)
        if key is None:
            raise KeyError(kid)
        return key

    def _is_expired(self) -> bool:
        if self._fetched_at is None:
            return True
        return (self._now() - self._fetched_at) >= self._ttl

    def _refresh(self) -> None:
        response = httpx.get(self._jwks_uri, timeout=self._timeout)
        response.raise_for_status()
        self._keys = _parse_jwks(response.json())
        self._fetched_at = self._now()


def _parse_jwks(document: dict[str, Any]) -> dict[str, Any]:
    """JWKS ドキュメント（``{"keys": [...]}``）を ``{kid: 公開鍵}`` に変換する。"""
    keys: dict[str, Any] = {}
    for jwk in document.get("keys", []):
        kid = jwk.get("kid")
        if not kid:
            continue
        # RSA 以外（EC 等）は自作 API の RS256 では使わないため無視する。
        if jwk.get("kty") != "RSA":
            continue
        keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
    return keys
