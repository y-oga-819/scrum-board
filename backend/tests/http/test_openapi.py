"""OpenAPI に共通エラー契約が載ることの検証（B-12・D-20）。

OpenAPI を単一の真実としてフロントの型を生成する以上、``Problem`` がスキーマに
含まれていなければならない。含まれていないと、生成された型がエラー本体を知らず、
フロントが素の any でエラーを扱う穴が空く。
"""

from __future__ import annotations

from fastapi import FastAPI

from app.http import build_openapi, install_error_handlers, install_openapi, problem_responses


def test_problem_and_violation_are_in_components() -> None:
    app = FastAPI()
    install_error_handlers(app)
    install_openapi(app)

    schemas = build_openapi(app)["components"]["schemas"]

    assert "Problem" in schemas
    assert "Violation" in schemas
    # Problem は violations に Violation の配列を持つ（機械可読な規則 ID の器）。
    props = schemas["Problem"]["properties"]
    assert "violations" in props
    assert "status" in props


def test_problem_responses_reference_problem_schema() -> None:
    responses = problem_responses(404, 412, 428)

    assert set(responses) == {404, 412, 428}
    content = responses[412]["content"]["application/problem+json"]
    assert content["schema"]["$ref"].endswith("/Problem")


def test_the_real_app_publishes_problem_schema() -> None:
    from app.main import app

    schemas = app.openapi()["components"]["schemas"]

    assert "Problem" in schemas
