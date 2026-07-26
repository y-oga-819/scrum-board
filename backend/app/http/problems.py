"""RFC 9457 ``application/problem+json`` のモデルと例外（B-12・D-20）。

エラー形式を標準に乗せると、拡張のたびの「形式どうする」議論が終わる（**P-2**）。
本文の要点は拡張メンバー ``violations`` で、**どの不変条件で弾いたか**を機械可読に
残す。これで D-19 のテーブル駆動テストが「弾かれたか」だけでなく「``I-4`` を意図した
入力が本当に ``I-4`` で弾かれたか」まで検証でき、偽陽性（``I-3`` で弾かれて通る）を防ぐ。

``type`` はエラー種別を指す URI。解決可能である必要はなく、**安定した識別子**であれば
よい（RFC 9457 §3.1.1）。リポジトリ配下の固定 URI を使う。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ``type`` URI の接頭辞。スラグを足してエラー種別ごとの安定 URI にする。
PROBLEM_TYPE_BASE = "https://github.com/y-oga-819/scrum-board/errors/"

# ステータスコードごとの既定スラグとタイトル（D-20 の割当表）。``ProblemException`` が
# 明示のスラグ／タイトルを持たないとき、また ``HTTPException`` / ``DataError`` を翻訳する
# ときの既定になる。detail（人間向けの個別説明）は例外側が持つ。
STATUS_PROBLEMS: Mapping[int, tuple[str, str]] = {
    401: ("unauthenticated", "認証が必要です"),
    403: ("forbidden", "このプロダクトのメンバーではありません"),
    404: ("not-found", "リソースが見つかりません"),
    409: ("conflict", "リソースが競合しています"),
    412: ("precondition-failed", "楽観排他に失敗しました"),
    422: ("validation", "入力が不正です"),
    428: ("precondition-required", "If-Match ヘッダが必要です"),
    503: ("service-unavailable", "サービスが利用できません"),
}
_FALLBACK_PROBLEM = ("internal-error", "サーバー内部エラー")


def type_uri(slug: str) -> str:
    """スラグを安定した ``type`` URI にする。"""
    return PROBLEM_TYPE_BASE + slug


def title_for(status: int) -> tuple[str, str]:
    """ステータスコードから既定の ``(type スラグ, title)`` を引く。"""
    return STATUS_PROBLEMS.get(status, _FALLBACK_PROBLEM)


class Violation(BaseModel):
    """``violations`` の 1 要素。**どの規則で弾いたか**を機械可読にする（D-20）。

    ``rule`` は不変条件 ID（``I-4`` など）。リクエストバリデーション由来のときは
    pydantic のエラー種別（``missing`` など）を入れる。``field`` は対象フィールド
    （不明・複数なら ``None``）。
    """

    rule: str
    field: str | None = None
    message: str


class Problem(BaseModel):
    """RFC 9457 の problem 本体。OpenAPI にも載せ、フロントの型生成が拾う（D-20）。"""

    type: str
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    violations: list[Violation] | None = None


class ProblemResponse(JSONResponse):
    """``application/problem+json`` を Content-Type に持つ JSON 応答。"""

    media_type = "application/problem+json"


class ProblemException(Exception):
    """problem+json として返したい HTTP エラー。

    ハンドラ（:mod:`.handlers`）がこれを拾って :class:`ProblemResponse` に翻訳する。
    ``type_slug`` / ``title`` を省くと :data:`STATUS_PROBLEMS` の既定を使う。``headers`` は
    そのまま応答に載る（401 の ``WWW-Authenticate`` など）。
    """

    def __init__(
        self,
        status: int,
        *,
        detail: str | None = None,
        title: str | None = None,
        type_slug: str | None = None,
        violations: Sequence[Violation] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        default_slug, default_title = title_for(status)
        self.status = status
        self.detail = detail
        self.title = title or default_title
        self.type_slug = type_slug or default_slug
        self.violations = list(violations) if violations is not None else None
        self.headers = dict(headers) if headers is not None else None
        super().__init__(detail or self.title)

    def to_problem(self, *, instance: str | None = None) -> Problem:
        """応答本体に載せる :class:`Problem` を組み立てる。"""
        return Problem(
            type=type_uri(self.type_slug),
            title=self.title,
            status=self.status,
            detail=self.detail,
            instance=instance,
            violations=self.violations,
        )


class InvariantViolation(ProblemException):
    """不変条件 I-1〜I-7 に違反した（422）。**必ず ``violations`` を伴う**（D-20）。

    サーバーが信頼境界であり、不変条件の判定はここでしか行わない。弾いた事実だけでなく
    弾いた規則（``I-4`` 等）を ``violations`` に載せ、テストがそこまで固定できるようにする。
    バリデーション関数（B-20 で I-1〜I-5 を単一関数に集約）が生成する ``Violation`` を渡す。
    """

    def __init__(
        self,
        violations: Sequence[Violation],
        *,
        detail: str | None = None,
    ) -> None:
        if not violations:
            raise ValueError("InvariantViolation は少なくとも 1 件の violation を要する")
        super().__init__(
            422,
            detail=detail,
            title="不変条件に違反しています",
            type_slug="invariant-violation",
            violations=violations,
        )
