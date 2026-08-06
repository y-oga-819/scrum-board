"""スプリント画面のボードの集約 GET（B-23・D-20）。

**読み取りは画面の都合に従う**（書き込みはリソース単位。D-20）。スプリント画面（画面B）が
必要とする「スプリント情報＋そのスプリントのタスク」を **1 往復**で返し、``タスク一覧 →
各タスクを引き直す`` のような N+1 を作らない。最頻出の画面（提案書 07章「ボード表示は
1 クエリで完結する」）なので軽く保つ。

* **各タスクは ``_etag`` を本文に載せる** — 集約 GET は応答全体の ``ETag`` ヘッダを持てない
  （複数ドキュメントを束ねるため意味を成さない）。フロントはボード操作（``todo`` / ``doing`` /
  ``done`` の移動＝ ``PATCH status``・ブロックフラグ＝ ``PATCH isBlocked``）のとき、対象
  タスクの ``_etag`` を ``If-Match`` に載せる（D-20）。版が噛み合わなければ 412 になり、
  フロントは黙って上書きせず最新を読み直す（D-24）。

* **カラムへの振り分けはしない** — ``todo`` / ``doing`` / ``done`` の 3 カラムへの束ねは
  ``status`` からの**導出**であって不変条件ではない（D-20 の信頼境界の但し書き）。サーバーは
  タスクを ``rank, id`` 順のフラットな列で返し、カラム分けはフロントが行う。二重の真実を
  作らないため、サーバーは並びだけを保証する。

進捗集計（提案書 05章の2本バーの分子分母）はこの集約に足す join point だが、**B-24（進捗表示）**
が所有する。ここでは ``sprint`` と ``tasks`` だけを返し、``BoardResponse`` を**オブジェクトで
包む**ことで、後から ``progress`` フィールドを破壊的でない形で足せるようにしておく（backlog を
オブジェクトで包んだのと同じ発想 — B-17）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from ..authz import Membership, get_repository, require_member
from ..data import Repository
from ..data.sprints import get_sprint
from ..data.tasks import list_sprint_tasks
from ..http import ProblemException, problem_responses
from .sprints import Sprint
from .tasks import Task

router = APIRouter(
    prefix="/api/products/{product_id}/sprints/{sprint_id}/board",
    tags=["board"],
)


class BoardTask(Task):
    """ボードに並ぶタスク。単一 GET の :class:`~app.api.tasks.Task` に ``_etag`` を足す
    （集約の各要素が版を本文で持つのは BacklogTask と同じ理由 — D-20）。
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    etag: str = Field(alias="_etag")


class BoardResponse(BaseModel):
    """スプリント画面の集約応答（B-23・D-20）。

    ``sprint`` はボード見出しの表示に使う（この画面ではスプリント自身は更新しないため
    ``_etag`` は持たせない。編集導線が要るのは終了処理 B-25）。``tasks`` はこのスプリントに
    属するタスクを ``rank, id`` 順で並べたもの（各要素が ``_etag`` を持つ）。進捗集計
    （2本バー）は B-24 がここに ``progress`` を足すため**オブジェクトで包む**。
    """

    sprint: Sprint
    tasks: list[BoardTask]


@router.get(
    "",
    response_model=BoardResponse,
    responses=problem_responses(401, 403, 404, 503),
)
def read_board(
    sprint_id: str,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> object:
    """ボードを 1 往復返す。スプリント情報＋そのスプリントのタスク（各要素に ``_etag``）。

    スプリントが存在しない／論理削除済みなら 404（存在を漏らさない）。タスクは ``sprintId``
    が一致するもの（pbi・team を問わない）を ``rank, id`` 順で返す。
    """
    sprint = get_sprint(repo, product_id=membership.product_id, sprint_id=sprint_id)
    if sprint is None:
        raise ProblemException(404, detail="スプリントが見つかりません")
    tasks = list_sprint_tasks(repo, membership.product_id, sprint_id)
    return {"sprint": sprint, "tasks": tasks}
