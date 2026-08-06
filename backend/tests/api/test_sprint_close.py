"""スプリント終了処理エンドポイントの統合テスト（B-25・I-5・D-20）。

``GET .../sprints/{sid}/close/preview``（持ち越しプレビュー）と
``POST .../sprints/{sid}/close``（確定）が端から端まで通ること、未完了だけが次スプリントへ
移り**完了タスクは動かない**こと（I-5）、締められるのは active だけ・移動先の妥当性（自己
指定／終了済み）を 422 で弾くこと、実在しないスプリントが 404、認可（非メンバー 403・
未認証 401・DB 無し 503）を確かめる。test_planning と同型。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.board import router as board_router
from app.api.pbis import router as pbis_router
from app.api.planning import router as planning_router
from app.api.sprint_close import router as sprint_close_router
from app.api.sprints import router as sprints_router
from app.api.tasks import router as tasks_router
from app.auth import get_current_user_resolver
from app.auth.resolver import AuthenticatedUser
from app.data.fake import InMemoryRepository
from app.data.members import Role, create_member
from app.http import install_error_handlers

MEMBER_OID = "oid-member"
STRANGER_OID = "oid-stranger"
PRODUCT = "prd_sandbox"
BASE = f"/api/products/{PRODUCT}"


class _StubResolver:
    def __init__(self, oid: str) -> None:
        self._oid = oid

    async def resolve(self, request) -> AuthenticatedUser:  # noqa: ANN001
        return AuthenticatedUser(oid=self._oid)


def _build_app(repo: InMemoryRepository | None) -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.state.repository = repo
    app.include_router(pbis_router)
    app.include_router(tasks_router)
    app.include_router(sprints_router)
    app.include_router(planning_router)
    app.include_router(sprint_close_router)
    app.include_router(board_router)
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


# --- 準備ヘルパ --------------------------------------------------------------


def _create_pbi(client: TestClient, title: str = "PBI") -> dict:
    res = client.post(f"{BASE}/pbis", json={"title": title})
    assert res.status_code == 201, res.text
    return res.json()


def _create_sprint(client: TestClient) -> dict:
    res = client.post(f"{BASE}/sprints", json={"goal": "回す"})
    assert res.status_code == 201, res.text
    return res.json()


def _activate(client: TestClient, sprint: dict) -> dict:
    res = client.patch(
        f"{BASE}/sprints/{sprint['id']}",
        json={"status": "active"},
        headers={"If-Match": _etag_of(client, sprint["id"])},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _active_sprint(client: TestClient) -> dict:
    return _activate(client, _create_sprint(client))


def _etag_of(client: TestClient, sprint_id: str) -> str:
    res = client.get(f"{BASE}/sprints/{sprint_id}")
    assert res.status_code == 200, res.text
    return res.headers["ETag"]


def _create_task_in_sprint(client: TestClient, pbi_id: str, sprint_id: str, title: str) -> dict:
    """pbi タスクを作り、プランニングでスプリントに取り込む（``sprintId`` を付ける）。"""
    res = client.post(f"{BASE}/tasks", json={"taskType": "pbi", "pbiId": pbi_id, "title": title})
    assert res.status_code == 201, res.text
    task = res.json()
    inc = client.post(f"{BASE}/sprints/{sprint_id}/pbis/{pbi_id}")
    assert inc.status_code == 204, inc.text
    return task


def _board_tasks(client: TestClient, sprint_id: str) -> list[dict]:
    res = client.get(f"{BASE}/sprints/{sprint_id}/board")
    assert res.status_code == 200, res.text
    return res.json()["tasks"]


def _mark_done(client: TestClient, sprint_id: str, task_id: str) -> None:
    task = next(t for t in _board_tasks(client, sprint_id) if t["id"] == task_id)
    res = client.patch(
        f"{BASE}/tasks/{task_id}",
        json={"status": "done"},
        headers={"If-Match": task["_etag"]},
    )
    assert res.status_code == 200, res.text


# --- プレビュー --------------------------------------------------------------


def test_preview_lists_only_incomplete(client: TestClient) -> None:
    pbi = _create_pbi(client)
    sprint = _active_sprint(client)
    todo = _create_task_in_sprint(client, pbi["id"], sprint["id"], "未着手")
    done = _create_task_in_sprint(client, pbi["id"], sprint["id"], "済")
    _mark_done(client, sprint["id"], done["id"])
    res = client.get(f"{BASE}/sprints/{sprint['id']}/close/preview")
    assert res.status_code == 200, res.text
    ids = {t["id"] for t in res.json()["tasks"]}
    assert todo["id"] in ids
    assert done["id"] not in ids  # I-5: 完了タスクは持ち越し対象に含めない。


def test_preview_unknown_sprint_is_404(client: TestClient) -> None:
    res = client.get(f"{BASE}/sprints/spr_missing/close/preview")
    assert res.status_code == 404


# --- 確定 --------------------------------------------------------------------


def test_close_moves_incomplete_and_closes(client: TestClient) -> None:
    pbi = _create_pbi(client)
    closing = _active_sprint(client)
    nxt = _create_sprint(client)
    todo = _create_task_in_sprint(client, pbi["id"], closing["id"], "未着手")
    res = client.post(f"{BASE}/sprints/{closing['id']}/close", json={"nextSprintId": nxt["id"]})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["carriedOver"] == 1
    assert body["sprint"]["status"] == "closed"
    # 未完了タスクは次スプリントのボードに現れる。
    assert todo["id"] in {t["id"] for t in _board_tasks(client, nxt["id"])}


def test_close_keeps_done_tasks_in_original_sprint(client: TestClient) -> None:
    # I-5: 完了タスクは締めても sprintId を変えない（元スプリントに残る）。
    pbi = _create_pbi(client)
    closing = _active_sprint(client)
    nxt = _create_sprint(client)
    done = _create_task_in_sprint(client, pbi["id"], closing["id"], "済")
    _mark_done(client, closing["id"], done["id"])
    res = client.post(f"{BASE}/sprints/{closing['id']}/close", json={"nextSprintId": nxt["id"]})
    assert res.status_code == 200, res.text
    assert res.json()["carriedOver"] == 0
    # 完了タスクは元スプリントのボードに残り、次には現れない。
    assert done["id"] in {t["id"] for t in _board_tasks(client, closing["id"])}
    assert done["id"] not in {t["id"] for t in _board_tasks(client, nxt["id"])}


def test_close_requires_active_sprint(client: TestClient) -> None:
    # planned のまま締めようとすると 422（締められるのは active だけ）。
    planned = _create_sprint(client)
    nxt = _create_sprint(client)
    res = client.post(f"{BASE}/sprints/{planned['id']}/close", json={"nextSprintId": nxt["id"]})
    assert res.status_code == 422
    assert res.json()["violations"][0]["rule"] == "sprint-close-status"


def test_close_rejects_self_target(client: TestClient) -> None:
    sprint = _active_sprint(client)
    res = client.post(f"{BASE}/sprints/{sprint['id']}/close", json={"nextSprintId": sprint["id"]})
    assert res.status_code == 422
    assert res.json()["violations"][0]["rule"] == "sprint-close-target"


def test_close_rejects_closed_target(client: TestClient) -> None:
    # 移動先が終了済みなら 422。
    closing = _active_sprint(client)
    already = _active_sprint(client)
    spare = _create_sprint(client)
    # already を先に締めておく（closed にする）。
    done = client.post(f"{BASE}/sprints/{already['id']}/close", json={"nextSprintId": spare["id"]})
    assert done.status_code == 200, done.text
    res = client.post(f"{BASE}/sprints/{closing['id']}/close", json={"nextSprintId": already["id"]})
    assert res.status_code == 422
    assert res.json()["violations"][0]["rule"] == "sprint-close-target"


def test_close_unknown_target_is_404(client: TestClient) -> None:
    sprint = _active_sprint(client)
    res = client.post(f"{BASE}/sprints/{sprint['id']}/close", json={"nextSprintId": "spr_missing"})
    assert res.status_code == 404


def test_close_unknown_sprint_is_404(client: TestClient) -> None:
    nxt = _create_sprint(client)
    res = client.post(f"{BASE}/sprints/spr_missing/close", json={"nextSprintId": nxt["id"]})
    assert res.status_code == 404


# --- 認可 --------------------------------------------------------------------


def test_close_non_member_is_403(repo: InMemoryRepository) -> None:
    app = _build_app(repo)
    member_client = _client(app, as_oid=MEMBER_OID)
    sprint = _active_sprint(member_client)
    nxt = _create_sprint(member_client)
    app.dependency_overrides[get_current_user_resolver] = lambda: _StubResolver(STRANGER_OID)
    res = TestClient(app).post(
        f"{BASE}/sprints/{sprint['id']}/close", json={"nextSprintId": nxt["id"]}
    )
    assert res.status_code == 403


def test_preview_unauthenticated_is_401(repo: InMemoryRepository) -> None:
    res = _client(_build_app(repo), as_oid=None).get(f"{BASE}/sprints/spr_x/close/preview")
    assert res.status_code == 401


def test_close_without_db_is_503() -> None:
    res = _client(_build_app(None), as_oid=MEMBER_OID).post(
        f"{BASE}/sprints/spr_x/close", json={"nextSprintId": "spr_y"}
    )
    assert res.status_code == 503
