"""デイリーノートのエンドポイントの統合テスト（B-27・D-27）。

``GET .../daily/{date}`` が get-or-create（無ければ空のノートを作って返し、``ETag`` を運ぶ・
再取得で編集が消えない）であること、``PATCH`` が ``If-Match`` の下で ``agenda`` / ``minutes`` を
更新すること（欠落 428・不一致 412）、不正な日付 422・幻のスプリント 404・PATCH 前に GET が
無ければ 404、認可（非メンバー 403・未認証 401・DB 無し 503）を確かめる。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.daily_notes import router as daily_router
from app.api.sprints import router as sprints_router
from app.auth import get_current_user_resolver
from app.auth.resolver import AuthenticatedUser
from app.data.fake import InMemoryRepository
from app.data.members import Role, create_member

MEMBER_OID = "oid-member"
STRANGER_OID = "oid-stranger"
PRODUCT = "prd_sandbox"
SPRINTS_URL = f"/api/products/{PRODUCT}/sprints"
DATE = "2026-08-05"


class _StubResolver:
    """トークン検証を通さず固定 oid を返す（層2の使い方。test_board と同型）。"""

    def __init__(self, oid: str) -> None:
        self._oid = oid

    async def resolve(self, request) -> AuthenticatedUser:  # noqa: ANN001
        return AuthenticatedUser(oid=self._oid)


def _build_app(repo: InMemoryRepository | None) -> FastAPI:
    app = FastAPI()
    from app.http import install_error_handlers

    install_error_handlers(app)
    app.state.repository = repo
    app.include_router(sprints_router)
    app.include_router(daily_router)
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


def _daily_url(sprint_id: str, date: str = DATE) -> str:
    return f"{SPRINTS_URL}/{sprint_id}/daily/{date}"


# --- GET（get-or-create） -----------------------------------------------------


def test_get_creates_empty_note_and_returns_etag(client: TestClient) -> None:
    sprint = _create_sprint(client)

    res = client.get(_daily_url(sprint["id"]))

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sprintId"] == sprint["id"]
    assert body["date"] == DATE
    assert body["agenda"] == []
    assert body["minutes"] == ""
    assert "_etag" not in body  # 単一ドキュメント応答は本文に版を載せない（D-20）
    assert res.headers["ETag"]  # 版はヘッダで返る（次の PATCH の If-Match に使う）


def test_get_is_idempotent_and_keeps_edits(client: TestClient) -> None:
    sprint = _create_sprint(client)
    first = client.get(_daily_url(sprint["id"]))
    etag = first.headers["ETag"]
    # 議事録を書く。
    client.patch(
        _daily_url(sprint["id"]),
        json={"minutes": "書いた"},
        headers={"If-Match": etag},
    )
    # 2回目の GET は既存を返し、編集が消えない（空で上書きしない）。
    again = client.get(_daily_url(sprint["id"]))
    assert again.json()["minutes"] == "書いた"


def test_get_makes_one_document_per_day(client: TestClient) -> None:
    sprint = _create_sprint(client)
    first = client.get(_daily_url(sprint["id"])).json()
    second = client.get(_daily_url(sprint["id"])).json()
    assert first["id"] == second["id"]  # 同じ (sprint, date) は同じ1件


def test_get_separates_notes_by_date(client: TestClient) -> None:
    sprint = _create_sprint(client)
    a = client.get(_daily_url(sprint["id"], "2026-08-05")).json()
    b = client.get(_daily_url(sprint["id"], "2026-08-06")).json()
    assert a["id"] != b["id"]
    assert a["date"] == "2026-08-05"
    assert b["date"] == "2026-08-06"


def test_get_unknown_sprint_is_404(client: TestClient) -> None:
    res = client.get(_daily_url("spr_does_not_exist"))
    assert res.status_code == 404


def test_get_invalid_date_is_422(client: TestClient) -> None:
    sprint = _create_sprint(client)
    res = client.get(_daily_url(sprint["id"], "2026-13-40"))
    assert res.status_code == 422
    violations = res.json()["violations"]
    assert violations[0]["rule"] == "daily-note-date"


def test_get_malformed_date_is_422(client: TestClient) -> None:
    sprint = _create_sprint(client)
    res = client.get(_daily_url(sprint["id"], "2026-8-5"))  # ゼロ埋めでない
    assert res.status_code == 422


# --- PATCH（編集・楽観排他） --------------------------------------------------


def test_patch_updates_agenda_and_minutes(client: TestClient) -> None:
    sprint = _create_sprint(client)
    etag = client.get(_daily_url(sprint["id"])).headers["ETag"]

    res = client.patch(
        _daily_url(sprint["id"]),
        json={
            "agenda": [{"id": "a1", "text": "昨日やったこと", "done": False}],
            "minutes": "## 議事録",
        },
        headers={"If-Match": etag},
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["agenda"] == [{"id": "a1", "text": "昨日やったこと", "done": False}]
    assert body["minutes"] == "## 議事録"
    assert res.headers["ETag"] != etag  # 版が回る


def test_patch_partial_leaves_untouched_fields(client: TestClient) -> None:
    sprint = _create_sprint(client)
    etag = client.get(_daily_url(sprint["id"])).headers["ETag"]
    # まず agenda を入れる。
    res1 = client.patch(
        _daily_url(sprint["id"]),
        json={"agenda": [{"id": "a1", "text": "x", "done": True}]},
        headers={"If-Match": etag},
    )
    # 次に minutes だけを更新——agenda は据え置かれる。
    res2 = client.patch(
        _daily_url(sprint["id"]),
        json={"minutes": "追記"},
        headers={"If-Match": res1.headers["ETag"]},
    )
    body = res2.json()
    assert body["minutes"] == "追記"
    assert body["agenda"] == [{"id": "a1", "text": "x", "done": True}]


def test_patch_without_if_match_is_428(client: TestClient) -> None:
    sprint = _create_sprint(client)
    client.get(_daily_url(sprint["id"]))
    res = client.patch(_daily_url(sprint["id"]), json={"minutes": "x"})
    assert res.status_code == 428


def test_patch_with_stale_if_match_is_412(client: TestClient) -> None:
    sprint = _create_sprint(client)
    etag = client.get(_daily_url(sprint["id"])).headers["ETag"]
    # 1回更新して版を回す。
    client.patch(_daily_url(sprint["id"]), json={"minutes": "一手目"}, headers={"If-Match": etag})
    # 古い版で更新しようとすると 412（黙って上書きさせない — D-24）。
    res = client.patch(
        _daily_url(sprint["id"]), json={"minutes": "上書き"}, headers={"If-Match": etag}
    )
    assert res.status_code == 412


def test_patch_before_get_is_404(client: TestClient) -> None:
    # GET（get-or-create）を通さずいきなり PATCH するとノートが無いので 404。
    sprint = _create_sprint(client)
    res = client.patch(
        _daily_url(sprint["id"]), json={"minutes": "x"}, headers={"If-Match": '"nope"'}
    )
    assert res.status_code == 404


def test_patch_invalid_date_is_422(client: TestClient) -> None:
    sprint = _create_sprint(client)
    res = client.patch(
        _daily_url(sprint["id"], "not-a-date"),
        json={"minutes": "x"},
        headers={"If-Match": '"x"'},
    )
    assert res.status_code == 422


# --- 認可 --------------------------------------------------------------------


def test_get_by_non_member_is_403(repo: InMemoryRepository) -> None:
    client = _client(_build_app(repo), as_oid=STRANGER_OID)
    res = client.get(_daily_url("spr_anything"))
    assert res.status_code == 403


def test_get_unauthenticated_is_401(repo: InMemoryRepository) -> None:
    client = _client(_build_app(repo), as_oid=None)
    res = client.get(_daily_url("spr_anything"))
    assert res.status_code == 401
    assert res.headers.get("WWW-Authenticate") == "Bearer"


def test_get_without_db_is_503() -> None:
    client = _client(_build_app(None), as_oid=MEMBER_OID)
    res = client.get(_daily_url("spr_anything"))
    assert res.status_code == 503
