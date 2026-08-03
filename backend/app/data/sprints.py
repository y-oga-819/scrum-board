"""スプリントのドメイン規則とデータアクセス（B-21）。

``sprint`` は「いつ・何を目指して回すか」を表すタイムボックス。パーティションは所属先の
``productId``、id は ``spr_<ULID>``（時系列にソート可能。:mod:`app.data.ids`）。

スプリントを参照するのは**タスクだけ**（``task.sprintId``。提案書 04章・図5）。PBI は
スプリントへの参照を持たない（完了地 ``completedSprintId`` を除く）。したがってこの
モジュールが持つのはスプリント自身の**ドメイン知識**だけに絞る:

* :class:`SprintStatus` — 状態の語彙（``planned`` / ``active`` / ``closed``）。
* :func:`is_valid_transition` — **正当な状態遷移**の判定（純関数）。PBI の状態遷移
  （:mod:`app.data.pbis`）と同じく ``planned → active → closed`` の一方向の隣接だけを
  許す。「``planned`` / ``active`` / ``closed`` が遷移する」という要件（B-21）の**規則
  そのもの**をここに一元化し、HTTP への翻訳（422 + violations）は API 層
  （:mod:`app.api.sprints`）が担う。データ層は HTTP を知らない。
* :func:`is_valid_period` — 期間（``startDate`` ≤ ``endDate``）の判定（純関数）。
* :func:`create_sprint` / :func:`get_sprint` / :func:`list_sprints` — Repository ポート
  越しの薄い生成・参照。共通フィールド付与・論理削除除外・楽観排他はポートが構造的に
  保証する（B-07）。
* ``number`` はパーティション内で**連番採番**する（:func:`next_number`）。作成順に
  1, 2, 3… と振り、スプリントを人が識別する見出しにする（提案書 04章 ``"number":2``）。

.. note::
   **同時に ``active`` なスプリントを1つに絞る**制約（操作をまたぐ不変条件）はここでは
   課さない。単一ドキュメントの状態遷移では表せず（他のスプリントの状態を見る必要が
   ある）、それが要るのはプランニング／ボード（B-22 / B-23）が「今どのスプリントか」を
   決める時点である。B-21 は CRUD と単体の状態遷移までを所有する（I-5 の担保を B-25 の
   終了処理に閉じたのと同じ切り分け）。
"""

from __future__ import annotations

from enum import StrEnum

from .documents import Document, DocumentType
from .repository import Repository


class SprintStatus(StrEnum):
    """スプリントの状態（提案書 04章 ``status:"planned | active | closed"``）。

    PBI の ``new`` / ``ready`` / … やタスクの ``todo`` / ``doing`` / ``done`` とは別の
    語彙。前進のみで、``closed`` は終端（終了処理 B-25 を経た後は戻さない）。
    """

    PLANNED = "planned"
    ACTIVE = "active"
    CLOSED = "closed"


# 正当な一方向遷移（``current → 次``）。計画 → 実行 → 終了 の隣接だけを許す。飛ばし
# （planned→closed）と逆流（closed→active 等）は許さない。PBI の ``_FORWARD`` と同型。
_FORWARD: dict[SprintStatus, SprintStatus] = {
    SprintStatus.PLANNED: SprintStatus.ACTIVE,
    SprintStatus.ACTIVE: SprintStatus.CLOSED,
}


def is_valid_transition(current: SprintStatus, target: SprintStatus) -> bool:
    """``current`` から ``target`` への状態変更が正当なら ``True``。

    許すのは (1) **同状態**（PATCH が status を据え置いてゴールや期間だけ直したとき
    の冪等な更新）と、(2) 一つ次への**前進**だけ。それ以外（飛ばし・逆流）は不正。
    弾いた事実の HTTP 表現（422・``violations``）は API 層が付ける（D-20）。
    """
    return target == current or _FORWARD.get(current) == target


