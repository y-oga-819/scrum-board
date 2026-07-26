"""API 共通規約の実装（B-12・D-20）。

このパッケージは **HTTP 境界そのものの約束事**を一手に引き受ける。個々の CRUD
（B-15 以降）は、ここが用意した部品に依存するだけで規約に従える。規約をハンドラごとに
書き散らさないことが要点で、これは認可（:mod:`app.authz`）を各ハンドラの ``if`` では
なく依存で表したのと同じ発想である。

* :mod:`.problems` — RFC 9457 ``application/problem+json`` のモデルと例外
* :mod:`.handlers` — 例外を problem+json に翻訳するハンドラ（:func:`install_error_handlers`）
* :mod:`.preconditions` — ``If-Match`` 必須の依存（欠落は 428）と ``ETag`` 応答ヘルパ

**信頼境界はサーバーである（D-20）。** 不変条件 I-1〜I-7 は必ずサーバーで評価する。
フロントの同型チェックは UX 補助であって正ではない。だからこそ「弾いた」ことを
:class:`~app.http.problems.Violation` で機械可読に返し、どの条件で弾いたかまで
テストで固定できるようにする。
"""

from __future__ import annotations

from .handlers import install_error_handlers
from .preconditions import ETAG_HEADER, require_if_match, set_etag
from .problems import (
    InvariantViolation,
    Problem,
    ProblemException,
    ProblemResponse,
    Violation,
)

__all__ = [
    "ETAG_HEADER",
    "InvariantViolation",
    "Problem",
    "ProblemException",
    "ProblemResponse",
    "Violation",
    "install_error_handlers",
    "require_if_match",
    "set_etag",
]
