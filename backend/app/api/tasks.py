"""タスクの CRUD エンドポイント（B-20・D-20）。

スプリントの作業単位（task）を、リソース単位で作成・取得・更新・論理削除する。すべて
``/api/products/{product_id}/tasks`` の下にあり、:func:`~app.authz.require_member` に
依存するだけで**非メンバーは 403**（B-09）。認可・401・DB 未構成 503 はこの依存が担う。

不変条件はサーバーが唯一の判定者（D-20）。作成・更新のたびに
:func:`~app.data.tasks.check_invariants`（I-1〜I-4 を集約した純関数）へ結果ドキュメントを
通し、破っていれば **422** に ``violations``（``rule='I-3'`` 等）を添えて弾く。「どの条件で
弾いたか」を機械可読に返すことで、フロントの同型チェック（UX 補助）と二重管理にならない。

規約はこの層に閉じ、ハンドラに書き散らさない（D-20）:

* **楽観排他** — ``PATCH`` / ``DELETE`` は :func:`~app.http.require_if_match` に依存し、
  ``If-Match`` 欠落は **428**・不一致は **412**（データ層が投げる）。
* **完了地の刻印** — ``PATCH`` で ``status`` を ``done`` に動かす／から戻すと、
  :func:`~app.data.tasks.completion_changes` が ``completedAt`` を自動で刻む／消す
  （I-1・I-2 をクライアントに再実装させない。ボード B-23 も同じ経路を通る）。
* **単一ドキュメント応答は ``ETag``** ヘッダを返す（本文に ``_etag`` は載せない。集約 GET が
  各要素で返すのは :mod:`app.api.backlog`）。

DB を触るため各ハンドラは ``def``（同期）で書き、FastAPI がスレッドプールに逃がす。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..authz import Membership, get_repository, require_member
from ..data import Repository
from ..data.pbis import get_pbi
from ..data.tasks import (
    TaskStatus,
    TaskType,
    check_invariants,
    completion_changes,
    create_task,
    get_task,
)
from ..http import (
    InvariantViolation,
    ProblemException,
    Violation,
    problem_responses,
    require_if_match,
    set_etag,
)

router = APIRouter(prefix="/api/products/{product_id}/tasks", tags=["tasks"])


# --- 入出力モデル（OpenAPI に載り、フロントの型生成が拾う。D-20） ----------------


class TaskCreate(BaseModel):
    """タスク作成の入力。``taskType`` が判別子で必ず持つ（I-4）。

    ``taskType='pbi'`` なら ``pbiId`` が必須（I-3）、``taskType='team'`` なら ``pbiId`` は
    ``null``（I-4）。整合はサーバーが :func:`~app.data.tasks.check_invariants` で確かめる。
    作成はタイトルだけの**クイック追加**に絞る（``todo`` / ``memo`` / ``assigneeId`` の編集は
    後から ``PATCH`` で足す — タスク詳細の作り込みは本 PBI の範囲外）。``sprintId`` / ``rank`` /
    ``status`` も入力に取らない（プランニング B-22・ボード B-23 が所有し、作成時は必ず
    ``todo`` 状態 / ``sprintId=null``）。
    """

    taskType: TaskType
    pbiId: str | None = None
    title: str = Field(min_length=1)


class TaskUpdate(BaseModel):
    """タスク更新の入力（部分更新）。**送られたフィールドだけ**を反映する。

    ``taskType`` / ``pbiId`` は載せない（作成時に確定する判別子。後から種別を変えると
    バックログの束ね方 I-3・I-4 が崩れる）。``completedAt`` も載せない — ``status`` を
    ``done`` に動かすとサーバーが自動で刻む（:func:`~app.data.tasks.completion_changes`）。
    ``sprintId`` はプランニング（B-22）、``rank`` はボード（B-23）が専用経路で動かす。
    """

    title: str | None = Field(default=None, min_length=1)
    todo: str | None = None
    memo: str | None = None
    status: TaskStatus | None = None
    isBlocked: bool | None = None
    blockedReason: str | None = None
    assigneeId: str | None = None


class Task(BaseModel):
    """タスクの応答表現（提案書 04章のフィールド）。

    ``_etag`` は本文に載せず ``ETag`` ヘッダで返すため ``extra='ignore'`` で捨てる
    （単一ドキュメント応答の版はヘッダが正 — D-20）。
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    type: str
    productId: str
    isDeleted: bool
    createdAt: str
    createdBy: str
    updatedAt: str
    updatedBy: str
    taskType: TaskType
    pbiId: str | None
    sprintId: str | None
    status: TaskStatus
    completedAt: str | None
    title: str
    todo: str
    memo: str
    assigneeId: str | None
    rank: str | None
    isBlocked: bool
    blockedReason: str


# --- 不変条件 → 422 の翻訳（rule = 不変条件 ID。D-20） --------------------------

