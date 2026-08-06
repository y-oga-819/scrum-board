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

進捗集計（提案書 05章の2本バーの分子分母）はこの集約の join point で、**B-24（進捗表示）**が
``progress`` フィールドとして足す。``BoardResponse`` は最初から**オブジェクトで包んで**あり
（backlog と同じ発想 — B-17）、``sprint`` / ``tasks`` を壊さずに ``progress`` を追加できた。
集計は既に引いた ``tasks`` から数えるだけで追加クエリを撃たず（N+1 を作らない）、マーカーの
「今日」は :func:`get_clock` が供給する（固定してテストできる — D-19・:mod:`app.data.clock`）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from ..authz import Membership, get_repository, require_member
from ..data import Repository
from ..data.clock import Clock, SystemClock, jst_date
from ..data.progress import ProgressSummary, compute_progress
from ..data.sprints import get_sprint
from ..data.tasks import list_sprint_tasks
from ..http import ProblemException, problem_responses
from .sprints import Sprint
from .tasks import Task


def get_clock(request: Request) -> Clock:
    """lifespan が ``app.state`` に置いた時計を取り出す（:mod:`app.main`）。

    ``get_repository`` と同型の供給口。営業日マーカーの「今日」を固定してテストできるよう、
    実装を差し替え可能にする（D-19）。未設定でも動くよう UTC の実時計にフォールバックする。
    テストは ``app.state.clock`` を固定時計に差し替える（repository と同じ流儀）。
    """
    return getattr(request.app.state, "clock", None) or SystemClock()


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


class ProgressBar(BaseModel):
    """2本バーの1本（完了 ``done`` / 総数 ``total``。提案書 05章）。"""

    done: int
    total: int


class Progress(BaseModel):
    """スプリントの進捗（2本バー＋営業日マーカー。B-24・提案書 05章）。

    ``planned``（計画タスク＝ ``taskType='pbi'``）と ``team``（チームタスク＝
    ``taskType='team'``）の2本を返す。マーカー位置は ``elapsedBusinessDays /
    totalBusinessDays``（経過営業日 ÷ 総営業日）。期間（``startDate`` / ``endDate``）が
    未設定なら営業日は **``null``**——フロントはマーカーを描かない（P-1）。
    """

    planned: ProgressBar
    team: ProgressBar
    elapsedBusinessDays: int | None
    totalBusinessDays: int | None


class BoardResponse(BaseModel):
    """スプリント画面の集約応答（B-23・B-24・D-20）。

    ``sprint`` はボード見出しの表示に使う（この画面ではスプリント自身は更新しないため
    ``_etag`` は持たせない。編集導線が要るのは終了処理 B-25）。``tasks`` はこのスプリントに
    属するタスクを ``rank, id`` 順で並べたもの（各要素が ``_etag`` を持つ）。``progress`` は
    2本バーの分子分母＋営業日マーカー（B-24）。件数は ``tasks`` から数えるだけで追加クエリを
    撃たない。
    """

    sprint: Sprint
    tasks: list[BoardTask]
    progress: Progress


@router.get(
    "",
    response_model=BoardResponse,
    responses=problem_responses(401, 403, 404, 503),
)
def read_board(
    sprint_id: str,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
    clock: Clock = Depends(get_clock),
) -> object:
    """ボードを 1 往復返す。スプリント情報＋そのスプリントのタスク（各要素に ``_etag``）＋進捗。

    スプリントが存在しない／論理削除済みなら 404（存在を漏らさない）。タスクは ``sprintId``
    が一致するもの（pbi・team を問わない）を ``rank, id`` 順で返す。進捗（2本バー＋営業日
    マーカー）は同じ ``tasks`` から数え、追加クエリを撃たない（B-24）。
    """
    sprint = get_sprint(repo, product_id=membership.product_id, sprint_id=sprint_id)
    if sprint is None:
        raise ProblemException(404, detail="スプリントが見つかりません")
    tasks = list_sprint_tasks(repo, membership.product_id, sprint_id)
    progress = compute_progress(
        tasks,
        start_date=sprint.get("startDate"),
        end_date=sprint.get("endDate"),
        today=jst_date(clock.now()),
    )
    return {"sprint": sprint, "tasks": tasks, "progress": _progress_body(progress)}


def _progress_body(summary: ProgressSummary) -> dict:
    """データ層の :class:`ProgressSummary`（snake_case）を応答モデルの形（camelCase）に写す。

    データ層は API のフィールド名（``elapsedBusinessDays`` 等）を知らない。翻訳はこの層で行う
    （ドメイン語彙が画面の語彙に侵食されないようにする — D-20）。
    """
    return {
        "planned": {"done": summary.planned.done, "total": summary.planned.total},
        "team": {"done": summary.team.done, "total": summary.team.total},
        "elapsedBusinessDays": summary.elapsed_business_days,
        "totalBusinessDays": summary.total_business_days,
    }
