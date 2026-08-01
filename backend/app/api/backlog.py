"""プロダクトバックログ画面の集約 GET（B-17・D-20）。

**読み取りは画面の都合に従う**（書き込みはリソース単位。D-20）。プロダクトバックログ
画面（画面A）が必要とする PBI 一覧を **1 往復**で返し、``PBI 一覧 → 各 PBI のタスク`` の
N+1 を作らない。並びの正はサーバー（``ORDER BY rank, id``）で、フロントは再ソートしない。

* **各要素は ``_etag`` を本文に載せる** — 集約 GET は応答全体の ``ETag`` ヘッダを持てない
  （複数ドキュメントを束ねるため意味を成さない）。クライアントは並び替え（``POST .../rank``）
  やステータス変更（``PATCH``）のとき、対象要素の ``_etag`` を ``If-Match`` に載せる（D-20）。
  単一ドキュメント GET（:mod:`app.api.pbis`）が ``_etag`` を本文から落とすのと逆で、ここは
  **意図して本文に含める**。PBI 配下のタスクも同じく各要素が ``_etag`` を持つ。

**配下タスクの結合（B-20）。** パーティションのタスクを 1 回だけ舐め、``pbiId`` で束ねて
各 PBI の ``tasks`` に載せる。``PBI 一覧 → 各 PBI ごとに tasks を引く`` の N+1 にはしない
（PBI の並び契約は B-17 で完結しているため、この追加で本体を作り直さない — D-20 の画面単位
GET）。ここで束ねるのは **pbi タスク**（``taskType='pbi'``）だけ。親 PBI を持たない
**未割当チームタスク**（``taskType='team'`` かつ ``sprintId=null``）を ``unassignedTeamTasks``
として露出するのは B-29（同じ join point に足す）。
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from ..authz import Membership, get_repository, require_member
from ..data import Repository
from ..data.pbis import list_backlog
from ..data.tasks import TaskType, list_tasks
from ..http import problem_responses
from .pbis import Pbi
from .tasks import Task

router = APIRouter(prefix="/api/products/{product_id}/backlog", tags=["backlog"])


class BacklogTask(Task):
    """バックログの PBI 配下に並ぶタスク。単一 GET の :class:`~app.api.tasks.Task` に
    ``_etag`` を足す（集約の各要素が版を本文で持つのは BacklogPbi と同じ理由 — D-20）。
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    etag: str = Field(alias="_etag")


class BacklogPbi(Pbi):
    """バックログ 1 行分の PBI。単一 GET の :class:`~app.api.pbis.Pbi` に ``_etag`` と
    **配下タスク**を足す。

    集約 GET では版（``_etag``）を**本文のフィールド**として返す（D-20）。フロントはこの値を
    そのまま並び替え・ステータス変更の ``If-Match`` に使う。``_etag`` は先頭が下線のため
    Pydantic では別名を張る（フィールド名は ``etag``・入出力の別名は ``_etag``）。``tasks`` は
    この PBI を親に持つ pbi タスクを ``rank, id`` 順で並べたもの（無ければ空配列）。
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    etag: str = Field(alias="_etag")
    tasks: list[BacklogTask] = []


class BacklogResponse(BaseModel):
    """プロダクトバックログ画面の集約応答（B-17・D-20）。

    PBI 一覧（各 PBI は配下タスクを ``tasks`` に持つ。B-20）。未割当チームタスクは B-29 で
    ``unassignedTeamTasks`` として足すため、**オブジェクトで包む**（フィールド追加で拡張でき、
    素の配列のように破壊的にならない）。
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
    """バックログを ``rank, id`` 順で 1 往復返す。各 PBI に ``_etag`` と配下タスクを含む。"""
    pbis = list_backlog(repo, membership.product_id)
    tasks_by_pbi = _group_pbi_tasks(list_tasks(repo, membership.product_id))
    return {"pbis": [{**pbi, "tasks": tasks_by_pbi.get(pbi["id"], [])} for pbi in pbis]}


def _group_pbi_tasks(tasks: list[dict]) -> dict[str, list[dict]]:
    """タスク列を親 ``pbiId`` ごとに束ねる（pbi タスクのみ。並びは入力の ``rank, id`` 順を保つ）。

    team タスクはここでは束ねない（未割当チームタスクの露出は B-29）。判別は ``taskType``
    で行い、``pbiId`` の有無では判断しない（I-4）。
    """
    grouped: dict[str, list[dict]] = defaultdict(list)
    for task in tasks:
        if task.get("taskType") == TaskType.PBI.value and task.get("pbiId"):
            grouped[task["pbiId"]].append(task)
    return grouped
