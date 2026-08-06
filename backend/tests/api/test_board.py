"""スプリントボード集約 GET の統合テスト（B-23・D-20）。

画面単位の読み取り ``GET /sprints/{sid}/board`` が、スプリント情報とそのスプリントに属する
タスクを 1 往復返すこと、各タスクに **``_etag`` を本文で含む**こと（ボード操作の ``If-Match``
に使うため）、``sprintId`` が別のタスク・論理削除済みを除外すること、存在しないスプリントは
404、認可（非メンバー 403・未認証 401・DB 無し 503）を確かめる。カラム（todo/doing/done）
への振り分けは導出のためフロントが行い、サーバーは並びだけ保証する（D-20）。

ボード操作そのもの（``status`` の移動・ブロックフラグ）は汎用の ``PATCH /tasks/{id}``
（B-20）で行うため、その 412／楽観排他は :mod:`tests.api.test_tasks` が持つ。ここは集約
GET が正しい版を運ぶこと（その ``_etag`` で ``PATCH`` が通ること）までを確かめる。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.board import router as board_router
from app.api.sprints import router as sprints_router
from app.api.tasks import router as tasks_router
from app.auth import get_current_user_resolver
from app.auth.resolver import AuthenticatedUser
from app.data.documents import DocumentType
from app.data.fake import InMemoryRepository
from app.data.members import Role, create_member
from app.data.tasks import TaskType, new_task_data
from app.http import install_error_handlers

MEMBER_OID = "oid-member"
STRANGER_OID = "oid-stranger"
PRODUCT = "prd_sandbox"
SPRINTS_URL = f"/api/products/{PRODUCT}/sprints"
TASKS_URL = f"/api/products/{PRODUCT}/tasks"


class _StubResolver:
    """トークン検証を通さず固定 oid を返す（層2の使い方。test_backlog と同型）。"""

    def __init__(self, oid: str) -> None:
        self._oid = oid

    async def resolve(self, request) -> AuthenticatedUser:  # noqa: ANN001
        return AuthenticatedUser(oid=self._oid)


def _build_app(repo: InMemoryRepository | None) -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.state.repository = repo
    # スプリント・タスクを作ってボードで読む。全ルータを載せる。
    app.include_router(sprints_router)
    app.include_router(tasks_router)
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


def _create_sprint(client: TestClient) -> dict:
    res = client.post(SPRINTS_URL, json={"goal": ""})
    assert res.status_code == 201, res.text
    return res.json()


def _seed_task(repo: InMemoryRepository, *, title: str, sprint_id: str | None) -> dict:
    """タスクを 1 件、``sprintId`` を指定して直接シードする（テスト用）。

    ``sprintId`` はプランニング（B-22）が専用経路で付けるフィールドで、汎用 ``PATCH``
    （:class:`~app.api.tasks.TaskUpdate`）には載っていない。ここではボードの**読み取り**だけを
    確かめたいので、プランニングの経路を通さずリポジトリへ直接 team タスクを積む。
    """
    data = new_task_data(task_type=TaskType.TEAM, title=title)
    data["sprintId"] = sprint_id
    return repo.create(product_id=PRODUCT, doc_type=DocumentType.TASK, data=data, actor=MEMBER_OID)


def _seed_pbi_task(
    repo: InMemoryRepository, *, title: str, sprint_id: str | None, status: str = "todo"
) -> dict:
    """pbi タスクを 1 件、``sprintId`` と ``status`` を指定して直接シードする（進捗集計用）。"""
    data = new_task_data(task_type=TaskType.PBI, title=title, pbi_id="pbi_x")
    data["sprintId"] = sprint_id
    data["status"] = status
    return repo.create(product_id=PRODUCT, doc_type=DocumentType.TASK, data=data, actor=MEMBER_OID)


class _FixedClock:
    """固定時刻を返すテスト用時計（営業日マーカーの「今日」を固定する — D-19）。"""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment


def _board_url(sprint_id: str) -> str:
    return f"{SPRINTS_URL}/{sprint_id}/board"


def test_board_returns_sprint_and_empty_tasks(client: TestClient) -> None:
    sprint = _create_sprint(client)

    res = client.get(_board_url(sprint["id"]))

    assert res.status_code == 200
    body = res.json()
    assert body["sprint"]["id"] == sprint["id"]
    assert body["sprint"]["number"] == sprint["number"]
    assert body["tasks"] == []


def test_board_returns_only_this_sprints_tasks(
    client: TestClient, repo: InMemoryRepository
) -> None:
    sprint = _create_sprint(client)
    other = _create_sprint(client)
    mine = _seed_task(repo, title="このスプリント", sprint_id=sprint["id"])
    _seed_task(repo, title="別スプリント", sprint_id=other["id"])
    _seed_task(repo, title="未割当", sprint_id=None)  # sprintId=null は載らない

    res = client.get(_board_url(sprint["id"]))

    ids = [t["id"] for t in res.json()["tasks"]]
    assert ids == [mine["id"]]


def test_board_tasks_carry_etag_for_if_match(client: TestClient, repo: InMemoryRepository) -> None:
    # 集約 GET は各タスクの _etag を本文で返す（ボード操作の If-Match に使う — D-20）。
    sprint = _create_sprint(client)
    task = _seed_task(repo, title="動かす", sprint_id=sprint["id"])

    res = client.get(_board_url(sprint["id"]))

    item = res.json()["tasks"][0]
    assert item["_etag"]
    # その _etag をそのまま If-Match に使うと status 移動（PATCH）が通る（版が噛み合う）。
    patched = client.patch(
        f"{TASKS_URL}/{task['id']}",
        json={"status": "doing"},
        headers={"If-Match": item["_etag"]},
    )
    assert patched.status_code == 200


def test_board_excludes_soft_deleted_tasks(client: TestClient, repo: InMemoryRepository) -> None:
    sprint = _create_sprint(client)
    keep = _seed_task(repo, title="残す", sprint_id=sprint["id"])
    drop = _seed_task(repo, title="消す", sprint_id=sprint["id"])
    etag = client.get(f"{TASKS_URL}/{drop['id']}").headers["ETag"]
    client.delete(f"{TASKS_URL}/{drop['id']}", headers={"If-Match": etag})

    res = client.get(_board_url(sprint["id"]))

    ids = [t["id"] for t in res.json()["tasks"]]
    assert ids == [keep["id"]]  # 論理削除済みは集約に載らない（D-20）


def test_board_unknown_sprint_is_404(client: TestClient) -> None:
    res = client.get(_board_url("spr_does_not_exist"))

    assert res.status_code == 404


def test_board_by_non_member_is_forbidden(repo: InMemoryRepository) -> None:
    # 非メンバーはスプリントの存在有無に触れる前に 403（認可が先）。
    client = _client(_build_app(repo), as_oid=STRANGER_OID)

    res = client.get(_board_url("spr_anything"))

    assert res.status_code == 403


def test_board_unauthenticated_is_401(repo: InMemoryRepository) -> None:
    client = _client(_build_app(repo), as_oid=None)

    res = client.get(_board_url("spr_anything"))

    assert res.status_code == 401
    assert res.headers.get("WWW-Authenticate") == "Bearer"


def test_board_without_db_is_503() -> None:
    client = _client(_build_app(None), as_oid=MEMBER_OID)

    res = client.get(_board_url("spr_anything"))

    assert res.status_code == 503


# --- 進捗（2本バー＋営業日マーカー。B-24） ---------------------------------------


def test_board_progress_counts_planned_and_team_bars(
    client: TestClient, repo: InMemoryRepository
) -> None:
    sprint = _create_sprint(client)
    _seed_pbi_task(repo, title="計画1", sprint_id=sprint["id"], status="done")
    _seed_pbi_task(repo, title="計画2", sprint_id=sprint["id"], status="todo")
    _seed_task(repo, title="チーム1", sprint_id=sprint["id"])  # team / todo

    progress = client.get(_board_url(sprint["id"])).json()["progress"]

    assert progress["planned"] == {"done": 1, "total": 2}
    assert progress["team"] == {"done": 0, "total": 1}


def test_board_progress_marker_uses_business_days_and_injected_today(
    repo: InMemoryRepository,
) -> None:
    # 「今日」を 2026-08-06 の JST 日付に固定（16:00Z は翌日になるので午前 UTC を使う）。
    app = _build_app(repo)
    app.state.clock = _FixedClock(datetime(2026, 8, 6, 3, 0, tzinfo=UTC))
    client = _client(app, as_oid=MEMBER_OID)
    # 08-03(月)〜08-14(金)。08-11(火)は山の日。営業日総数は 9、08-06 時点の経過は 4。
    sprint = client.post(
        SPRINTS_URL, json={"goal": "", "startDate": "2026-08-03", "endDate": "2026-08-14"}
    ).json()

    progress = client.get(_board_url(sprint["id"])).json()["progress"]

    assert progress["totalBusinessDays"] == 9
    assert progress["elapsedBusinessDays"] == 4


def test_board_progress_has_null_marker_when_period_unset(client: TestClient) -> None:
    sprint = _create_sprint(client)  # 期間なし（goal のみ）

    progress = client.get(_board_url(sprint["id"])).json()["progress"]

    assert progress["totalBusinessDays"] is None
    assert progress["elapsedBusinessDays"] is None
