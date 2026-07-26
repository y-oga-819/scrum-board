"""例外を RFC 9457 ``application/problem+json`` に翻訳する（B-12・D-20）。

各層は HTTP を知らないまま自分の語彙で例外を投げる。ここが**唯一の翻訳点**として
それを problem+json に整える。翻訳の対象は 4 系統:

* :class:`~app.http.problems.ProblemException` — API 層が明示的に投げる problem
  （不変条件違反 :class:`~app.http.problems.InvariantViolation` を含む）
* :class:`~app.data.errors.DataError` — データ層の例外。``http_status`` で振り分ける
  （404 / 409 / 412 / 422 / 428。データ層は HTTP を知らない）
* :class:`RequestValidationError` — FastAPI のリクエスト検証失敗を 422 の problem にし、
  各エラーを ``violations`` へ機械可読に落とす
* :class:`HTTPException` — 既存の 401 / 403 / 503 などを problem+json に揃える
  （``WWW-Authenticate`` 等のヘッダは保持する）

これで「素の ``{"detail": ...}``」と「problem+json」が混在する状態を無くす。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from ..data.errors import DataError
from .problems import (
    Problem,
    ProblemException,
    ProblemResponse,
    Violation,
    title_for,
    type_uri,
)

# add_exception_handler は「基底 Exception を受ける」ハンドラ型を要求する。各ハンドラは
# 具体的な例外型で受けたいので、登録時にこの型へ cast する（実行時の振り分けは正しい）。
_Handler = Callable[[Request, Any], Response]


def _render(problem: Problem, *, headers: dict[str, str] | None = None) -> ProblemResponse:
    """``Problem`` を problem+json 応答にする。

    任意メンバー（``detail`` / ``instance`` / ``violations``）は**省略せず明示的な
    ``null`` として載せる**。生成した TypeScript 型（`Problem`）はこれらを必須・nullable
    として持つため、本文と型を一致させておくとフロントが `undefined` と `null` を
    使い分けずに済む（OpenAPI を単一の真実にする以上、本文がそこからズレない）。
    """
    body = problem.model_dump()
    return ProblemResponse(status_code=problem.status, content=body, headers=headers)


def _handle_problem(request: Request, exc: ProblemException) -> ProblemResponse:
    return _render(exc.to_problem(instance=request.url.path), headers=exc.headers)


def _handle_data_error(request: Request, exc: DataError) -> ProblemResponse:
    # データ層は HTTP を知らないため、ここで http_status からタイトル／type を与える。
    # detail は例外メッセージ（予約語 productId 等、原因が利用者に有益なもの）。
    status = exc.http_status
    slug, title = title_for(status)
    problem = Problem(
        type=type_uri(slug),
        title=title,
        status=status,
        detail=str(exc) or None,
        instance=request.url.path,
    )
    return _render(problem)


def _handle_validation_error(request: Request, exc: RequestValidationError) -> ProblemResponse:
    # FastAPI（pydantic）のリクエスト検証失敗。各エラーを violations に落とし、
    # どの項目がどの規則で弾かれたかを機械可読にする。rule には pydantic の
    # エラー種別（missing / string_type 等）を入れる（不変条件 I-* とは別系統）。
    violations = [
        Violation(
            rule=str(err.get("type", "validation")),
            field=_loc_to_field(err.get("loc", ())),
            message=str(err.get("msg", "")),
        )
        for err in exc.errors()
    ]
    slug, title = title_for(422)
    problem = Problem(
        type=type_uri(slug),
        title=title,
        status=422,
        detail="リクエストの内容が不正です",
        instance=request.url.path,
        violations=violations or None,
    )
    return _render(problem)


def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> ProblemResponse:
    # 既存の HTTPException（401 / 403 / 404 / 503 …）を problem+json に揃える。
    # detail が既定文言（種別タイトルと重複）でなければ本文に残す。ヘッダ
    # （401 の WWW-Authenticate など）は保持する。
    slug, title = title_for(exc.status_code)
    detail = exc.detail if isinstance(exc.detail, str) else None
    problem = Problem(
        type=type_uri(slug),
        title=title,
        status=exc.status_code,
        detail=detail if detail and detail != title else None,
        instance=request.url.path,
    )
    headers = dict(exc.headers) if exc.headers else None
    return _render(problem, headers=headers)


def _loc_to_field(loc: object) -> str | None:
    """pydantic の ``loc`` タプルを ``a.b`` 形式のフィールド名にする。

    先頭の ``body`` / ``query`` / ``path`` は入口の種別なので落とし、残りを繋ぐ。
    """
    if not isinstance(loc, (list, tuple)):
        return None
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header")]
    return ".".join(parts) or None


def install_error_handlers(app: FastAPI) -> None:
    """アプリに problem+json のハンドラを取り付ける（:mod:`app.main` が呼ぶ）。

    FastAPI 既定の ``HTTPException`` / ``RequestValidationError`` ハンドラを上書きし、
    すべてのエラー応答を problem+json に統一する。
    """
    app.add_exception_handler(ProblemException, cast(_Handler, _handle_problem))
    app.add_exception_handler(DataError, cast(_Handler, _handle_data_error))
    app.add_exception_handler(RequestValidationError, cast(_Handler, _handle_validation_error))
    app.add_exception_handler(StarletteHTTPException, cast(_Handler, _handle_http_exception))
