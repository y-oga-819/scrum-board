"""``GET /api/me`` の統合テスト。

ポートの差し替え（``dependency_overrides``）と、Entra 実装＋テスト鍵での
端から端まで（改ざん → 401 を含む）を確認する。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user_resolver
from app.auth.resolver import AuthenticatedUser, EntraCurrentUserResolver
from app.data.fake import InMemoryRepository
from app.data.members import get_member
from app.data.products import SANDBOX_PRODUCT_ID, create_product
from app.data.users import get_user
from app.main import app

from .keys import TEST_OID, TEST_SETTINGS, SigningKeypair, static_jwks


@pytest.fixture
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()
    # /api/me は app.state.repository を読む。テスト間で漏らさないよう毎回消す
    # （lifespan を回さない TestClient では属性が残り続けるため）。
    if hasattr(app.state, "repository"):
        del app.state.repository


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


def _stub_resolver(user: AuthenticatedUser) -> None:
    """トークン検証を通さず固定ユーザーを返す実装に差し替える（層2の使い方）。"""

    class StubResolver:
        async def resolve(self, request) -> AuthenticatedUser:  # noqa: ANN001
            return user

    app.dependency_overrides[get_current_user_resolver] = lambda: StubResolver()


def test_me_without_db_returns_identity_with_empty_products(client: TestClient) -> None:
    # DB 未構成（M1 の認証のみ）でも /api/me は成立する。所属は空一覧（D-21）。
    _stub_resolver(AuthenticatedUser(oid="fixed-oid", display_name="Fixed User"))

    res = client.get("/api/me")

    assert res.status_code == 200
    assert res.json() == {
        "oid": "fixed-oid",
        "displayName": "Fixed User",
        "isGuest": False,
        "products": [],
    }


def test_me_bootstraps_user_and_sandbox_membership(client: TestClient) -> None:
    # DB があれば初回サインインで user とサンドボックス member が作られ、所属一覧に出る
    # （B-10 の中核。403 で詰まる経路を無くす）。
    repo = InMemoryRepository()
    create_product(repo, product_id=SANDBOX_PRODUCT_ID, name="サンドボックス", actor="sys")
    app.state.repository = repo
    _stub_resolver(AuthenticatedUser(oid="newcomer", display_name="New Comer"))

    res = client.get("/api/me")

    assert res.status_code == 200
    body = res.json()
    assert body["oid"] == "newcomer"
    assert body["isGuest"] is False
    assert body["products"] == [
        {"productId": SANDBOX_PRODUCT_ID, "name": "サンドボックス", "role": "member"}
    ]
    # 副作用: user と member が実際に作られている（冪等なので再取得で確認できる）。
    assert get_user(repo, "newcomer") is not None
    assert get_member(repo, product_id=SANDBOX_PRODUCT_ID, oid="newcomer") is not None


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
