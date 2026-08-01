"""プロダクトバックログ画面の集約 GET（B-17・D-20）。

**読み取りは画面の都合に従う**（書き込みはリソース単位。D-20）。プロダクトバックログ
画面（画面A）が必要とする PBI 一覧を **1 往復**で返し、``PBI 一覧 → 各 PBI のタスク`` の
N+1 を作らない。並びの正はサーバー（``ORDER BY rank, id``）で、フロントは再ソートしない。

* **各要素は ``_etag`` を本文に載せる** — 集約 GET は応答全体の ``ETag`` ヘッダを持てない
  （複数ドキュメントを束ねるため意味を成さない）。クライアントは並び替え（``POST .../rank``）
  やステータス変更（``PATCH``）のとき、対象要素の ``_etag`` を ``If-Match`` に載せる（D-20）。
  単一ドキュメント GET（:mod:`app.api.pbis`）が ``_etag`` を本文から落とすのと逆で、ここは
  **意図して本文に含める**。

配下タスク・未割当チームタスクの結合はタスク層（B-20）が入った時点でこの集約へ足す。
その追加は「同じパーティションをもう一度型で舐めて ``pbiId`` で束ねる」だけで、PBI の並び
契約はここで完結しているため、追加時に本体を作り直さない（D-20 の画面単位 GET）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from ..authz import Membership, get_repository, require_member
from ..data import Repository
from ..data.pbis import list_backlog
from ..http import problem_responses
from .pbis import Pbi

router = APIRouter(prefix="/api/products/{product_id}/backlog", tags=["backlog"])


class BacklogPbi(Pbi):
    """バックログ 1 行分の PBI。単一 GET の :class:`~app.api.pbis.Pbi` に ``_etag`` を足す。

    集約 GET では版（``_etag``）を**本文のフィールド**として返す（D-20）。フロントはこの値を
    そのまま並び替え・ステータス変更の ``If-Match`` に使う。``_etag`` は先頭が下線のため
    Pydantic では別名を張る（フィールド名は ``etag``・入出力の別名は ``_etag``）。
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    etag: str = Field(alias="_etag")


class BacklogResponse(BaseModel):
    """プロダクトバックログ画面の集約応答（B-17・D-20）。

    今は PBI 一覧のみ。配下タスク・未割当チームタスクはタスク層（B-20）で足すため、
    **オブジェクトで包む**（フィールド追加で拡張でき、素の配列のように破壊的にならない）。
    """

    pbis: list[BacklogPbi]


@router.get(
    "",
    response_model=BacklogResponse,
    responses=problem_responses(401, 403, 503),
)
def read_backlog(
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> object:
    """バックログを ``rank, id`` 順で 1 往復返す。各 PBI に ``_etag`` を含む。"""
    pbis = list_backlog(repo, membership.product_id)
    return {"pbis": pbis}
