"""タスク CRUD エンドポイントの統合テスト（B-20・D-20）。

作成・取得・更新・論理削除が端から端まで通ること、不変条件 I-1〜I-4 が 422 +
``violations``（``rule='I-3'`` 等）で弾かれること、team タスク（親 PBI なし）が作れること、
``done`` への出入りで ``completedAt`` が刻まれる／消えること、``PATCH`` / ``DELETE`` の
``If-Match`` 必須（欠落 428・不一致 412）、認可（非メンバー 403・未認証 401・DB 無し 503）を
確かめる。テスト専用アプリに実ルータを載せて検証する（test_pbis と同型）。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.pbis import router as pbis_router
from app.api.tasks import router as tasks_router
from app.auth import get_current_user_resolver
from app.auth.resolver import AuthenticatedUser
from app.data.fake import InMemoryRepository
from app.data.members import Role, create_member
from app.http import install_error_handlers

MEMBER_OID = "oid-member"
STRANGER_OID = "oid-stranger"
PRODUCT = "prd_sandbox"
OTHER_PRODUCT = "prd_scrum_board"
TASKS_URL = f"/api/products/{PRODUCT}/tasks"
PBIS_URL = f"/api/products/{PRODUCT}/pbis"


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
    # pbi タスクの親 PBI を用意できるよう、PBI ルータも載せる。
    app.include_router(pbis_router)
    app.include_router(tasks_router)
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


def _create_pbi(client: TestClient, title: str = "親 PBI") -> dict:
    res = client.post(PBIS_URL, json={"title": title})
    assert res.status_code == 201, res.text
    return res.json()


def _create_team_task(client: TestClient, **body: object) -> dict:
    payload = {"taskType": "team", "title": "調査", **body}
    res = client.post(TASKS_URL, json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def _etag_of(client: TestClient, task_id: str) -> str:
    return client.get(f"{TASKS_URL}/{task_id}").headers["ETag"]


# --- 作成 --------------------------------------------------------------------


def test_create_team_task_without_parent(client: TestClient) -> None:
    # taskType='team'（親 PBI なし）でも作成できる（B-20 の完了条件）。
    res = client.post(TASKS_URL, json={"taskType": "team", "title": "環境整備"})

    assert res.status_code == 201
    body = res.json()
    assert body["id"].startswith("tsk_")
    assert body["type"] == "task"
    assert body["taskType"] == "team"
    assert body["pbiId"] is None
    assert body["status"] == "todo"
    assert body["completedAt"] is None
    assert body["createdBy"] == MEMBER_OID
    assert res.headers.get("ETag")
    assert "_etag" not in body


def test_create_pbi_task_with_existing_parent(client: TestClient) -> None:
    pbi = _create_pbi(client)

    res = client.post(TASKS_URL, json={"taskType": "pbi", "pbiId": pbi["id"], "title": "実装"})

    assert res.status_code == 201, res.text
    assert res.json()["pbiId"] == pbi["id"]


def test_create_pbi_task_without_pbi_id_is_422_i3(client: TestClient) -> None:
    res = client.post(TASKS_URL, json={"taskType": "pbi", "title": "実装"})

    assert res.status_code == 422
    body = res.json()
    assert body["violations"][0]["rule"] == "I-3"
    assert body["violations"][0]["field"] == "pbiId"


def test_create_team_task_with_pbi_id_is_422_i4(client: TestClient) -> None:
    # 判別は taskType（pbiId の有無ではない）。team なのに pbiId を付けたら I-4。
    pbi = _create_pbi(client)

    res = client.post(TASKS_URL, json={"taskType": "team", "pbiId": pbi["id"], "title": "x"})

    assert res.status_code == 422
    assert res.json()["violations"][0]["rule"] == "I-4"


def test_create_pbi_task_with_missing_parent_is_422(client: TestClient) -> None:
    res = client.post(TASKS_URL, json={"taskType": "pbi", "pbiId": "pbi_missing", "title": "x"})

    assert res.status_code == 422
    assert res.json()["violations"][0]["rule"] == "task-pbi-ref"


def test_create_rejects_empty_title(client: TestClient) -> None:
    res = client.post(TASKS_URL, json={"taskType": "team", "title": ""})

    assert res.status_code == 422
    assert res.headers["content-type"].startswith("application/problem+json")


def test_create_by_non_member_is_forbidden(repo: InMemoryRepository) -> None:
    client = _client(_build_app(repo), as_oid=STRANGER_OID)

    res = client.post(TASKS_URL, json={"taskType": "team", "title": "x"})

    assert res.status_code == 403


def test_create_unauthenticated_is_401(repo: InMemoryRepository) -> None:
    client = _client(_build_app(repo), as_oid=None)

    res = client.post(TASKS_URL, json={"taskType": "team", "title": "x"})

    assert res.status_code == 401
    assert res.headers.get("WWW-Authenticate") == "Bearer"


def test_create_without_db_is_503() -> None:
    client = _client(_build_app(None), as_oid=MEMBER_OID)

    res = client.post(TASKS_URL, json={"taskType": "team", "title": "x"})

    assert res.status_code == 503


# --- 取得 --------------------------------------------------------------------


def test_get_returns_task_with_etag(client: TestClient) -> None:
    created = _create_team_task(client)

    res = client.get(f"{TASKS_URL}/{created['id']}")

    assert res.status_code == 200
    assert res.json()["id"] == created["id"]
    assert res.headers.get("ETag")


def test_get_missing_is_404(client: TestClient) -> None:
    res = client.get(f"{TASKS_URL}/tsk_missing")

    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")


# --- 更新（If-Match・完了地の刻印） ------------------------------------------


def test_patch_updates_fields(client: TestClient) -> None:
    created = _create_team_task(client)

    res = client.patch(
        f"{TASKS_URL}/{created['id']}",
        json={"title": "改称", "memo": "メモ", "isBlocked": True, "blockedReason": "待ち"},
        headers={"If-Match": _etag_of(client, created["id"])},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "改称"
    assert body["memo"] == "メモ"
    assert body["isBlocked"] is True
    assert body["blockedReason"] == "待ち"


def test_patch_to_done_stamps_completed_at(client: TestClient) -> None:
    created = _create_team_task(client)

    res = client.patch(
        f"{TASKS_URL}/{created['id']}",
        json={"status": "done"},
        headers={"If-Match": _etag_of(client, created["id"])},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "done"
    assert body["completedAt"] is not None  # I-2: done なら completedAt が記録される


def test_patch_out_of_done_clears_completed_at(client: TestClient) -> None:
    created = _create_team_task(client)
    client.patch(
        f"{TASKS_URL}/{created['id']}",
        json={"status": "done"},
        headers={"If-Match": _etag_of(client, created["id"])},
    )

    res = client.patch(
        f"{TASKS_URL}/{created['id']}",
        json={"status": "doing"},  # 完了取り消し
        headers={"If-Match": _etag_of(client, created["id"])},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "doing"
    assert body["completedAt"] is None  # I-1: 未完了なら completedAt は null に戻る


def test_patch_cannot_change_task_type(client: TestClient) -> None:
    # taskType は TaskUpdate に無いため、送っても無視される（判別子は不変）。
    created = _create_team_task(client)

    res = client.patch(
        f"{TASKS_URL}/{created['id']}",
        json={"taskType": "pbi", "pbiId": "pbi_x"},
        headers={"If-Match": _etag_of(client, created["id"])},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["taskType"] == "team"  # 変わらない
    assert body["pbiId"] is None


def test_patch_without_if_match_is_428(client: TestClient) -> None:
    created = _create_team_task(client)

    res = client.patch(f"{TASKS_URL}/{created['id']}", json={"title": "x"})

    assert res.status_code == 428


def test_patch_with_stale_if_match_is_412(client: TestClient) -> None:
    created = _create_team_task(client)

    res = client.patch(
        f"{TASKS_URL}/{created['id']}",
        json={"title": "x"},
        headers={"If-Match": '"stale"'},
    )

    assert res.status_code == 412


def test_patch_missing_is_404(client: TestClient) -> None:
    res = client.patch(
        f"{TASKS_URL}/tsk_missing", json={"title": "x"}, headers={"If-Match": '"any"'}
    )

    assert res.status_code == 404


# --- 論理削除 ----------------------------------------------------------------


def test_delete_soft_deletes(client: TestClient) -> None:
    created = _create_team_task(client)

    res = client.delete(
        f"{TASKS_URL}/{created['id']}", headers={"If-Match": _etag_of(client, created["id"])}
    )

    assert res.status_code == 204
    assert client.get(f"{TASKS_URL}/{created['id']}").status_code == 404


def test_delete_without_if_match_is_428(client: TestClient) -> None:
    created = _create_team_task(client)

    res = client.delete(f"{TASKS_URL}/{created['id']}")

    assert res.status_code == 428


def test_delete_missing_is_404(client: TestClient) -> None:
    res = client.delete(f"{TASKS_URL}/tsk_missing", headers={"If-Match": '"any"'})

    assert res.status_code == 404


# --- パーティション境界 ------------------------------------------------------


def test_member_cannot_touch_other_product(client: TestClient) -> None:
    res = client.post(
        f"/api/products/{OTHER_PRODUCT}/tasks", json={"taskType": "team", "title": "x"}
    )

    assert res.status_code == 403
