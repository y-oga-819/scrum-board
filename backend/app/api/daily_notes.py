"""デイリーノートのエンドポイント（B-27・D-27）。

デイリースクラムの**その日の**アジェンダと議事録を読み書きする。すべて
``/api/products/{product_id}/sprints/{sprint_id}/daily`` の下にあり（``planning`` / ``board`` /
``close`` と同じくスプリントにネストする）、:func:`~app.authz.require_member` に依存するだけで
**非メンバーは 403**（B-09）。認可・401・DB 未構成 503 はこの依存が担う。

読み書きの非対称（D-20・D-27）:

* **``GET .../daily/{date}`` は get-or-create** — その日のノートが無ければ空のノートを1件作って
  返す（:func:`~app.data.daily_notes.ensure_daily_note`。冪等）。パネルが常に**編集対象と版
  （``ETag``）**を持てるようにする。初回サインインの ``GET /api/me`` が user と member を作るのと
  同じ既定パターン（D-21・D-27）。スプリントが無ければ 404（幻のスプリントにノートを作らない）。
* **``PATCH .../daily/{date}`` は単一リソースの部分更新** — ``agenda`` / ``minutes`` を
  :func:`~app.http.require_if_match` の下で更新する（欠落 428・不一致 412）。単一ドキュメント
  応答は ``ETag`` ヘッダで版を返す（:func:`~app.http.set_etag`）。書き込みに専用経路を新設せず、
  PBI 詳細（B-18）と同型の汎用 ``PATCH``＋``If-Match`` に乗せる。

``{date}`` は ``YYYY-MM-DD``（ISO 8601）のみ受ける（不正な形は 422）。スプリント期間内かは
問わない——朝会は期間外の日に開くこともあり、事実を縛らない（P-1・D-27）。DB を触るため各
ハンドラは ``def``（同期）で書き、FastAPI がスレッドプールに逃がす。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict

from ..authz import Membership, get_repository, require_member
from ..data import Repository
from ..data.daily_notes import ensure_daily_note, get_daily_note
from ..data.sprints import get_sprint
from ..http import (
    ProblemException,
    Violation,
    problem_responses,
    require_if_match,
    set_etag,
)

router = APIRouter(
    prefix="/api/products/{product_id}/sprints/{sprint_id}/daily",
    tags=["daily-notes"],
)


# --- 入出力モデル（OpenAPI に載り、フロントの型生成が拾う。D-20） ----------------


class AgendaItem(BaseModel):
    """朝会アジェンダの1項目（提案書 04章 ``{"id","text","done"}``）。

    ``id`` はクライアントが採番する不透明な識別子（B-18 の完了条件チェックリストと同じ）。
    """

    id: str
    text: str
    done: bool = False


class DailyNote(BaseModel):
    """デイリーノートの応答表現（提案書 04章のフィールド）。

    単一ドキュメント応答なので ``_etag`` は本文に載せず ``ETag`` ヘッダで返す（``extra='ignore'``
    で捨てる。集約 GET の各要素が ``_etag`` を本文に持つのとは非対称 — D-20）。
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
    sprintId: str
    date: str
    agenda: list[AgendaItem]
    minutes: str


class DailyNoteUpdate(BaseModel):
    """ノート更新の入力（部分更新）。**送られたフィールドだけ**を反映する。

    ``sprintId`` / ``date`` は載せない（id を決める鍵であり、後から動かさない — D-27）。
    """

    agenda: list[AgendaItem] | None = None
    minutes: str | None = None


# --- エンドポイント ----------------------------------------------------------


@router.get(
    "/{date}",
    response_model=DailyNote,
    responses=problem_responses(401, 403, 404, 422, 503),
)
def get_or_create(
    sprint_id: str,
    date: str,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
) -> object:
    """その日のノートを返す（無ければ空のノートを作って返す＝get-or-create。D-27）。

    ``date`` の形が不正なら 422、スプリントが存在しない／論理削除済みなら 404（存在を漏らさない）。
    """
    _validate_date(date)
    sprint = get_sprint(repo, product_id=membership.product_id, sprint_id=sprint_id)
    if sprint is None:
        raise ProblemException(status.HTTP_404_NOT_FOUND, detail="スプリントが見つかりません")
    doc = ensure_daily_note(
        repo,
        product_id=membership.product_id,
        sprint_id=sprint_id,
        date=date,
        actor=membership.oid,
    )
    set_etag(response, doc)
    return doc


@router.patch(
    "/{date}",
    response_model=DailyNote,
    responses=problem_responses(401, 403, 404, 412, 422, 428, 503),
)
def update(
    sprint_id: str,
    date: str,
    body: DailyNoteUpdate,
    response: Response,
    membership: Membership = Depends(require_member),
    repo: Repository = Depends(get_repository),
    if_match: str = Depends(require_if_match),
) -> object:
    """アジェンダ・議事録を部分更新する（``If-Match`` 必須。欠落 428・不一致 412）。

    ノートは先に ``GET`` で存在させる前提（get-or-create）。無ければ 404。``date`` の形が
    不正なら 422。版がずれれば 412——フロントは黙って上書きせず最新を読み直す（D-24）。
    """
    _validate_date(date)
    current = _load_or_404(repo, membership.product_id, sprint_id, date)
    changes = body.model_dump(exclude_unset=True, mode="json")
    updated = repo.replace(
        product_id=membership.product_id,
        doc_id=current["id"],
        changes=changes,
        actor=membership.oid,
        if_match=if_match,
    )
    set_etag(response, updated)
    return updated


# --- ヘルパ ------------------------------------------------------------------


def _load_or_404(repo: Repository, product_id: str, sprint_id: str, date: str) -> dict:
    """ノートを引き、無ければ 404 を投げる（論理削除済みも 404）。"""
    doc = get_daily_note(repo, product_id=product_id, sprint_id=sprint_id, date=date)
    if doc is None:
        raise ProblemException(status.HTTP_404_NOT_FOUND, detail="デイリーノートが見つかりません")
    return doc


def _validate_date(value: str) -> None:
    """``value`` が ``YYYY-MM-DD``（実在する暦日）でなければ 422（``rule='daily-note-date'``）。

    ``date.fromisoformat`` は ``YYYY-MM-DD`` のゼロ埋め形だけを受け、``2026-13-40`` のような
    実在しない日付も弾く。id を決める鍵（``dly_<sprintId>_<date>``）なので形を揃える（D-27）。
    """
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        message = "日付は YYYY-MM-DD 形式でなければなりません"
        raise ProblemException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="日付の形式が不正です",
            type_slug="invalid-daily-note-date",
            detail=message,
            violations=[Violation(rule="daily-note-date", field="date", message=message)],
        ) from exc
