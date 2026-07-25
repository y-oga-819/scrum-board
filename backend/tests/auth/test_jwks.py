"""JWKS プロバイダのキャッシュ挙動（V-1「鍵はキャッシュする」）。"""

from __future__ import annotations

import json

import pytest

from app.auth.jwks import CachingJwksProvider

from .keys import SigningKeypair


def _jwks_document(keypair: SigningKeypair) -> dict:
    """テスト鍵ペアの公開鍵を JWKS ドキュメント形式で返す。"""
    from jwt.algorithms import RSAAlgorithm

    jwk = json.loads(RSAAlgorithm.to_jwk(keypair.public_key))
    jwk["kid"] = keypair.kid
    jwk["kty"] = "RSA"
    return {"keys": [jwk]}


class _CountingClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


def _provider_with_recorder(document, clock):
    """httpx.get を叩かず、呼び出し回数を数える差し替えを仕込んだプロバイダ。"""
    calls = {"count": 0}

    provider = CachingJwksProvider("https://example/jwks", ttl_seconds=100.0, now=clock)

    def fake_refresh() -> None:
        calls["count"] += 1
        from app.auth.jwks import _parse_jwks

        provider._keys = _parse_jwks(document)
        provider._fetched_at = clock()

    provider._refresh = fake_refresh  # type: ignore[method-assign]
    return provider, calls


def test_fetches_once_then_serves_from_cache() -> None:
    kp = SigningKeypair()
    clock = _CountingClock()
    provider, calls = _provider_with_recorder(_jwks_document(kp), clock)

    provider.get_signing_key(kp.kid)
    provider.get_signing_key(kp.kid)
    provider.get_signing_key(kp.kid)

    # 既知の kid・TTL 内なら 1 度しか取りにいかない（最頻出処理を外部往復に律速させない）。
    assert calls["count"] == 1


def test_refetches_after_ttl_expires() -> None:
    kp = SigningKeypair()
    clock = _CountingClock()
    provider, calls = _provider_with_recorder(_jwks_document(kp), clock)

    provider.get_signing_key(kp.kid)
    clock.value = 200.0  # TTL(100) を超過
    provider.get_signing_key(kp.kid)

    assert calls["count"] == 2


def test_refetches_on_unknown_kid_then_raises_if_still_absent() -> None:
    # 鍵ローテーション直後に未知の kid が来たら、TTL 内でも一度だけ取り直す。
    kp = SigningKeypair()
    clock = _CountingClock()
    provider, calls = _provider_with_recorder(_jwks_document(kp), clock)

    provider.get_signing_key(kp.kid)  # 1 回目
    with pytest.raises(KeyError):
        provider.get_signing_key("rotated-away-kid")  # 取り直すが見つからない

    assert calls["count"] == 2
