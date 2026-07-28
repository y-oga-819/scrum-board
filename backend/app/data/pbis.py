"""PBI のドメイン規則とデータアクセス（B-15）。

``pbi`` は「何を作るか」を表すプロダクトバックログの1項目。パーティションは所属先の
``productId``、id は ``pbi_<ULID>``（時系列にソート可能。:mod:`app.data.ids`）。

ここが持つのは PBI 固有の**ドメイン知識**だけに絞る:

* :class:`PbiStatus` — 状態の語彙（``new`` / ``ready`` / ``inProgress`` / ``done``）。
* :func:`is_valid_transition` — **正当な状態遷移**の判定（純関数）。提案書 図6 の
  ``new → ready → inProgress → done`` の一方向の隣接だけを許す。「不正な遷移を弾く」
  という要件（B-15）の**規則そのもの**をここに一元化し、HTTP への翻訳（422 + violations）は
  API 層（:mod:`app.api.pbis`）が担う。データ層は HTTP を知らない。
* :func:`create_pbi` / :func:`get_pbi` — Repository ポート越しの薄い生成・参照。
  共通フィールド付与・論理削除除外・楽観排他はポートが構造的に保証する（B-07）。

``completedAt`` / ``completedSprintId`` は作成時に ``null`` を置くが、**その刻印は
スプリント終了処理（B-25）が所有する**。B-15 の更新経路（:mod:`app.api.pbis` の PATCH）は
これらを触らない（クライアントから編集させない）。``rank`` の採番は並び替え（B-16）、
``parentPbiId`` は分割（B-19）がそれぞれ所有する。
"""

from __future__ import annotations

from enum import StrEnum

from .documents import Document, DocumentType
from .ranking import rank_after
from .repository import Repository


class PbiStatus(StrEnum):
    """PBI の状態（提案書 04章・図6）。

    タスクの ``todo`` / ``doing`` / ``done`` とは別の語彙を持つ。前進のみで、``done`` は
    終端（タスクと違い完了取り消しの戻り遷移を持たない — 完了地は不変。提案書 図6）。
    """

    NEW = "new"
    READY = "ready"
    IN_PROGRESS = "inProgress"
    DONE = "done"


# 正当な一方向遷移（``current → 次``）。提案書 図6 の隣接だけを許す。飛ばし
# （new→done 等）と逆流（done→inProgress 等）は許さない。
_FORWARD: dict[PbiStatus, PbiStatus] = {
    PbiStatus.NEW: PbiStatus.READY,
    PbiStatus.READY: PbiStatus.IN_PROGRESS,
    PbiStatus.IN_PROGRESS: PbiStatus.DONE,
}


def is_valid_transition(current: PbiStatus, target: PbiStatus) -> bool:
    """``current`` から ``target`` への状態変更が正当なら ``True``。

    許すのは (1) **同状態**（PATCH が status を据え置いたときの冪等な更新）と、
    (2) 図6 の**一つ次への前進**だけ。それ以外（飛ばし・逆流）はすべて不正。
    弾いた事実の HTTP 表現（422・``violations``）は API 層が付ける（D-20）。
    """
    return target == current or _FORWARD.get(current) == target


def new_pbi_data(
    *,
    title: str,
    description: str = "",
    acceptance_criteria: list[Document] | None = None,
    estimate: int | None = None,
) -> Document:
    """新規 PBI の**ドメインフィールド**を組み立てる（共通フィールドは repo が付与）。

    作成時の状態は必ず ``new``（提案書 図6 の始点）。``completedAt`` /
    ``completedSprintId`` / ``parentPbiId`` は ``null`` から始まり、それぞれ B-25 / B-19 が
    後で刻む。``rank`` はここでは ``null`` を置く**プレースホルダ**にすぎない。実際の採番
    には並びの末尾（現在の最大 rank）が要るため、repo を持つ :func:`create_pbi` が
    作成直前に上書きで打つ（B-16 が rank を所有する）。
    """
    return {
        "title": title,
        "description": description,
        "acceptanceCriteria": acceptance_criteria if acceptance_criteria is not None else [],
        "status": PbiStatus.NEW.value,
        "estimate": estimate,
        "rank": None,
        "completedAt": None,
        "completedSprintId": None,
        "parentPbiId": None,
    }


def last_rank(repo: Repository, product_id: str) -> str | None:
    """パーティション内の PBI の**最大 rank**（末尾）を返す。無ければ ``None``。

    末尾追加の採番に使う。``rank`` が未設定（``None``）の PBI は除いて最大を採る。
    パーティションを 1 回舐めるだけで、バックログは単一パーティション・小件数のため
    許容する（クロスパーティションではない）。
    """
    ranks = [
        doc["rank"]
        for doc in repo.query(product_id=product_id, doc_type=DocumentType.PBI)
        if doc.get("rank") is not None
    ]
    return max(ranks) if ranks else None


def create_pbi(
    repo: Repository,
    *,
    product_id: str,
    actor: str,
    title: str,
    description: str = "",
    acceptance_criteria: list[Document] | None = None,
    estimate: int | None = None,
) -> Document:
    """PBI を1件作成し、``_etag`` 付きの保存結果を返す（id は ``pbi_<ULID>``）。

    ``rank`` は**バックログの末尾**に採番する（新規 PBI は最下位に積まれる）。以後の
    並び替えは専用エンドポイント（:mod:`app.api.pbis` の ``POST .../rank``）が前後の
    要素 ID から生成し直す（B-16）。
    """
    data = new_pbi_data(
        title=title,
        description=description,
        acceptance_criteria=acceptance_criteria,
        estimate=estimate,
    )
    data["rank"] = rank_after(last_rank(repo, product_id))
    return repo.create(
        product_id=product_id,
        doc_type=DocumentType.PBI,
        data=data,
        actor=actor,
    )


def get_pbi(repo: Repository, *, product_id: str, pbi_id: str) -> Document | None:
    """``product_id`` パーティションから PBI をポイントリードする。

    未作成・論理削除済みは ``None``（ポート契約どおり存在を漏らさない）。id が PBI 以外の
    型を指していた場合も ``None`` を返す（``pbi_<id>`` 以外を誤って掴まない防波堤）。
    """
    doc = repo.get(product_id, pbi_id)
    if doc is None or doc.get("type") != DocumentType.PBI.value:
        return None
    return doc
