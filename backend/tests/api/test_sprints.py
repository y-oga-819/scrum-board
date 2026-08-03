"""スプリント CRUD エンドポイントの統合テスト（B-21・D-20）。

作成・取得・一覧・更新・論理削除が端から端まで通ること、不正な状態遷移
（planned → active → closed 以外）と期間の逆転が弾かれること、``PATCH`` / ``DELETE`` の
``If-Match`` 必須（欠落 428・不一致 412）を確かめる。認可（非メンバー 403・未認証 401）は
テスト専用アプリに実ルータを載せて検証する（test_pbis と同型）。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sprints import router as sprints_router
from app.auth import get_current_user_resolver
from app.auth.resolver import AuthenticatedUser
from app.data.fake import InMemoryRepository
from app.data.members import Role, create_member
from app.http import install_error_handlers

MEMBER_OID = "oid-member"
STRANGER_OID = "oid-stranger"
PRODUCT = "prd_sandbox"
SPRINTS_URL = f"/api/products/{PRODUCT}/sprints"


class _StubResolver:
    """トークン検証を通さず固定 oid を返す（層2の使い方。test_pbis と同型）。"""

    def __init__(self, oid: str) -> None:
        self._oid = oid

    async def resolve(self, request) -> AuthenticatedUser:  # noqa: ANN001
        return AuthenticatedUser(oid=self._oid)


def _build_app(repo: InMemoryRepository | None) -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.state.repository = repo
    app.include_router(sprints_router)
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
    res = client.post(SPRINTS_URL, json=body)
    assert res.status_code == 201, res.text
    return res.json()


# --- 作成 --------------------------------------------------------------------


def test_create_returns_new_sprint_with_etag(client: TestClient) -> None:
    res = client.post(SPRINTS_URL, json={})

    assert res.status_code == 201
    body = res.json()
    assert body["id"].startswith("spr_")
    assert body["type"] == "sprint"
    assert body["productId"] == PRODUCT
    assert body["number"] == 1  # 連番採番の始点
    assert body["status"] == "planned"  # 始点は必ず planned
    assert body["goal"] == ""
    assert body["startDate"] is None
    assert body["endDate"] is None
    assert body["createdBy"] == MEMBER_OID
    # 単一ドキュメント応答は ETag を返す（D-20）。本文には _etag を載せない。
    assert res.headers.get("ETag")
    assert "_etag" not in body


def test_create_accepts_period_and_goal(client: TestClient) -> None:
    body = _create(client, goal="ログインを通す", startDate="2026-08-03", endDate="2026-08-14")
    assert body["goal"] == "ログインを通す"
    assert body["startDate"] == "2026-08-03"
    assert body["endDate"] == "2026-08-14"


def test_create_numbers_sequentially(client: TestClient) -> None:
    assert _create(client)["number"] == 1
    assert _create(client)["number"] == 2
    assert _create(client)["number"] == 3


def test_create_rejects_inverted_period(client: TestClient) -> None:
    res = client.post(SPRINTS_URL, json={"startDate": "2026-08-14", "endDate": "2026-08-03"})

    assert res.status_code == 422
    assert res.headers["content-type"].startswith("application/problem+json")
    assert res.json()["violations"][0]["rule"] == "sprint-period"


def test_create_by_non_member_is_forbidden(repo: InMemoryRepository) -> None:
    client = _client(_build_app(repo), as_oid=STRANGER_OID)

    res = client.post(SPRINTS_URL, json={})

    assert res.status_code == 403


def test_create_unauthenticated_is_unauthorized(repo: InMemoryRepository) -> None:
    client = _client(_build_app(repo), as_oid=None)

    res = client.post(SPRINTS_URL, json={})

    assert res.status_code == 401


# --- 一覧・取得 --------------------------------------------------------------


def test_list_returns_sprints_ordered_by_number_with_etag(client: TestClient) -> None:
    _create(client)
    _create(client)

    res = client.get(SPRINTS_URL)

    assert res.status_code == 200
    items = res.json()
    assert [s["number"] for s in items] == [1, 2]
    # 一覧の各要素は版を本文で運ぶ（集約 GET と同じ非対称 — D-20）。
    assert all(s["_etag"] for s in items)


def test_get_one_returns_sprint_with_etag(client: TestClient) -> None:
    created = _create(client)

    res = client.get(f"{SPRINTS_URL}/{created['id']}")

    assert res.status_code == 200
    assert res.json()["id"] == created["id"]
    assert res.headers.get("ETag")
    assert "_etag" not in res.json()


def test_get_missing_is_not_found(client: TestClient) -> None:
    res = client.get(f"{SPRINTS_URL}/spr_missing")
    assert res.status_code == 404


# --- 更新（状態遷移・期間・楽観排他） ----------------------------------------


def test_patch_advances_status_forward(client: TestClient) -> None:
    created = _create(client)
    etag = _etag_of(client, created["id"])

    res = client.patch(
        f"{SPRINTS_URL}/{created['id']}",
        json={"status": "active"},
        headers={"If-Match": etag},
    )

    assert res.status_code == 200
    assert res.json()["status"] == "active"


def test_patch_rejects_status_skip(client: TestClient) -> None:
    created = _create(client)
    etag = _etag_of(client, created["id"])

    res = client.patch(
        f"{SPRINTS_URL}/{created['id']}",
        json={"status": "closed"},  # planned → closed は飛ばし
        headers={"If-Match": etag},
    )

    assert res.status_code == 422
    assert res.json()["violations"][0]["rule"] == "sprint-status-transition"


def test_patch_updates_goal_and_period(client: TestClient) -> None:
    created = _create(client, startDate="2026-08-03", endDate="2026-08-14")
    etag = _etag_of(client, created["id"])

    res = client.patch(
        f"{SPRINTS_URL}/{created['id']}",
        json={"goal": "決済を通す", "endDate": "2026-08-21"},
        headers={"If-Match": etag},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["goal"] == "決済を通す"
    assert body["endDate"] == "2026-08-21"


def test_patch_rejects_inverted_period_against_current(client: TestClient) -> None:
    # 現行 startDate=2026-08-03 に対し、endDate だけを前へ動かすと逆転する。
    created = _create(client, startDate="2026-08-03", endDate="2026-08-14")
    etag = _etag_of(client, created["id"])

    res = client.patch(
        f"{SPRINTS_URL}/{created['id']}",
        json={"endDate": "2026-08-01"},
        headers={"If-Match": etag},
    )

    assert res.status_code == 422
    assert res.json()["violations"][0]["rule"] == "sprint-period"


def test_patch_without_if_match_is_precondition_required(client: TestClient) -> None:
    created = _create(client)

    res = client.patch(f"{SPRINTS_URL}/{created['id']}", json={"goal": "x"})

    assert res.status_code == 428


def test_patch_with_stale_if_match_is_precondition_failed(client: TestClient) -> None:
    created = _create(client)

    res = client.patch(
        f"{SPRINTS_URL}/{created['id']}",
        json={"goal": "x"},
        headers={"If-Match": '"stale-etag"'},
    )

    assert res.status_code == 412


# --- 論理削除 ----------------------------------------------------------------


def test_delete_soft_deletes_then_404(client: TestClient) -> None:
    created = _create(client)
    etag = _etag_of(client, created["id"])

    res = client.delete(f"{SPRINTS_URL}/{created['id']}", headers={"If-Match": etag})
    assert res.status_code == 204

    assert client.get(f"{SPRINTS_URL}/{created['id']}").status_code == 404


def test_delete_without_if_match_is_precondition_required(client: TestClient) -> None:
    created = _create(client)

    res = client.delete(f"{SPRINTS_URL}/{created['id']}")

    assert res.status_code == 428


# --- ヘルパ ------------------------------------------------------------------


def _etag_of(client: TestClient, sprint_id: str) -> str:
    """単一 GET の ``ETag`` ヘッダを取り出す（If-Match に使う版）。"""
    res = client.get(f"{SPRINTS_URL}/{sprint_id}")
    assert res.status_code == 200
    return res.headers["ETag"]
