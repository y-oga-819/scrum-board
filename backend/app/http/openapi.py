"""OpenAPI に共通のエラー契約を載せる（B-12・D-20）。

FastAPI は既定でバリデーションエラーを ``HTTPValidationError`` として文書化するが、
実際の応答は :mod:`.handlers` が problem+json に揃える。OpenAPI を**単一の真実**に
するには（そこからフロントの型を生成する以上）、``Problem`` をスキーマに載せておく
必要がある。ここでは ``Problem`` / ``Violation`` を必ず components に含める。

個々のエンドポイント（B-15 以降）は :func:`problem_responses` を ``responses`` に
展開して「この操作はどのコードで problem を返すか」を宣言する。宣言は生成される
TypeScript 型に伝播し、フロントがエラー本体を型付きで扱えるようになる。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from .problems import Problem

PROBLEM_MEDIA_TYPE = "application/problem+json"


def _problem_component_schemas() -> dict[str, Any]:
    """``Problem`` とその依存（``Violation``）の JSON Schema を components 形式で返す。"""
    schema = Problem.model_json_schema(ref_template="#/components/schemas/{model}")
    defs = schema.pop("$defs", {})
    return {"Problem": schema, **defs}


def problem_responses(
    *statuses: int, descriptions: Mapping[int, str] | None = None
) -> dict[int, dict[str, Any]]:
    """エンドポイントの ``responses`` に展開する problem 応答の宣言を作る。

    例: ``@router.patch(..., responses=problem_responses(404, 412, 428))``。
    各ステータスに ``Problem`` を参照する ``application/problem+json`` を割り当てる。
    """
    descriptions = descriptions or {}
    return {
        status: {
            "description": descriptions.get(status, "Problem"),
            "content": {PROBLEM_MEDIA_TYPE: {"schema": {"$ref": "#/components/schemas/Problem"}}},
        }
        for status in statuses
    }


def build_openapi(app: FastAPI) -> dict[str, Any]:
    """アプリの OpenAPI スキーマを組み立て、``Problem`` を components に必ず含める。

    :func:`fastapi.FastAPI.openapi` の差し替え先。生成結果はキャッシュされる
    （FastAPI の既定挙動に合わせる）。
    """
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    for name, sub in _problem_component_schemas().items():
        components.setdefault(name, sub)
    app.openapi_schema = schema
    return schema


def install_openapi(app: FastAPI) -> None:
    """``app.openapi`` を :func:`build_openapi` に差し替える。"""

    def _openapi() -> dict[str, Any]:
        return build_openapi(app)

    app.openapi = _openapi  # type: ignore[method-assign]


__all__: Sequence[str] = ["build_openapi", "install_openapi", "problem_responses"]
