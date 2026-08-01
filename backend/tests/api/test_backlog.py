"""バックログ集約 GET の統合テスト（B-17・D-20）。

画面単位の読み取り ``GET /backlog`` が、PBI を **優先順位順（``rank, id``）** で 1 往復
返すこと、各要素に **``_etag`` を本文で含む**こと（並び替え・ステータス変更の ``If-Match``
に使うため）、論理削除済みを除外すること、認可（非メンバー 403・未認証 401・DB 無し 503）を
確かめる。並びの正はサーバー（フロントで再ソートしない — D-20）。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.backlog import router as backlog_router
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
BACKLOG_URL = f"/api/products/{PRODUCT}/backlog"
PBIS_URL = f"/api/products/{PRODUCT}/pbis"
TASKS_URL = f"/api/products/{PRODUCT}/tasks"


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
    # 書き込み（PBI・タスク作成）でデータを用意し、集約 GET で読む。全ルータを載せる。
    app.include_router(pbis_router)
    app.include_router(tasks_router)
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


def _create(client: TestClient, title: str) -> dict:
    res = client.post(PBIS_URL, json={"title": title})
    assert res.status_code == 201, res.text
    return res.json()


def test_empty_backlog_returns_empty_list(client: TestClient) -> None:
    res = client.get(BACKLOG_URL)

    assert res.status_code == 200
    assert res.json() == {"pbis": []}


def test_backlog_returns_pbis_in_rank_order(client: TestClient) -> None:
    # 末尾採番なので作成順に rank が増える。並びは作成順（＝優先順位順）で返る。
    first = _create(client, "A")
    second = _create(client, "B")
    third = _create(client, "C")

    res = client.get(BACKLOG_URL)

    assert res.status_code == 200
    ids = [p["id"] for p in res.json()["pbis"]]
    assert ids == [first["id"], second["id"], third["id"]]


def test_backlog_reflects_reorder(client: TestClient) -> None:
    # 並び替え後もサーバーの ORDER BY で正しい順に返る（フロントで再ソートしない）。
    a = _create(client, "A")
    b = _create(client, "B")
    c = _create(client, "C")
    etag_c = client.get(f"{PBIS_URL}/{c['id']}").headers["ETag"]
    client.post(
        f"{PBIS_URL}/{c['id']}/rank",
        json={"beforeId": a["id"], "afterId": b["id"]},
        headers={"If-Match": etag_c},
    )

    res = client.get(BACKLOG_URL)

    ids = [p["id"] for p in res.json()["pbis"]]
    assert ids == [a["id"], c["id"], b["id"]]


def test_backlog_items_carry_etag_for_if_match(client: TestClient) -> None:
    # 集約 GET は各要素の _etag を本文で返す（応答全体の ETag は持てない — D-20）。
    _create(client, "A")

    res = client.get(BACKLOG_URL)

    item = res.json()["pbis"][0]
    assert item["_etag"]
    # その _etag をそのまま If-Match に使うと更新が通る（版が噛み合っている）。
    patched = client.patch(
        f"{PBIS_URL}/{item['id']}",
        json={"title": "改称"},
        headers={"If-Match": item["_etag"]},
    )
    assert patched.status_code == 200


def test_backlog_excludes_soft_deleted(client: TestClient) -> None:
    a = _create(client, "A")
    b = _create(client, "B")
    etag_a = client.get(f"{PBIS_URL}/{a['id']}").headers["ETag"]
    client.delete(f"{PBIS_URL}/{a['id']}", headers={"If-Match": etag_a})

    res = client.get(BACKLOG_URL)

    ids = [p["id"] for p in res.json()["pbis"]]
    assert ids == [b["id"]]  # 論理削除済みは集約に載らない（D-20）


# --- 配下タスクの結合（B-20） ------------------------------------------------


def _add_pbi_task(client: TestClient, pbi_id: str, title: str) -> dict:
    res = client.post(TASKS_URL, json={"taskType": "pbi", "pbiId": pbi_id, "title": title})
    assert res.status_code == 201, res.text
    return res.json()


def test_backlog_pbi_without_tasks_has_empty_list(client: TestClient) -> None:
    _create(client, "A")

    res = client.get(BACKLOG_URL)

    assert res.json()["pbis"][0]["tasks"] == []


def test_backlog_joins_pbi_tasks_under_their_pbi(client: TestClient) -> None:
    a = _create(client, "A")
    b = _create(client, "B")
    t1 = _add_pbi_task(client, a["id"], "実装")
    t2 = _add_pbi_task(client, a["id"], "テスト")
    _add_pbi_task(client, b["id"], "別 PBI のタスク")

    res = client.get(BACKLOG_URL)

    pbis = {p["id"]: p for p in res.json()["pbis"]}
    a_task_ids = [t["id"] for t in pbis[a["id"]]["tasks"]]
    assert a_task_ids == [t1["id"], t2["id"]]  # rank 未設定なので作成順（id 昇順）
    assert len(pbis[b["id"]]["tasks"]) == 1


def test_backlog_tasks_carry_etag_for_if_match(client: TestClient) -> None:
    # 配下タスクも _etag を本文で返す（ボード操作の If-Match に使う — D-20）。
    a = _create(client, "A")
    task = _add_pbi_task(client, a["id"], "実装")

    res = client.get(BACKLOG_URL)

    item = res.json()["pbis"][0]["tasks"][0]
    assert item["_etag"]
    patched = client.patch(
        f"{TASKS_URL}/{task['id']}",
        json={"status": "doing"},
        headers={"If-Match": item["_etag"]},
    )
    assert patched.status_code == 200


def test_backlog_excludes_team_tasks_from_pbi_join(client: TestClient) -> None:
    # 未割当チームタスクは PBI 配下に混ざらない（露出は B-29）。
    a = _create(client, "A")
    _add_pbi_task(client, a["id"], "実装")
    client.post(TASKS_URL, json={"taskType": "team", "title": "チーム作業"})

    res = client.get(BACKLOG_URL)

    titles = [t["title"] for t in res.json()["pbis"][0]["tasks"]]
    assert titles == ["実装"]  # team タスクは束ねない


def test_backlog_excludes_soft_deleted_tasks(client: TestClient) -> None:
    a = _create(client, "A")
    task = _add_pbi_task(client, a["id"], "消す")
    etag = client.get(f"{TASKS_URL}/{task['id']}").headers["ETag"]
    client.delete(f"{TASKS_URL}/{task['id']}", headers={"If-Match": etag})

    res = client.get(BACKLOG_URL)

    assert res.json()["pbis"][0]["tasks"] == []


def test_backlog_by_non_member_is_forbidden(repo: InMemoryRepository) -> None:
    client = _client(_build_app(repo), as_oid=STRANGER_OID)

    res = client.get(BACKLOG_URL)

    assert res.status_code == 403


def test_backlog_unauthenticated_is_401(repo: InMemoryRepository) -> None:
    client = _client(_build_app(repo), as_oid=None)

    res = client.get(BACKLOG_URL)

    assert res.status_code == 401
    assert res.headers.get("WWW-Authenticate") == "Bearer"


def test_backlog_without_db_is_503() -> None:
    client = _client(_build_app(None), as_oid=MEMBER_OID)

    res = client.get(BACKLOG_URL)

    assert res.status_code == 503
