"""``If-Match`` 必須（428）と ``ETag`` 応答の契約（B-12・D-20）。

``PATCH`` / ``DELETE`` から ``If-Match`` を省ける経路が存在しないことを、依存を載せた
テスト専用ルートで確かめる。単一ドキュメント応答が ``ETag`` を返すことも検証する。
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI, Response
from fastapi.testclient import TestClient

from app.http import install_error_handlers, require_if_match, set_etag


def _build_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.patch("/api/products/{product_id}/things/{thing_id}")
    def _update(
        product_id: str, thing_id: str, if_match: str = Depends(require_if_match)
    ) -> dict[str, str]:
        # ハンドラは受け取った If-Match をそのまま repo.replace(if_match=...) に渡す想定。
        return {"id": thing_id, "ifMatch": if_match}

    @app.get("/api/products/{product_id}/things/{thing_id}")
    def _get(product_id: str, thing_id: str, response: Response) -> dict[str, str]:
        doc = {"id": thing_id, "_etag": "etag-abc"}
        set_etag(response, doc)
        return {"id": thing_id}

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_app())


def test_patch_without_if_match_is_428(client: TestClient) -> None:
    res = client.patch("/api/products/prd_x/things/thing_1")

    assert res.status_code == 428
    body = res.json()
    assert body["type"].endswith("/errors/precondition-required")
    assert res.headers["content-type"].startswith("application/problem+json")


def test_patch_with_if_match_passes_value_through(client: TestClient) -> None:
    res = client.patch("/api/products/prd_x/things/thing_1", headers={"If-Match": "etag-abc"})

    assert res.status_code == 200
    # 値は不透明にそのまま往復する（加工しない）。
    assert res.json()["ifMatch"] == "etag-abc"


def test_single_doc_response_returns_etag(client: TestClient) -> None:
    res = client.get("/api/products/prd_x/things/thing_1")

    assert res.status_code == 200
    assert res.headers.get("ETag") == "etag-abc"


def test_etag_round_trips_as_if_match(client: TestClient) -> None:
    # GET が返した ETag を If-Match にそのまま載せれば通る（クライアントの往復契約）。
    got = client.get("/api/products/prd_x/things/thing_1")
    etag = got.headers["ETag"]

    res = client.patch("/api/products/prd_x/things/thing_1", headers={"If-Match": etag})

    assert res.status_code == 200
    assert res.json()["ifMatch"] == etag
