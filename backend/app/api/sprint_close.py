"""スプリント終了処理の専用エンドポイント（B-25・I-5・D-20）。

「スプリントを終了」を **プレビュー（GET）** と **確定（POST）** の2手に分ける（D-20。
頻度は低いが取り返しのつかない操作なので、事実を見せてから確定する — 提案書 07章・P-1）:

* ``GET  .../sprints/{sid}/close/preview`` — 締めたときに**持ち越される一覧**（このスプリント
  の未完了タスク）を返す。読み取りのみで状態は変えない。強制も警告もせず事実だけ見せる（P-1）。
* ``POST .../sprints/{sid}/close`` — ``nextSprintId`` を受け取り、未完了タスクをそこへ移して
  スプリントを ``closed`` にする（完了タスクは動かさない — I-5）。持ち越した件数を返す。

実体（未完了だけを次スプリントへ移し、完了は凍結し、スプリントを締める）はデータ層
（:mod:`app.data.sprint_close`）に閉じる（D-20。複数ドキュメントを1規則で束ねる操作を
汎用 ``PATCH`` に分解するとクライアントに規則が漏れる）。この層は認可・実在確認・状態遷移の
検査・HTTP への翻訳だけを担う。

規約はこの層に閉じ、ハンドラに書き散らさない（D-20）:

* **認可** — :func:`~app.authz.require_member` に依存するだけで**非メンバーは 403**（B-09）。
  認証・401・DB 未構成 503 もこの依存が担う。
* **実在確認** — 締める対象・移動先スプリントが無ければ **404**（存在を漏らさない）。
* **締められる状態か** — 締められるのは **``active`` のスプリントだけ**（未開始の ``planned``
  や既に ``closed`` は 422）。状態機械（planned → active → closed）と揃える（B-21）。
* **移動先の妥当性** — 移動先が締める対象と同じ／既に ``closed`` なら **422**（自己持ち越し・
  終了済みへの持ち越しを塞ぐ）。
* **``If-Match`` は取らない** — 分割（B-19）・プランニング（B-22）と同じく、複数タスクを
  1規則で束ねて動かす**サーバー所有のドメイン操作**であり、クライアントが版を持つ単一
  リソースの更新ではない（個々の楽観排他はデータ層が読み直した ``_etag`` で内部的に満たす）。

DB を触るため各ハンドラは ``def``（同期）で書き、FastAPI がスレッドプールに逃がす。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from ..authz import Membership, get_repository, require_member
from ..data import Repository
from ..data.sprint_close import carry_over_targets, close_sprint
from ..data.sprints import SprintStatus, get_sprint
from ..data.tasks import TaskType
from ..http import ProblemException, Violation, problem_responses, set_etag
from .sprints import Sprint

router = APIRouter(
    prefix="/api/products/{product_id}/sprints/{sprint_id}/close",
    tags=["sprint-close"],
)


# --- 入出力モデル（OpenAPI に載り、フロントの型生成が拾う。D-20） ----------------


class CarryOverTask(BaseModel):
    """持ち越しプレビューの1行。人が「何が次へ移るか」を読める最小限に絞る。

    プレビューは事実を見せるだけ（P-1）なので版（``_etag``）は載せない——確定
    （``POST .../close``）は ``If-Match`` を取らないサーバー所有の操作で、クライアントが
    個々のタスクの版を運ぶ必要がないため（ボードの :class:`BoardTask` とは非対称）。
    """

    id: str
    title: str
    taskType: TaskType
    status: str


class ClosePreview(BaseModel):
    """締めたときに持ち越される一覧（このスプリントの未完了タスク）。完了タスクは含めない（I-5）。"""

    tasks: list[CarryOverTask]


class CloseRequest(BaseModel):
    """スプリント終了の確定入力。未完了タスクの**移動先スプリント**を指定する。

    ``nextSprintId`` は既存の別スプリント（``planned`` or ``active``）を指す。フロントは
    「次スプリント」を先に作ってからその id を渡す（提案書 07章 ``sprintId = <nextSprintId>``）。
    """

    nextSprintId: str


class CloseResult(BaseModel):
    """スプリント終了の結果。締めたスプリントと**持ち越した件数**を返す（事実の提示 — P-1）。"""

    sprint: Sprint
    carriedOver: int


# --- エンドポイント ----------------------------------------------------------


@router.get(
    "/preview",
    response_model=ClosePreview,
    responses=problem_responses(401, 403, 404, 503),
)
def preview(
    sprint_id: str,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> object:
    """締めたときに持ち越される一覧（未完了タスク）を返す。読み取りのみ（P-1）。"""
    _require_sprint(repo, membership.product_id, sprint_id)
    targets = carry_over_targets(repo, product_id=membership.product_id, sprint_id=sprint_id)
    return {"tasks": targets}


@router.post(
    "",
    response_model=CloseResult,
    responses=problem_responses(401, 403, 404, 422, 503),
)
def close(
    sprint_id: str,
    body: CloseRequest,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> object:
    """スプリントを締める。未完了タスクを ``nextSprintId`` へ移し、状態を ``closed`` にする。"""
    product_id = membership.product_id
    sprint = _require_sprint(repo, product_id, sprint_id)
    _require_active(sprint)
    _require_valid_target(repo, product_id, sprint_id, body.nextSprintId)
    carried = close_sprint(
        repo,
        product_id=product_id,
        sprint=sprint,
        next_sprint_id=body.nextSprintId,
        actor=membership.oid,
    )
    closed = _require_sprint(repo, product_id, sprint_id)
    set_etag(response, closed)
    return {"sprint": closed, "carriedOver": len(carried)}


# --- ヘルパ ------------------------------------------------------------------


def _require_sprint(repo: Repository, product_id: str, sprint_id: str) -> dict:
    """スプリントを引き、無ければ 404（論理削除済みも 404。存在を漏らさない）。"""
    doc = get_sprint(repo, product_id=product_id, sprint_id=sprint_id)
    if doc is None:
        raise ProblemException(status.HTTP_404_NOT_FOUND, detail="スプリントが見つかりません")
    return doc


def _require_active(sprint: dict) -> None:
    """締められるのは ``active`` のスプリントだけ（未開始・終了済みは 422）。"""
    if sprint["status"] == SprintStatus.ACTIVE.value:
        return
    raise ProblemException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="スプリントを終了できません",
        type_slug="invalid-sprint-close",
        detail="終了できるのは実行中（active）のスプリントだけです",
        violations=[
            Violation(
                rule="sprint-close-status",
                field="status",
                message="スプリントは active のときだけ終了（closed）できます",
            )
        ],
    )


def _require_valid_target(
    repo: Repository, product_id: str, sprint_id: str, next_sprint_id: str
) -> None:
    """移動先スプリントの妥当性を確かめる。無ければ 404、自己指定／終了済みは 422。"""
    if next_sprint_id == sprint_id:
        raise _target_violation("持ち越し先は終了するスプリントと別でなければなりません")
    target = get_sprint(repo, product_id=product_id, sprint_id=next_sprint_id)
    if target is None:
        raise ProblemException(
            status.HTTP_404_NOT_FOUND, detail="持ち越し先のスプリントが見つかりません"
        )
    if target["status"] == SprintStatus.CLOSED.value:
        raise _target_violation("持ち越し先のスプリントは終了済みです")


def _target_violation(message: str) -> ProblemException:
    """移動先が不正なときの 422 problem（``rule='sprint-close-target'``）。"""
    return ProblemException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="持ち越し先のスプリントが不正です",
        type_slug="invalid-sprint-close-target",
        detail=message,
        violations=[Violation(rule="sprint-close-target", field="nextSprintId", message=message)],
    )
