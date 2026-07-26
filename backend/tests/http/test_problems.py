"""problem+json エラー応答の契約（B-12・D-20）。

本番の CRUD は B-15 以降で入る。ここではその土台となる翻訳ハンドラを、各層の例外を
投げるテスト専用 probe ルートに載せ、**RFC 9457 の形／ステータス割当／violations の
機械可読性**を端から端まで確かめる。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.data.errors import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    ReservedProductIdError,
)
from app.http import InvariantViolation, Violation, install_error_handlers


class _Body(BaseModel):
    name: str
    count: int


def _build_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom/not-found")
    def _not_found() -> None:
        raise NotFoundError("PBI は存在しません")

    @app.get("/boom/conflict")
    def _conflict() -> None:
        raise ConflictError("id が重複しています")

    @app.get("/boom/precondition-failed")
    def _precondition_failed() -> None:
        raise PreconditionFailedError("_etag が一致しません")

    @app.get("/boom/reserved")
    def _reserved() -> None:
        raise ReservedProductIdError("_system は予約語です")

    @app.get("/boom/invariant")
    def _invariant() -> None:
        raise InvariantViolation(
            [Violation(rule="I-4", field="pbiId", message="taskType='team' のとき pbiId は null")]
        )

    @app.post("/echo")
    def _echo(body: _Body) -> dict[str, object]:
        return {"name": body.name, "count": body.count}

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_app())


def test_problem_content_type_and_shape(client: TestClient) -> None:
    res = client.get("/boom/not-found")

    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")
    body = res.json()
    assert body["status"] == 404
    assert body["type"].endswith("/errors/not-found")
    assert body["title"]
    assert body["detail"] == "PBI は存在しません"
    assert body["instance"] == "/boom/not-found"


@pytest.mark.parametrize(
    ("path", "status", "slug"),
    [
        ("/boom/not-found", 404, "not-found"),
        ("/boom/conflict", 409, "conflict"),
        ("/boom/precondition-failed", 412, "precondition-failed"),
        ("/boom/reserved", 422, "validation"),
    ],
)
def test_data_errors_map_to_status(client: TestClient, path: str, status: int, slug: str) -> None:
    # データ層の例外が http_status どおりのコードと type に翻訳される（D-20 の割当表）。
    res = client.get(path)

    assert res.status_code == status
    assert res.json()["type"].endswith(f"/errors/{slug}")


def test_invariant_violation_carries_rule_id(client: TestClient) -> None:
    # 「弾いたか」だけでなく「どの規則で弾いたか」まで機械可読（D-20 の要点）。
    res = client.get("/boom/invariant")

    assert res.status_code == 422
    body = res.json()
    assert body["type"].endswith("/errors/invariant-violation")
    assert body["violations"] == [
        {"rule": "I-4", "field": "pbiId", "message": "taskType='team' のとき pbiId は null"}
    ]


def test_request_validation_becomes_problem_with_violations(client: TestClient) -> None:
    # FastAPI のリクエスト検証失敗も素の {"detail": [...]} ではなく problem+json にする。
    res = client.post("/echo", json={"count": "not-an-int"})

    assert res.status_code == 422
    assert res.headers["content-type"].startswith("application/problem+json")
    body = res.json()
    fields = {v["field"] for v in body["violations"]}
    # name 欠落と count 型不正の両方が violations に機械可読で載る。
    assert "name" in fields
    assert "count" in fields


def test_invariant_violation_requires_at_least_one(client: TestClient) -> None:
    with pytest.raises(ValueError):
        InvariantViolation([])
