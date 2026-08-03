"""スプリントの CRUD エンドポイント（B-21・D-20）。

スプリント（``sprint``）を、リソース単位で作成・取得・一覧・更新・論理削除する。
すべて ``/api/products/{product_id}/sprints`` の下にあり、
:func:`~app.authz.require_member` に依存するだけで**非メンバーは 403**（B-09）。
認可・401・DB 未構成 503 はこの依存が担う。

規約はこの層に閉じ、ハンドラに書き散らさない（D-20）:

* **楽観排他** — ``PATCH`` / ``DELETE`` は :func:`~app.http.require_if_match` に依存し、
  ``If-Match`` 欠落は **428**。値はそのまま ``repo.replace`` / ``repo.soft_delete`` の
  ``if_match`` に渡し、不一致は **412**（データ層が投げる）。
* **状態遷移** — ``PATCH`` で ``status`` を動かすときだけ
  :func:`~app.data.sprints.is_valid_transition` で正当性を確かめ、不正なら **422** に
  ``violations``（``rule='sprint-status-transition'``）を添えて弾く。
* **期間** — ``startDate`` / ``endDate`` を動かすとき、更新後の期間が破れていれば
  **422**（``rule='sprint-period'``）。判断の余地がない入力エラー（終了 < 開始）だけを弾く。
* **単一ドキュメント応答は ``ETag``** ヘッダを返す（:func:`~app.http.set_etag`）。一覧
  （``GET``）は集約 GET と同じく各要素の ``_etag`` を**本文のフィールド**で返す（D-20）。

PBI の CRUD（:mod:`app.api.pbis`）と同じ組み立て。DB を触るため各ハンドラは ``def``
（同期）で書き、FastAPI がスレッドプールに逃がす。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..authz import Membership, get_repository, require_member
from ..data import Repository
from ..data.sprints import (
    SprintStatus,
    create_sprint,
    get_sprint,
    is_valid_period,
    is_valid_transition,
    list_sprints,
)
from ..http import (
    ProblemException,
    Violation,
    problem_responses,
    require_if_match,
    set_etag,
)

router = APIRouter(prefix="/api/products/{product_id}/sprints", tags=["sprints"])


# --- 入出力モデル（OpenAPI に載り、フロントの型生成が拾う。D-20） ----------------


class SprintCreate(BaseModel):
    """スプリント作成の入力。期間・ゴールは任意（計画中は未定のことがある）。

    ``number`` はサーバーが連番採番するため受け取らない（クライアントに採番させない）。
    ``status`` も受け取らない——作成時は必ず ``planned`` から始まる。
    """

    goal: str = ""
    startDate: str | None = None
    endDate: str | None = None


class SprintUpdate(BaseModel):
    """スプリント更新の入力（部分更新）。**送られたフィールドだけ**を反映する。

    ``number`` は載せない（採番はサーバーが所有し、後から振り直さない）。``status`` は
    状態機械（planned → active → closed）を通してのみ動かす。
    """

    goal: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    status: SprintStatus | None = None


class Sprint(BaseModel):
    """スプリントの応答表現（提案書 04章のフィールド）。

    単一ドキュメント応答（作成・取得・更新）では ``_etag`` を本文に載せず ``ETag``
    ヘッダで返すため ``extra='ignore'`` で捨てる。一覧は :class:`SprintListItem` が
    ``_etag`` を本文に持たせる（集約 GET と同じ非対称 — D-20）。
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
    number: int
    goal: str
    startDate: str | None
    endDate: str | None
    status: SprintStatus


