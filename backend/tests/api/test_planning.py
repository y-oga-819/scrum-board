"""プランニング専用エンドポイントの統合テスト（B-22・D-15・D-20）。

``POST/DELETE /api/products/{pid}/sprints/{sid}/pbis/{pbiId}`` が端から端まで通ること、
配下の未完了タスクに ``sprintId`` が付く／外れること、タスク0件の PBI 取り込みで「タスク分解」
が1件生成されること（D-15）、完了タスクを動かさないこと（I-5）、実在しないスプリント／PBI が
404、認可（非メンバー 403・未認証 401・DB 無し 503）を確かめる。test_tasks と同型。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.backlog import router as backlog_router
from app.api.pbis import router as pbis_router
from app.api.planning import router as planning_router
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
    app.include_router(backlog_router)
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


def _create_pbi(client: TestClient, title: str = "PBI") -> dict:
    res = client.post(f"{BASE}/pbis", json={"title": title})
    assert res.status_code == 201, res.text
    return res.json()


def _create_sprint(client: TestClient) -> dict:
    res = client.post(f"{BASE}/sprints", json={"goal": "回す"})
    assert res.status_code == 201, res.text
    return res.json()


def _create_pbi_task(client: TestClient, pbi_id: str, title: str = "実装") -> dict:
    res = client.post(f"{BASE}/tasks", json={"taskType": "pbi", "pbiId": pbi_id, "title": title})
    assert res.status_code == 201, res.text
    return res.json()


def _backlog(client: TestClient) -> dict:
    res = client.get(f"{BASE}/backlog")
    assert res.status_code == 200, res.text
    return res.json()


def _tasks_of(backlog: dict, pbi_id: str) -> list[dict]:
    return next(p["tasks"] for p in backlog["pbis"] if p["id"] == pbi_id)


# --- 取り込み ----------------------------------------------------------------


def test_include_assigns_sprint_id(client: TestClient) -> None:
    pbi = _create_pbi(client)
    sprint = _create_sprint(client)
    _create_pbi_task(client, pbi["id"])
    res = client.post(f"{BASE}/sprints/{sprint['id']}/pbis/{pbi['id']}")
    assert res.status_code == 204, res.text
    tasks = _tasks_of(_backlog(client), pbi["id"])
    assert [t["sprintId"] for t in tasks] == [sprint["id"]]


def test_include_zero_tasks_generates_decomposition(client: TestClient) -> None:
    # D-15: タスク0件の PBI を取り込むと「タスク分解」が1件現れ、そのスプリントに入る。
    pbi = _create_pbi(client)
    sprint = _create_sprint(client)
    res = client.post(f"{BASE}/sprints/{sprint['id']}/pbis/{pbi['id']}")
    assert res.status_code == 204, res.text
    tasks = _tasks_of(_backlog(client), pbi["id"])
    assert len(tasks) == 1
    assert tasks[0]["title"] == "タスク分解"
    assert tasks[0]["sprintId"] == sprint["id"]


def test_include_unknown_sprint_is_404(client: TestClient) -> None:
    pbi = _create_pbi(client)
    res = client.post(f"{BASE}/sprints/spr_missing/pbis/{pbi['id']}")
    assert res.status_code == 404


def test_include_unknown_pbi_is_404(client: TestClient) -> None:
    sprint = _create_sprint(client)
    res = client.post(f"{BASE}/sprints/{sprint['id']}/pbis/pbi_missing")
    assert res.status_code == 404


# --- 外す --------------------------------------------------------------------


def test_exclude_resets_incomplete_tasks(client: TestClient) -> None:
    pbi = _create_pbi(client)
    sprint = _create_sprint(client)
    _create_pbi_task(client, pbi["id"])
    client.post(f"{BASE}/sprints/{sprint['id']}/pbis/{pbi['id']}")
    res = client.delete(f"{BASE}/sprints/{sprint['id']}/pbis/{pbi['id']}")
    assert res.status_code == 204, res.text
    tasks = _tasks_of(_backlog(client), pbi["id"])
    assert [t["sprintId"] for t in tasks] == [None]


def test_exclude_keeps_done_tasks_in_sprint(client: TestClient) -> None:
    # I-5: 完了タスクは外す操作で sprintId を変えない。
    pbi = _create_pbi(client)
    sprint = _create_sprint(client)
    task = _create_pbi_task(client, pbi["id"])
    client.post(f"{BASE}/sprints/{sprint['id']}/pbis/{pbi['id']}")
    # 取り込み後の版を取り、done にする。
    in_sprint = _tasks_of(_backlog(client), pbi["id"])[0]
    done_res = client.patch(
        f"{BASE}/tasks/{task['id']}",
        json={"status": "done"},
        headers={"If-Match": in_sprint["_etag"]},
    )
    assert done_res.status_code == 200, done_res.text
    client.delete(f"{BASE}/sprints/{sprint['id']}/pbis/{pbi['id']}")
    tasks = _tasks_of(_backlog(client), pbi["id"])
    assert tasks[0]["status"] == "done"
    assert tasks[0]["sprintId"] == sprint["id"]


# --- 認可 --------------------------------------------------------------------


def test_include_non_member_is_403(repo: InMemoryRepository) -> None:
    app = _build_app(repo)
    member_client = _client(app, as_oid=MEMBER_OID)
    pbi = _create_pbi(member_client)
    sprint = _create_sprint(member_client)
    app.dependency_overrides[get_current_user_resolver] = lambda: _StubResolver(STRANGER_OID)
    res = TestClient(app).post(f"{BASE}/sprints/{sprint['id']}/pbis/{pbi['id']}")
    assert res.status_code == 403


def test_include_unauthenticated_is_401(repo: InMemoryRepository) -> None:
    res = _client(_build_app(repo), as_oid=None).post(f"{BASE}/sprints/spr_x/pbis/pbi_x")
    assert res.status_code == 401


def test_include_without_db_is_503() -> None:
    res = _client(_build_app(None), as_oid=MEMBER_OID).post(f"{BASE}/sprints/spr_x/pbis/pbi_x")
    assert res.status_code == 503
