"""PBI の CRUD エンドポイント（B-15・D-20）。

プロダクトバックログの1項目（PBI）を、リソース単位で作成・取得・更新・論理削除する。
書き込みはドメインの語彙のまま（画面単位の読み取り ``/backlog`` は B-17）。すべて
``/api/products/{product_id}/pbis`` の下にあり、:func:`~app.authz.require_member` に
依存するだけで**非メンバーは 403**（B-09）。認可・401・DB 未構成 503 はこの依存が担う。

規約はこの層に閉じ、ハンドラに書き散らさない（D-20）:

* **楽観排他** — ``PATCH`` / ``DELETE`` は :func:`~app.http.require_if_match` に依存し、
  ``If-Match`` 欠落は **428**。値はそのまま ``repo.replace`` / ``repo.soft_delete`` の
  ``if_match`` に渡し、不一致は **412**（データ層が投げる）。
* **状態遷移** — ``PATCH`` で ``status`` を動かすときだけ
  :func:`~app.data.pbis.is_valid_transition` で正当性を確かめ、不正なら **422** に
  ``violations``（``rule='pbi-status-transition'``）を添えて弾く（提案書 図6）。
* **単一ドキュメント応答は ``ETag``** ヘッダを返す（:func:`~app.http.set_etag`）。本文には
  ``_etag`` を載せない（集約 GET が各要素で返すのは B-17）。

DB を触るため各ハンドラは ``def``（同期）で書き、FastAPI がスレッドプールに逃がす
（:mod:`app.data.repository` の方針。Cosmos の同期 SDK と噛み合う）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..authz import Membership, get_repository, require_member
from ..data import Repository
from ..data.pbis import PbiStatus, create_pbi, get_pbi, is_valid_transition
from ..http import (
    ProblemException,
    Violation,
    problem_responses,
    require_if_match,
    set_etag,
)

router = APIRouter(prefix="/api/products/{product_id}/pbis", tags=["pbis"])


# --- 入出力モデル（OpenAPI に載り、フロントの型生成が拾う。D-20） ----------------


class AcceptanceCriterion(BaseModel):
    """完了条件チェックリストの1項目（提案書 04章）。編集は B-18。"""

    id: str
    text: str
    checked: bool = False


class PbiCreate(BaseModel):
    """PBI 作成の入力。``title`` 以外は任意（未設定は既定値）。"""

    title: str = Field(min_length=1)
    description: str = ""
    acceptanceCriteria: list[AcceptanceCriterion] = []
    # 見積りは任意入力・未設定でも警告を出さない（D-06。編集 UX は B-18）。
    estimate: int | None = None


class PbiUpdate(BaseModel):
    """PBI 更新の入力（部分更新）。**送られたフィールドだけ**を反映する。

    ``rank`` / ``parentPbiId`` / ``completedAt`` / ``completedSprintId`` は載せない。
    それぞれ並び替え（B-16）・分割（B-19）・スプリント終了（B-25）が所有し、汎用 PATCH
    では動かさない（クライアントに完了地やランクの規則を漏らさない）。
    """

    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    acceptanceCriteria: list[AcceptanceCriterion] | None = None
    estimate: int | None = None
    status: PbiStatus | None = None


class Pbi(BaseModel):
    """PBI の応答表現（提案書 04章のフィールド）。

    保存ドキュメントから組み立てる。``_etag`` は本文に載せず ``ETag`` ヘッダで返すため
    ``extra='ignore'`` で捨てる（単一ドキュメント応答の版はヘッダが正 — D-20）。
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
    title: str
    description: str
    acceptanceCriteria: list[AcceptanceCriterion]
    status: PbiStatus
    estimate: int | None
    rank: str | None
    completedAt: str | None
    completedSprintId: str | None
    parentPbiId: str | None


# --- エンドポイント ----------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Pbi,
    responses=problem_responses(401, 403, 422, 503),
)
def create(
    body: PbiCreate,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> object:
    """PBI を1件作成する。状態は必ず ``new`` から始まる（提案書 図6）。"""
    doc = create_pbi(
        repo,
        product_id=membership.product_id,
        actor=membership.oid,
        title=body.title,
        description=body.description,
        acceptance_criteria=[ac.model_dump() for ac in body.acceptanceCriteria],
        estimate=body.estimate,
    )
    set_etag(response, doc)
    return doc


@router.get(
    "/{pbi_id}",
    response_model=Pbi,
    responses=problem_responses(401, 403, 404, 503),
)
def get_one(
    pbi_id: str,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> object:
    """PBI を1件取得する。存在しない／論理削除済みは 404（存在を漏らさない）。"""
    doc = _load_or_404(repo, membership.product_id, pbi_id)
    set_etag(response, doc)
    return doc


@router.patch(
    "/{pbi_id}",
    response_model=Pbi,
    responses=problem_responses(401, 403, 404, 412, 422, 428, 503),
)
def update(
    pbi_id: str,
    body: PbiUpdate,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
    if_match: str = Depends(require_if_match),
) -> object:
    """PBI を部分更新する。``status`` を動かすときだけ状態遷移の正当性を確かめる。"""
    current = _load_or_404(repo, membership.product_id, pbi_id)
    changes = body.model_dump(exclude_unset=True, mode="json")
    if "status" in changes:
        _check_status_transition(current["status"], changes["status"])
    updated = repo.replace(
        product_id=membership.product_id,
        doc_id=pbi_id,
        changes=changes,
        actor=membership.oid,
        if_match=if_match,
    )
    set_etag(response, updated)
    return updated


@router.delete(
    "/{pbi_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=problem_responses(401, 403, 404, 412, 428, 503),
)
def delete(
    pbi_id: str,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
    if_match: str = Depends(require_if_match),
) -> Response:
    """PBI を論理削除する（物理削除しない。D-07）。以後 GET は 404。"""
    _load_or_404(repo, membership.product_id, pbi_id)
    repo.soft_delete(
        product_id=membership.product_id,
        doc_id=pbi_id,
        actor=membership.oid,
        if_match=if_match,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- ヘルパ ------------------------------------------------------------------


def _load_or_404(repo: Repository, product_id: str, pbi_id: str) -> dict:
    """PBI を引き、無ければ 404 を投げる（論理削除済みも 404）。"""
    doc = get_pbi(repo, product_id=product_id, pbi_id=pbi_id)
    if doc is None:
        raise ProblemException(status.HTTP_404_NOT_FOUND, detail="PBI が見つかりません")
    return doc


def _check_status_transition(current: str, target: str) -> None:
    """状態遷移が不正なら 422（``violations`` に規則 ID を載せる。D-20）。"""
    if is_valid_transition(PbiStatus(current), PbiStatus(target)):
        return
    raise ProblemException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="不正な状態遷移です",
        type_slug="invalid-status-transition",
        detail=f"'{current}' から '{target}' への状態遷移は許可されていません",
        violations=[
            Violation(
                rule="pbi-status-transition",
                field="status",
                message=("PBI の状態は new → ready → inProgress → done の順にのみ進められます"),
            )
        ],
    )
