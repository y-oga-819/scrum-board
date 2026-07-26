"""楽観排他の HTTP 契約（B-12・D-20）。

``If-Match`` を **忘れられる状態を構造的に無くす**のがこの層の仕事。提案書が
「後から入れると全 API 改修になる」（06章）と書くとおり、最初から強制する。

* :func:`require_if_match` — ``PATCH`` / ``DELETE`` の依存。``If-Match`` が無ければ
  **428 Precondition Required**。あれば値を返し、ハンドラはそれを
  :meth:`~app.data.repository.Repository.replace` の ``if_match`` に渡す。
  不一致（412）はデータ層が投げる。
* :func:`set_etag` — 単一ドキュメント応答に ``ETag`` を載せるヘルパ。

``ETag`` / ``If-Match`` の値は**不透明**に扱う（ストアが採番する ``_etag`` をそのまま
往復させる）。中身を解釈しないので、Cosmos とフェイクで表現が違っても壊れない。
集約 GET（``/backlog`` ``/board``）は応答全体の ETag が意味を持てないため、各要素の
``_etag`` をフィールドとして返す（:func:`etag_of` はその取り出しにも使える）。
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import Response

from ..data.documents import Document
from ..data.errors import PreconditionRequiredError

ETAG_HEADER = "ETag"
IF_MATCH_HEADER = "If-Match"


def require_if_match(request: Request) -> str:
    """``If-Match`` を必須にする依存。欠落は 428（無条件更新を許さない。D-20）。

    428 で弾くのは、楽観排他を省ける経路を 1 つも残さないため。省略を黙って許すと、
    実装のどこか 1 箇所で更新が消える経路が残り、しかも朝会で 2 人が同時に触ったときにしか
    再現しない。:class:`~app.data.errors.PreconditionRequiredError` を再利用し、
    428 への翻訳はエラーハンドラ（:mod:`.handlers`）に一元化する。
    """
    if_match = request.headers.get(IF_MATCH_HEADER)
    if not if_match:
        raise PreconditionRequiredError("If-Match ヘッダが必要です（無条件更新は許可されません）")
    return if_match


def etag_of(doc: Document) -> str | None:
    """ドキュメントの ``_etag`` を取り出す（無ければ ``None``）。"""
    etag = doc.get("_etag")
    return etag if isinstance(etag, str) else None


def set_etag(response: Response, doc: Document) -> None:
    """単一ドキュメント応答に ``ETag`` を載せる（``_etag`` が無ければ何もしない）。

    クライアントはこの値を次の更新の ``If-Match`` にそのまま載せる（:func:`require_if_match`
    が受け取る）。値は不透明なので加工しない。
    """
    etag = etag_of(doc)
    if etag:
        response.headers[ETAG_HEADER] = etag