# 不変条件 ID → (対象フィールド, 人間向けメッセージ)。check_invariants が返した ID を
# violations に翻訳する唯一の対応表。ここを 1 箇所に閉じ、各ハンドラに撒かない。
_INVARIANT_FIELDS: dict[str, tuple[str, str]] = {
    "I-1": ("completedAt", "未完了のタスクに完了日時を持たせられません"),
    "I-2": ("completedAt", "完了したタスクは完了日時を持たなければなりません"),
    "I-3": ("pbiId", "PBI タスクには pbiId が必要です"),
    "I-4": ("pbiId", "チームタスクに pbiId を付けられません"),
}


def _reject_if_invalid(doc: dict) -> None:
    """タスク文書が不変条件を破っていれば 422（``violations`` に不変条件 ID を載せる）。"""
    violated = check_invariants(doc)
    if not violated:
        return
    raise InvariantViolation(
        [
            Violation(rule=inv, field=_INVARIANT_FIELDS[inv][0], message=_INVARIANT_FIELDS[inv][1])
            for inv in violated
        ]
    )


def _require_existing_pbi(repo: Repository, product_id: str, pbi_id: str) -> None:
    """親 PBI が同じパーティションに実在することを確かめる（無ければ 422）。

    I-3（pbiId 必須）を満たしていても、存在しない PBI を指すタスクは宙に浮く
    （バックログの束ね先が無い）。参照先の実在まで作成時に保証し、孤児タスクを作らせない。
    """
    if get_pbi(repo, product_id=product_id, pbi_id=pbi_id) is None:
        raise ProblemException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="親 PBI が存在しません",
            type_slug="invalid-task-pbi-ref",
            detail="指定された pbiId の PBI が存在しません",
            violations=[
                Violation(
                    rule="task-pbi-ref",
                    field="pbiId",
                    message="指定された pbiId の PBI が存在しません",
                )
            ],
        )


# --- エンドポイント ----------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Task,
    responses=problem_responses(401, 403, 422, 503),
)
def create(
    body: TaskCreate,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> object:
    """タスクを1件作成する。状態は必ず ``todo`` から始まる（提案書 図5）。

    ``taskType`` の整合（I-3・I-4）を作成前に検証し、``pbi`` タスクは親 PBI の実在も確かめる。
    ``team`` タスク（親 PBI なし）も作成できる（B-20 の完了条件）。
    """
    data = {
        "taskType": body.taskType.value,
        "pbiId": body.pbiId,
        "status": TaskStatus.TODO.value,
        "completedAt": None,
    }
    _reject_if_invalid(data)
    if body.taskType is TaskType.PBI and body.pbiId is not None:
        _require_existing_pbi(repo, membership.product_id, body.pbiId)
    doc = create_task(
        repo,
        product_id=membership.product_id,
        actor=membership.oid,
        task_type=body.taskType,
        title=body.title,
        pbi_id=body.pbiId,
    )
    set_etag(response, doc)
    return doc


@router.get(
    "/{task_id}",
    response_model=Task,
    responses=problem_responses(401, 403, 404, 503),
)
def get_one(
    task_id: str,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> object:
    """タスクを1件取得する。存在しない／論理削除済みは 404（存在を漏らさない）。"""
    doc = _load_or_404(repo, membership.product_id, task_id)
    set_etag(response, doc)
    return doc


@router.patch(
    "/{task_id}",
    response_model=Task,
    responses=problem_responses(401, 403, 404, 412, 422, 428, 503),
)
def update(
    task_id: str,
    body: TaskUpdate,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
    if_match: str = Depends(require_if_match),
) -> object:
    """タスクを部分更新する。``status`` を動かすと ``completedAt`` を自動で刻む／消す。"""
    current = _load_or_404(repo, membership.product_id, task_id)
    changes = body.model_dump(exclude_unset=True, mode="json")
    if "status" in changes:
        # done への出入りで completedAt を保つ（I-1・I-2 を 1 箇所に閉じる）。
        changes.update(
            completion_changes(
                current_status=current["status"],
                current_completed_at=current.get("completedAt"),
                target_status=changes["status"],
            )
        )
    _reject_if_invalid({**current, **changes})
    updated = repo.replace(
        product_id=membership.product_id,
        doc_id=task_id,
        changes=changes,
        actor=membership.oid,
        if_match=if_match,
    )
    set_etag(response, updated)
    return updated


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=problem_responses(401, 403, 404, 412, 428, 503),
)
def delete(
    task_id: str,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
    if_match: str = Depends(require_if_match),
) -> Response:
    """タスクを論理削除する（物理削除しない。D-07）。以後 GET は 404。"""
    _load_or_404(repo, membership.product_id, task_id)
    repo.soft_delete(
        product_id=membership.product_id,
        doc_id=task_id,
        actor=membership.oid,
        if_match=if_match,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- ヘルパ ------------------------------------------------------------------


def _load_or_404(repo: Repository, product_id: str, task_id: str) -> dict:
    """タスクを引き、無ければ 404 を投げる（論理削除済みも 404）。"""
    doc = get_task(repo, product_id=product_id, task_id=task_id)
    if doc is None:
        raise ProblemException(status.HTTP_404_NOT_FOUND, detail="タスクが見つかりません")
    return doc
