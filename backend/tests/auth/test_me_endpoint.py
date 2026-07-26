"""``GET /api/me`` の統合テスト。

ポートの差し替え（``dependency_overrides``）と、Entra 実装＋テスト鍵での
端から端まで（改ざん → 401 を含む）を確認する。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user_resolver
from app.auth.resolver import AuthenticatedUser, EntraCurrentUserResolver
from app.main import app

from .keys import TEST_OID, TEST_SETTINGS, SigningKeypair, static_jwks


@pytest.fixture
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# --- 認証の有無 --------------------------------------------------------------


def test_me_requires_authentication(client: TestClient) -> None:
    # トークンなしのアクセスは 401（D-20: 401 は未認証・トークン不正）。
    res = client.get("/api/me")

    assert res.status_code == 401
    assert res.headers.get("WWW-Authenticate") == "Bearer"


def test_health_stays_public(client: TestClient) -> None:
    # 認証を足しても疎通用のヘルスチェックは公開のまま（B-01 の不変）。
    assert client.get("/api/health").status_code == 200


# --- ポートの差し替え（層2の使い方） -----------------------------------------


def test_me_returns_oid_with_stubbed_resolver(client: TestClient) -> None:
    # ハンドラのテストはトークン検証を通さず、固定ユーザーを返す実装に差し替える
    # （D-21「分岐ではなく差し替えで表現する」）。
    class StubResolver:
        async def resolve(self, request) -> AuthenticatedUser:
            return AuthenticatedUser(oid="fixed-oid", display_name="Fixed User")

    app.dependency_overrides[get_current_user_resolver] = lambda: StubResolver()

    res = client.get("/api/me")

    assert res.status_code == 200
    assert res.json() == {"oid": "fixed-oid", "displayName": "Fixed User"}


# --- Entra 実装＋テスト鍵での端から端まで ------------------------------------


def _bind_entra_resolver(keypair: SigningKeypair) -> None:
    resolver = EntraCurrentUserResolver(TEST_SETTINGS, static_jwks(keypair))
    app.dependency_overrides[get_current_user_resolver] = lambda: resolver


def test_me_end_to_end_with_valid_token(client: TestClient) -> None:
    kp = SigningKeypair()
    _bind_entra_resolver(kp)

    res = client.get("/api/me", headers={"Authorization": f"Bearer {kp.mint()}"})

    assert res.status_code == 200
    # API が検証した oid が返る（B-04: 端から端まで通ったことの可視化）。
    assert res.json()["oid"] == TEST_OID


def test_me_rejects_tampered_token_end_to_end(client: TestClient) -> None:
    kp = SigningKeypair()
    _bind_entra_resolver(kp)
    header, payload, signature = kp.mint().split(".")
    tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    tampered = ".".join([header, tampered_payload, signature])

    res = client.get("/api/me", headers={"Authorization": f"Bearer {tampered}"})

    assert res.status_code == 401


def test_me_rejects_missing_bearer_prefix(client: TestClient) -> None:
    kp = SigningKeypair()
    _bind_entra_resolver(kp)

    res = client.get("/api/me", headers={"Authorization": kp.mint()})

    assert res.status_code == 401
