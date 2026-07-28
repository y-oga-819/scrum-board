"""PBI CRUD エンドポイントの統合テスト（B-15・D-20）。

作成・取得・更新・論理削除が端から端まで通ること、不正な状態遷移が弾かれること、
``PATCH`` / ``DELETE`` の ``If-Match`` 必須（欠落 428・不一致 412）を確かめる。認可
（非メンバー 403・未認証 401）はテスト専用アプリに実ルータを載せて検証する。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.pbis import router as pbis_router
from app.auth import get_current_user_resolver
from app.auth.resolver import AuthenticatedUser
from app.data.fake import InMemoryRepository
from app.data.members import Role, create_member
from app.http import install_error_handlers

MEMBER_OID = "oid-member"
STRANGER_OID = "oid-stranger"
PRODUCT = "prd_sandbox"
OTHER_PRODUCT = "prd_scrum_board"
PBIS_URL = f"/api/products/{PRODUCT}/pbis"


class _StubResolver:
    """トークン検証を通さず固定 oid を返す（層2の使い方。test_authz と同型）。"""

    def __init__(self, oid: str) -> None:
        self._oid = oid

    async def resolve(self, request) -> AuthenticatedUser:  # noqa: ANN001
        return AuthenticatedUser(oid=self._oid)


def _build_app(repo: InMemoryRepository | None) -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.state.repository = repo
    app.include_router(pbis_router)
    return app


def _client(app: FastAPI, *, as_oid: str | None) -> TestClient:
    if as_oid is not None:
        app.dependency_overrides[get_current_user_resolver] = lambda: _StubResolver(as_oid)
    return TestClient(app)


@pytest.fixture
def repo() -> InMemoryRepository:
    repository = InMemoryRepository()
    create_member(
        repository, product_id=PRODUCT, oid=MEMBER_OID, role=Role.MEMBER, actor=MEMBER_OID
    )
    return repository


@pytest.fixture
def client(repo: InMemoryRepository) -> TestClient:
    return _client(_build_app(repo), as_oid=MEMBER_OID)


def _create(client: TestClient, **body: object) -> dict:
    payload = {"title": "ログイン機能", **body}
    res = client.post(PBIS_URL, json=payload)
    assert res.status_code == 201, res.text
    return res.json()


# --- 作成 --------------------------------------------------------------------


def test_create_returns_new_pbi_with_etag(client: TestClient) -> None:
    res = client.post(PBIS_URL, json={"title": "ログイン機能"})

    assert res.status_code == 201
    body = res.json()
    assert body["id"].startswith("pbi_")
    assert body["type"] == "pbi"
    assert body["productId"] == PRODUCT
    assert body["title"] == "ログイン機能"
    assert body["status"] == "new"  # 始点は必ず new（図6）
    assert body["estimate"] is None
    assert body["acceptanceCriteria"] == []
    assert body["createdBy"] == MEMBER_OID
    # 単一ドキュメント応答は ETag を返す（D-20）。本文には _etag を載せない。
    assert res.headers.get("ETag")
    assert "_etag" not in body


def test_create_accepts_optional_fields(client: TestClient) -> None:
    body = _create(
        client,
        title="検索",
        description="全文検索",
        estimate=13,
        acceptanceCriteria=[{"id": "ac1", "text": "ヒットする", "checked": False}],
    )
    assert body["description"] == "全文検索"
    assert body["estimate"] == 13
    assert body["acceptanceCriteria"][0]["text"] == "ヒットする"


def test_create_rejects_empty_title(client: TestClient) -> None:
    res = client.post(PBIS_URL, json={"title": ""})

    assert res.status_code == 422
    assert res.headers["content-type"].startswith("application/problem+json")
    assert res.json()["violations"]  # どの項目で弾いたかを機械可読に返す


def test_create_by_non_member_is_forbidden(repo: InMemoryRepository) -> None:
    client = _client(_build_app(repo), as_oid=STRANGER_OID)

    res = client.post(PBIS_URL, json={"title": "x"})

    assert res.status_code == 403


def test_create_unauthenticated_is_401(repo: InMemoryRepository) -> None:
    client = _client(_build_app(repo), as_oid=None)

    res = client.post(PBIS_URL, json={"title": "x"})

    assert res.status_code == 401
    assert res.headers.get("WWW-Authenticate") == "Bearer"


def test_create_without_db_is_503() -> None:
    client = _client(_build_app(None), as_oid=MEMBER_OID)

    res = client.post(PBIS_URL, json={"title": "x"})

    assert res.status_code == 503


# --- 取得 --------------------------------------------------------------------


def test_get_returns_pbi_with_etag(client: TestClient) -> None:
    created = _create(client)

    res = client.get(f"{PBIS_URL}/{created['id']}")

    assert res.status_code == 200
    assert res.json()["id"] == created["id"]
    assert res.headers.get("ETag")


def test_get_missing_is_404(client: TestClient) -> None:
    res = client.get(f"{PBIS_URL}/pbi_missing")

    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")


# --- 更新（If-Match と状態遷移） ---------------------------------------------


def test_patch_updates_fields(client: TestClient) -> None:
    created = _create(client)
    etag = client.get(f"{PBIS_URL}/{created['id']}").headers["ETag"]

    res = client.patch(
        f"{PBIS_URL}/{created['id']}",
        json={"title": "改称"},
        headers={"If-Match": etag},
    )

    assert res.status_code == 200
    assert res.json()["title"] == "改称"
    # 更新で版が回る（次の If-Match は新しい値になる）。
    assert res.headers["ETag"] != etag


def test_patch_without_if_match_is_428(client: TestClient) -> None:
    created = _create(client)

    res = client.patch(f"{PBIS_URL}/{created['id']}", json={"title": "x"})

    assert res.status_code == 428


def test_patch_with_stale_if_match_is_412(client: TestClient) -> None:
    created = _create(client)

    res = client.patch(
        f"{PBIS_URL}/{created['id']}",
        json={"title": "x"},
        headers={"If-Match": '"stale-etag"'},
    )

    assert res.status_code == 412


def test_patch_missing_is_404(client: TestClient) -> None:
    res = client.patch(
        f"{PBIS_URL}/pbi_missing", json={"title": "x"}, headers={"If-Match": '"any"'}
    )

    assert res.status_code == 404


def test_patch_valid_status_transition(client: TestClient) -> None:
    created = _create(client)
    etag = client.get(f"{PBIS_URL}/{created['id']}").headers["ETag"]

    res = client.patch(
        f"{PBIS_URL}/{created['id']}",
        json={"status": "ready"},  # new → ready は正当（隣接前進）
        headers={"If-Match": etag},
    )

    assert res.status_code == 200
    assert res.json()["status"] == "ready"


def test_patch_same_status_is_idempotent(client: TestClient) -> None:
    created = _create(client)
    etag = client.get(f"{PBIS_URL}/{created['id']}").headers["ETag"]

    res = client.patch(
        f"{PBIS_URL}/{created['id']}",
        json={"status": "new"},  # 据え置きは許す
        headers={"If-Match": etag},
    )

    assert res.status_code == 200


def test_patch_invalid_status_transition_is_422_with_violation(client: TestClient) -> None:
    created = _create(client)
    etag = client.get(f"{PBIS_URL}/{created['id']}").headers["ETag"]

    res = client.patch(
        f"{PBIS_URL}/{created['id']}",
        json={"status": "done"},  # new → done は飛ばし（不正）
        headers={"If-Match": etag},
    )

    assert res.status_code == 422
    body = res.json()
    assert body["type"].endswith("/errors/invalid-status-transition")
    assert body["violations"][0]["rule"] == "pbi-status-transition"
    assert body["violations"][0]["field"] == "status"
    # 弾いたのだから状態は据え置き（new のまま）。
    assert client.get(f"{PBIS_URL}/{created['id']}").json()["status"] == "new"


def test_patch_cannot_edit_completed_fields(client: TestClient) -> None:
    # completedAt / rank は PATCH モデルに無いため、送っても無視される（未知フィールド）。
    # rank の変更は専用エンドポイント（POST .../rank）が所有し、汎用 PATCH では動かさない。
    created = _create(client)
    etag = client.get(f"{PBIS_URL}/{created['id']}").headers["ETag"]

    res = client.patch(
        f"{PBIS_URL}/{created['id']}",
        json={"completedAt": "2026-08-03T00:00:00Z", "rank": "0|hzzz:"},
        headers={"If-Match": etag},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["completedAt"] is None
    # rank は作成時に採番された値のまま（PATCH では変えられない）。
    assert body["rank"] == created["rank"]


# --- 論理削除 ----------------------------------------------------------------


def test_delete_soft_deletes(client: TestClient) -> None:
    created = _create(client)
    etag = client.get(f"{PBIS_URL}/{created['id']}").headers["ETag"]

    res = client.delete(f"{PBIS_URL}/{created['id']}", headers={"If-Match": etag})

    assert res.status_code == 204
    # 以後は存在しない扱い（404）。
    assert client.get(f"{PBIS_URL}/{created['id']}").status_code == 404


def test_delete_without_if_match_is_428(client: TestClient) -> None:
    created = _create(client)

    res = client.delete(f"{PBIS_URL}/{created['id']}")

    assert res.status_code == 428


def test_delete_with_stale_if_match_is_412(client: TestClient) -> None:
    created = _create(client)

    res = client.delete(f"{PBIS_URL}/{created['id']}", headers={"If-Match": '"stale"'})

    assert res.status_code == 412


def test_delete_missing_is_404(client: TestClient) -> None:
    res = client.delete(f"{PBIS_URL}/pbi_missing", headers={"If-Match": '"any"'})

    assert res.status_code == 404


def test_patch_on_deleted_is_404(client: TestClient) -> None:
    created = _create(client)
    etag = client.get(f"{PBIS_URL}/{created['id']}").headers["ETag"]
    client.delete(f"{PBIS_URL}/{created['id']}", headers={"If-Match": etag})

    res = client.patch(
        f"{PBIS_URL}/{created['id']}", json={"title": "x"}, headers={"If-Match": '"any"'}
    )

    assert res.status_code == 404


# --- パーティション境界 ------------------------------------------------------


def test_member_cannot_touch_other_product(client: TestClient) -> None:
    # サンドボックスの member 資格で本番プロダクトの PBI を作っても 403（B-09）。
    res = client.post(f"/api/products/{OTHER_PRODUCT}/pbis", json={"title": "x"})

    assert res.status_code == 403
