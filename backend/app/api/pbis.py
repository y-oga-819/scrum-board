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
from ..data.errors import InvalidRankBoundsError
from ..data.pbis import PbiStatus, create_pbi, get_pbi, is_valid_transition, split_pbi
from ..data.ranking import rank_between
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


class RankMove(BaseModel):
    """並び替えの移動先を**前後の要素 ID** で指定する（D-20）。

    ランクそのものはクライアントに作らせない。移動先の直前・直後の要素 ID だけを受け取り、
    サーバーが両者の ``rank`` の**間**に入る新しいランクを生成する（アルゴリズムを1箇所に
    閉じ、フロントを差し替えても挙動が変わらない — 提案書 06章）。

    * ``beforeId`` — 移動先の**直前**（1つ上・rank が小さい方）の PBI id。先頭へ動かす
      場合は ``null``。
    * ``afterId`` — 移動先の**直後**（1つ下・rank が大きい方）の PBI id。末尾へ動かす
      場合は ``null``。

    両方 ``null`` は「並びに他の要素が無い（唯一の要素）」を表す。
    """

    beforeId: str | None = None
    afterId: str | None = None


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


@router.post(
    "/{pbi_id}/split",
    status_code=status.HTTP_201_CREATED,
    response_model=Pbi,
    responses=problem_responses(401, 403, 404, 422, 503),
)
def split(
    pbi_id: str,
    body: PbiCreate,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> object:
    """分割元 ``pbi_id`` を親に持つ子 PBI を作成する（B-19）。

    大きな PBI を割って別の PBI を切り出す。生成物は通常の PBI（状態は ``new`` から）で、
    ``parentPbiId`` に分割元の id を刻む——一覧から分割元を辿るための唯一の参照
    （提案書 04章）。分割元は**変更しない**ため、これは新規作成であり ``If-Match`` を要さない
    （更新経路 ``PATCH`` とは非対称。汎用 PATCH は ``parentPbiId`` を触らない — D-20）。
    分割元が無ければ **404**（存在しないものからは分割できない）。入力（子のフィールド）は
    :class:`PbiCreate` と同形——分割は「親を指す作成」であり、新しい入力語彙を増やさない。
    """
    _load_or_404(repo, membership.product_id, pbi_id)
    doc = split_pbi(
        repo,
        product_id=membership.product_id,
        actor=membership.oid,
        parent_pbi_id=pbi_id,
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


@router.post(
    "/{pbi_id}/rank",
    response_model=Pbi,
    responses=problem_responses(401, 403, 404, 412, 422, 428, 503),
)
def reorder(
    pbi_id: str,
    body: RankMove,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
    if_match: str = Depends(require_if_match),
) -> object:
    """PBI を前後の要素の**間**へ並び替える。更新は移動した1件だけ（提案書 06章）。

    移動先の直前・直後の PBI id（:class:`RankMove`）から、両者の ``rank`` の間に入る
    新しいランクをサーバーで生成し、移動した PBI の ``rank`` だけを書き換える。整数 order の
    ように後続を巻き込まない（更新は常に1ドキュメント）。``If-Match`` は移動対象の
    ``_etag``（欠落 428・不一致 412）。
    """
    _load_or_404(repo, membership.product_id, pbi_id)
    before_rank = _neighbor_rank(repo, membership.product_id, pbi_id, body.beforeId, "beforeId")
    after_rank = _neighbor_rank(repo, membership.product_id, pbi_id, body.afterId, "afterId")
    new_rank = _rank_between_or_422(before_rank, after_rank)
    updated = repo.replace(
        product_id=membership.product_id,
        doc_id=pbi_id,
        changes={"rank": new_rank},
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


def _neighbor_rank(
    repo: Repository,
    product_id: str,
    moved_id: str,
    neighbor_id: str | None,
    field: str,
) -> str | None:
    """並び替えの隣接要素の ``rank`` を引く（端は ``None``）。

    ``neighbor_id`` が ``None`` なら端（先頭／末尾）を表す ``None`` を返す。指定された
    id が**存在しない・移動対象自身・rank 未設定**のいずれかなら、リクエスト本文の
    問題として **422**（どのフィールドが不正かを ``violations`` に載せる）。
    """
    if neighbor_id is None:
        return None
    if neighbor_id == moved_id:
        raise _rank_violation(field, "移動対象自身を前後の要素に指定できません")
    neighbor = get_pbi(repo, product_id=product_id, pbi_id=neighbor_id)
    if neighbor is None:
        raise _rank_violation(field, "指定された前後の要素が存在しません")
    rank = neighbor.get("rank")
    if not isinstance(rank, str):
        raise _rank_violation(field, "指定された前後の要素に rank がありません")
    return rank


def _rank_between_or_422(before: str | None, after: str | None) -> str:
    """前後の rank の間の新しいランクを生成する。前後関係が破れていれば 422。"""
    try:
        return rank_between(before, after)
    except InvalidRankBoundsError:
        raise _rank_violation(
            "beforeId", "beforeId は afterId より前（rank が小さい方）でなければなりません"
        ) from None


def _rank_violation(field: str, message: str) -> ProblemException:
    """並び替え入力の不正を 422 problem にする（``rule='pbi-rank'``）。"""
    return ProblemException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="並び替えの指定が不正です",
        type_slug="invalid-rank",
        detail=message,
        violations=[Violation(rule="pbi-rank", field=field, message=message)],
    )


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
