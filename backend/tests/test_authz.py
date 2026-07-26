"""``require_member`` 認可依存（B-09・D-21）の統合テスト。

本番の product スコープ・エンドポイントは B-15 以降で入る。ここではその土台となる
依存を、テスト専用の probe ルート（``/api/products/{product_id}/_probe``）に載せて、
**非メンバーは 403 / メンバーは通過** を端から端まで確かめる。
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user_resolver
from app.auth.resolver import AuthenticatedUser
from app.authz import Membership, require_member
from app.data.fake import InMemoryRepository
from app.data.members import Role, create_member

MEMBER_OID = "oid-member"
STRANGER_OID = "oid-stranger"
PRODUCT = "prd_sandbox"


class _StubResolver:
    """トークン検証を通さず固定 oid を返す（層2の使い方。test_me_endpoint と同型）。"""

    def __init__(self, oid: str) -> None:
        self._oid = oid

    async def resolve(self, request) -> AuthenticatedUser:  # noqa: ANN001
        return AuthenticatedUser(oid=self._oid)


def _build_app(repository: InMemoryRepository | None) -> FastAPI:
    app = FastAPI()
    app.state.repository = repository

    @app.get("/api/products/{product_id}/_probe")
    def probe(membership: Membership = Depends(require_member)) -> dict[str, str]:
        return {
            "productId": membership.product_id,
            "oid": membership.oid,
            "role": membership.role.value,
        }

    return app


def _client(app: FastAPI, *, as_oid: str) -> TestClient:
    app.dependency_overrides[get_current_user_resolver] = lambda: _StubResolver(as_oid)
    return TestClient(app)


@pytest.fixture
def repo() -> InMemoryRepository:
    repository = InMemoryRepository()
    create_member(
        repository, product_id=PRODUCT, oid=MEMBER_OID, role=Role.MEMBER, actor=MEMBER_OID
    )
    return repository


def test_member_passes_and_role_is_exposed(repo: InMemoryRepository) -> None:
    client = _client(_build_app(repo), as_oid=MEMBER_OID)

    res = client.get(f"/api/products/{PRODUCT}/_probe")

    assert res.status_code == 200
    assert res.json() == {"productId": PRODUCT, "oid": MEMBER_OID, "role": "member"}


def test_non_member_is_forbidden(repo: InMemoryRepository) -> None:
    # 認証は済んでいるが member ではない → 403（B-09 の中核）。
    client = _client(_build_app(repo), as_oid=STRANGER_OID)

    res = client.get(f"/api/products/{PRODUCT}/_probe")

    assert res.status_code == 403


def test_member_of_another_product_is_forbidden(repo: InMemoryRepository) -> None:
    # サンドボックスの member 資格で本番プロダクトを叩いても 403（パーティション境界）。
    client = _client(_build_app(repo), as_oid=MEMBER_OID)

    res = client.get("/api/products/prd_scrum_board/_probe")

    assert res.status_code == 403


def test_unauthenticated_is_401_not_403(repo: InMemoryRepository) -> None:
    # 認可より先に認証が効く。トークンなしは 401（current_user）。
    app = _build_app(repo)
    res = TestClient(app).get(f"/api/products/{PRODUCT}/_probe")

    assert res.status_code == 401
    assert res.headers.get("WWW-Authenticate") == "Bearer"


def test_admin_role_is_exposed() -> None:
    repository = InMemoryRepository()
    create_member(repository, product_id=PRODUCT, oid=MEMBER_OID, role=Role.ADMIN, actor=MEMBER_OID)
    client = _client(_build_app(repository), as_oid=MEMBER_OID)

    res = client.get(f"/api/products/{PRODUCT}/_probe")

    assert res.json()["role"] == "admin"


def test_missing_repository_is_503() -> None:
    # DB 無しで起動した状態（M1 相当）では認可判定が成立しない → 503。
    client = _client(_build_app(None), as_oid=MEMBER_OID)

    res = client.get(f"/api/products/{PRODUCT}/_probe")

    assert res.status_code == 503
