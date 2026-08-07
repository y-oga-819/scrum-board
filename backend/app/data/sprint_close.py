"""スプリント終了処理のドメイン操作（B-25・I-5・D-20）。

スプリントを締める操作は、提案書 07章のとおり **2 つの更新**に尽きる:

1. **未完了タスクを次スプリントへ**（``sprintId = 次スプリント``）。完了タスクは動かさない。
2. **スプリントを締める**（``status = closed``）。

要点は **I-5**——「完了タスクは持ち越し・除外の対象にしない。``sprintId`` を変更しない」。
これは単一文書では表せない**操作級の不変条件**（完了タスクの ``sprintId`` を凍結したまま、
未完了だけを動かす）で、その担保をこの終了操作に閉じる（:mod:`app.data.tasks` の
``check_invariants`` は単一文書の I-1〜I-4 だけを見る）。プランニングの「外す」（B-22）が
未完了だけを ``null`` に戻したのと**同じ切り分け**で、ここは未完了だけを次スプリントへ移す。

* :func:`carry_over_targets` — 持ち越し対象＝このスプリントの**未完了**タスク（読み取り
  のみ）。「スプリントを終了」を押した時点で**プレビュー表示**する土台（提案書 07章・
  強制も警告もせず事実だけ見せる — P-1）。完了タスクは含めない（I-5）。
* :func:`close_sprint` — 上の 1・2 を実行する。持ち越したタスク文書の列を返し、API 層が
  件数を扱えるようにする。

複数ドキュメントを1規則で束ねて動かす**サーバー所有のドメイン操作**であり（分割 B-19・
プランニング B-22 と同じ）、クライアントが版を持つ単一リソースの更新ではない——``If-Match``
は取らず、個々のドキュメントの楽観排他はデータ層が読み直した ``_etag`` で内部的に満たす。
スプリント・移動先の実在確認と状態遷移の正当性（HTTP への翻訳）は API 層
（:mod:`app.api.sprint_close`）が担い、ここはドメインの語彙だけを扱う（データ層は HTTP を
知らない）。

.. note::
   タスクの移動とスプリントの締めを**順に** ``replace`` する（原子的なバッチではない）。
   実 Cosmos のトランザクショナルバッチ（提案書 09章・同一パーティション）による原子化は
   層3（B-11）／実サービス（B-31）に回す。プランニングの取り込み／外すが同じく順次
   ``replace`` で書いているのと揃える。
"""

from __future__ import annotations

from .documents import Document
from .repository import Repository
from .sprints import SprintStatus
from .tasks import TaskStatus, list_sprint_tasks


def carry_over_targets(repo: Repository, *, product_id: str, sprint_id: str) -> list[Document]:
    """スプリント ``sprint_id`` の**持ち越し対象**（未完了タスク）を ``rank, id`` 順で返す。

    未完了（``status != 'done'``）のタスクだけを返す。**完了タスクは含めない**（I-5。完了地を
    凍結する）。読み取りのみで、状態は変えない——「スプリントを終了」を押した時点で持ち越される
    一覧を**プレビュー表示**するために使う（提案書 07章。事実を見せるだけ — P-1）。pbi・team を
    問わず、このスプリントに属する未完了タスクが対象（ボードの集約と同じ ``list_sprint_tasks``
    に乗り、N+1 を作らない）。
    """
    return [
        task
        for task in list_sprint_tasks(repo, product_id, sprint_id)
        if task.get("status") != TaskStatus.DONE.value
    ]


def close_sprint(
    repo: Repository,
    *,
    product_id: str,
    sprint: Document,
    next_sprint_id: str,
    actor: str,
) -> list[Document]:
    """スプリントを締める。持ち越したタスク文書の列を返す（提案書 07章）。

    1. このスプリントの**未完了**タスクの ``sprintId`` を ``next_sprint_id`` に付け替える
       （完了タスクは動かさない — I-5）。
    2. スプリント自身を ``status = closed`` にする。

    ``sprint`` は API 層が実在確認・状態遷移の検査のために読み込んだ最新の文書を渡す
    （その ``_etag`` をスプリント更新の ``if_match`` に使う）。移動先 ``next_sprint_id`` の
    実在・自己指定でないこと・締め済みでないことの検査も API 層が済ませる（HTTP への翻訳を
    データ層に持ち込まない）。
    """
    carried: list[Document] = []
    for task in carry_over_targets(repo, product_id=product_id, sprint_id=sprint["id"]):
        carried.append(
            repo.replace(
                product_id=product_id,
                doc_id=task["id"],
                changes={"sprintId": next_sprint_id},
                actor=actor,
                if_match=task["_etag"],
            )
        )
    repo.replace(
        product_id=product_id,
        doc_id=sprint["id"],
        changes={"status": SprintStatus.CLOSED.value},
        actor=actor,
        if_match=sprint["_etag"],
    )
    return carried