class SprintListItem(Sprint):
    """一覧の1要素。集約 GET と同じく各要素が版（``_etag``）を本文で運ぶ（D-20）。

    一覧応答全体では単一の ``ETag`` を返せないため、フロントは各要素の ``_etag`` を
    そのスプリントへの ``PATCH`` / ``DELETE`` の ``If-Match`` にそのまま載せる。
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    etag: str = Field(alias="_etag")


# --- エンドポイント ----------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Sprint,
    responses=problem_responses(401, 403, 422, 503),
)
def create(
    body: SprintCreate,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> object:
    """スプリントを1件作成する。状態は必ず ``planned`` から始まる。"""
    if not is_valid_period(body.startDate, body.endDate):
        raise _period_violation()
    doc = create_sprint(
        repo,
        product_id=membership.product_id,
        actor=membership.oid,
        goal=body.goal,
        start_date=body.startDate,
        end_date=body.endDate,
    )
    set_etag(response, doc)
    return doc


@router.get(
    "",
    response_model=list[SprintListItem],
    responses=problem_responses(401, 403, 503),
)
def list_all(
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> object:
    """スプリントを**番号順**で一覧する。各要素が ``_etag`` を本文に持つ（D-20）。"""
    return list_sprints(repo, membership.product_id)


@router.get(
    "/{sprint_id}",
    response_model=Sprint,
    responses=problem_responses(401, 403, 404, 503),
)
def get_one(
    sprint_id: str,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> object:
    """スプリントを1件取得する。存在しない／論理削除済みは 404（存在を漏らさない）。"""
    doc = _load_or_404(repo, membership.product_id, sprint_id)
    set_etag(response, doc)
    return doc


@router.patch(
    "/{sprint_id}",
    response_model=Sprint,
    responses=problem_responses(401, 403, 404, 412, 422, 428, 503),
)
def update(
    sprint_id: str,
    body: SprintUpdate,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
    if_match: str = Depends(require_if_match),
) -> object:
    """スプリントを部分更新する。``status`` の遷移と期間の破れを更新前に確かめる。"""
    current = _load_or_404(repo, membership.product_id, sprint_id)
    changes = body.model_dump(exclude_unset=True, mode="json")
    if "status" in changes:
        _check_status_transition(current["status"], changes["status"])
    _check_period(current, changes)
    updated = repo.replace(
        product_id=membership.product_id,
        doc_id=sprint_id,
        changes=changes,
        actor=membership.oid,
        if_match=if_match,
    )
    set_etag(response, updated)
    return updated


@router.delete(
    "/{sprint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=problem_responses(401, 403, 404, 412, 428, 503),
)
def delete(
    sprint_id: str,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
    if_match: str = Depends(require_if_match),
) -> Response:
    """スプリントを論理削除する（物理削除しない。D-07）。以後 GET は 404。"""
    _load_or_404(repo, membership.product_id, sprint_id)
    repo.soft_delete(
        product_id=membership.product_id,
        doc_id=sprint_id,
        actor=membership.oid,
        if_match=if_match,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- ヘルパ ------------------------------------------------------------------


def _load_or_404(repo: Repository, product_id: str, sprint_id: str) -> dict:
    """スプリントを引き、無ければ 404 を投げる（論理削除済みも 404）。"""
    doc = get_sprint(repo, product_id=product_id, sprint_id=sprint_id)
    if doc is None:
        raise ProblemException(status.HTTP_404_NOT_FOUND, detail="スプリントが見つかりません")
    return doc


def _check_status_transition(current: str, target: str) -> None:
    """状態遷移が不正なら 422（``violations`` に規則 ID を載せる。D-20）。"""
    if is_valid_transition(SprintStatus(current), SprintStatus(target)):
        return
    raise ProblemException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="不正な状態遷移です",
        type_slug="invalid-status-transition",
        detail=f"'{current}' から '{target}' への状態遷移は許可されていません",
        violations=[
            Violation(
                rule="sprint-status-transition",
                field="status",
                message="スプリントの状態は planned → active → closed の順にのみ進められます",
            )
        ],
    )


def _check_period(current: dict, changes: dict) -> None:
    """更新後の期間（``startDate`` / ``endDate``）が破れていれば 422。

    部分更新なので、変更後の実効値（``changes`` にあればそれ、無ければ現行値）で判定する。
    片方だけ更新しても、もう片方の現行値と突き合わせて逆転を検出できる。
    """
    start = changes.get("startDate", current.get("startDate"))
    end = changes.get("endDate", current.get("endDate"))
    if not is_valid_period(start, end):
        raise _period_violation()


def _period_violation() -> ProblemException:
    """期間の逆転を 422 problem にする（``rule='sprint-period'``）。"""
    message = "終了日は開始日以降でなければなりません"
    return ProblemException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="スプリントの期間が不正です",
        type_slug="invalid-sprint-period",
        detail=message,
        violations=[Violation(rule="sprint-period", field="endDate", message=message)],
    )