def is_valid_period(start_date: str | None, end_date: str | None) -> bool:
    """期間が破れていなければ ``True``（``startDate`` ≤ ``endDate``）。

    片方でも未設定（``None``）なら期間として比較できないので判定しない（``True``）。
    日付は ISO 8601 の ``YYYY-MM-DD`` 文字列で、**辞書順比較が暦順と一致する**ため
    文字列の大小比較で足りる（rank と同じ発想 — B-16）。終了日が開始日より前という
    のは判断の余地がない入力エラーなので、ここで弾いて 422 に翻訳する（API 層）。
    """
    if start_date is None or end_date is None:
        return True
    return start_date <= end_date


def next_number(repo: Repository, product_id: str) -> int:
    """パーティション内の**次のスプリント番号**を返す（既存の最大 + 1、無ければ 1）。

    連番採番に使う。論理削除済みはポートが除外するため、削除された番号は空く（欠番は
    許容する。番号は識別の見出しであって密な連番を保証しない）。単一パーティション・
    小件数のためパーティションを 1 回舐めるだけで足りる（クロスパーティションではない）。
    """
    numbers = [
        doc["number"]
        for doc in repo.query(product_id=product_id, doc_type=DocumentType.SPRINT)
        if isinstance(doc.get("number"), int)
    ]
    return max(numbers) + 1 if numbers else 1


def new_sprint_data(
    *,
    goal: str = "",
    start_date: str | None = None,
    end_date: str | None = None,
) -> Document:
    """新規スプリントの**ドメインフィールド**を組み立てる（共通フィールドは repo が付与）。

    作成時の状態は必ず ``planned``（まだ回っていない）。``number`` はここでは ``None`` を
    置く**プレースホルダ**にすぎない。実際の採番にはパーティション内の既存番号が要るため、
    repo を持つ :func:`create_sprint` が作成直前に上書きで打つ。期間・ゴールは任意
    （計画中はまだ決まっていないことがある。「設定できる」＝必須ではない）。
    """
    return {
        "number": None,
        "goal": goal,
        "startDate": start_date,
        "endDate": end_date,
        "status": SprintStatus.PLANNED.value,
    }


def create_sprint(
    repo: Repository,
    *,
    product_id: str,
    actor: str,
    goal: str = "",
    start_date: str | None = None,
    end_date: str | None = None,
) -> Document:
    """スプリントを1件作成し、``_etag`` 付きの保存結果を返す（id は ``spr_<ULID>``）。

    ``number`` は**パーティションの次番号**を採番する（作成順に 1, 2, 3…）。状態は必ず
    ``planned`` から始まる。以後の期間・ゴール・状態の変更は汎用 ``PATCH``（B-21 の
    :mod:`app.api.sprints`）が担う。
    """
    data = new_sprint_data(goal=goal, start_date=start_date, end_date=end_date)
    data["number"] = next_number(repo, product_id)
    return repo.create(
        product_id=product_id,
        doc_type=DocumentType.SPRINT,
        data=data,
        actor=actor,
    )


def list_sprints(repo: Repository, product_id: str) -> list[Document]:
    """パーティションのスプリントを**番号順**で返す（論理削除済みは除外）。

    ``rank`` を持たない型なので既定の ``ORDER BY rank, id`` ではなく ``number`` で並べる
    （B-07 のポートに ``order_by`` を渡す）。プランニング（B-22）やボード（B-23）が
    「今どのスプリントか」を選ぶための一覧。単一パーティション・小件数。
    """
    return repo.query(product_id=product_id, doc_type=DocumentType.SPRINT, order_by=("number",))


def get_sprint(repo: Repository, *, product_id: str, sprint_id: str) -> Document | None:
    """``product_id`` パーティションからスプリントをポイントリードする。

    未作成・論理削除済みは ``None``（ポート契約どおり存在を漏らさない）。id が sprint 以外の
    型を指していた場合も ``None`` を返す（``spr_<id>`` 以外を誤って掴まない防波堤）。
    """
    doc = repo.get(product_id, sprint_id)
    if doc is None or doc.get("type") != DocumentType.SPRINT.value:
        return None
    return doc
