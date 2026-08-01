"""タスクのドメイン規則・不変条件検証・データアクセス（B-20）。

``task`` は「誰が・何を・どうやる」を表すスプリントの作業単位。パーティションは所属先の
``productId``、id は ``tsk_<ULID>``（時系列にソート可能。:mod:`app.data.ids`）。タスクには
2 種あり、判別子は **``taskType``**（提案書 04章・図5）:

* ``taskType='pbi'`` — ある PBI を実現するための作業。``pbiId`` で親 PBI を指す（必須）。
* ``taskType='team'`` — PBI に紐づかないチーム作業（環境整備・調査など）。``pbiId`` は ``null``。

**種別の判定は ``pbiId`` の有無ではなく ``taskType`` で行う（I-4）。** ``pbiId`` が偶然
``null`` かどうかで種別を推測すると、team タスクと「pbiId を付け忘れた pbi タスク」を
区別できず、不変条件が崩れる。だから ``taskType`` を必ず持たせ、そこだけを見て判断する。

ここが持つのは**タスク固有のドメイン知識**に絞る:

* :class:`TaskType` / :class:`TaskStatus` — 種別と状態の語彙。
* :func:`check_invariants` — 提案書 04章の不変条件 **I-1〜I-4** を単一の純関数に集約する
  （B-20 の完了条件。D-19 の必須4領域の1つ）。単一文書で判定できる不変条件だけを見て、
  **違反した不変条件 ID の列**を返す。HTTP への翻訳（422・``violations``）は API 層
  （:mod:`app.api.tasks`）が担い、データ層は HTTP を知らない。
* :func:`completion_changes` — 状態を ``done`` に動かした／から戻したとき、I-1・I-2 を
  保つために ``completedAt`` へ加える差分を計算する（完了地の刻印はここに閉じる）。
* :func:`new_task_data` / :func:`create_task` / :func:`get_task` / :func:`list_tasks` —
  Repository ポート越しの薄い生成・参照。共通フィールド付与・論理削除除外・楽観排他は
  ポートが構造的に保証する（B-07）。

不変条件のうち **I-5**（完了タスクを持ち越し・除外の対象にしない＝``sprintId`` を動かさない）
は単一文書では表せず、スプリント終了操作（B-25）に閉じる。ここでは扱わない（提案書 04章の表・
:mod:`tests.invariants` の ``single_doc=False``）。``sprintId`` の付け外しはプランニング
（B-22）が、``rank`` はボード（B-23）がそれぞれ所有する。B-20 の生成では ``null`` を置く。
"""

from __future__ import annotations

from enum import StrEnum

from .clock import Clock, SystemClock, isoformat_utc
from .documents import Document, DocumentType
from .repository import Repository


class TaskType(StrEnum):
    """タスクの種別（提案書 04章・図5）。**判別子であり、必ず持つ**。"""

    PBI = "pbi"
    TEAM = "team"


class TaskStatus(StrEnum):
    """タスクの状態（提案書 図5）。

    PBI の状態（``new`` … ``done``）とは別の語彙。ボード上を ``todo`` / ``doing`` /
    ``done`` の間で自由に行き来する（PBI と違い一方向ではない — 完了取り消しがある。
    その戻し遷移で ``completedAt`` を ``null`` へ戻すのが I-1・I-2）。
    """

    TODO = "todo"
    DOING = "doing"
    DONE = "done"


# --- 不変条件 I-1〜I-4（単一文書で判定できる領域） -------------------------------
#
# 提案書 04章の不変条件表:
#   I-1  status != 'done' のとき completedAt は必ず null
#   I-2  done にした時点で completedAt を記録（取り消し時は null に戻す）
#   I-3  taskType='pbi' のとき pbiId は必須
#   I-4  taskType='team' のとき pbiId は null（判別はフィールドの有無ではなく taskType）
#
# I-5 は複数文書・操作をまたぐ（スプリント終了で完了タスクの sprintId を動かさない）ため
# ここでは扱わない。B-25 の終了操作に閉じる。


def check_invariants(doc: Document) -> list[str]:
    """タスク文書が破っている不変条件 ID の列を返す（違反が無ければ空）。

    **サーバーが信頼境界**（D-20）であり、不変条件の判定はここでしか行わない。返すのは
    ``["I-3"]`` のような不変条件 ID の列で、API 層がこれを ``violations`` に載せて 422 に
    翻訳する。「弾いた」だけでなく「どの条件で弾いたか」まで機械可読にすることで、D-19 の
    テーブル駆動テストが偽陽性（I-3 を意図した入力が I-4 で弾かれて通る）を防げる。

    判定は**渡された1文書だけ**を見る（I-1〜I-4）。I-5 のような操作をまたぐ不変条件は
    各操作エンドポイント（B-25 等）が担い、ここには持ち込まない。
    """
    violated: list[str] = []
    status = doc.get("status")
    completed_at = doc.get("completedAt")
    task_type = doc.get("taskType")
    pbi_id = doc.get("pbiId")

    # I-1: 未完了なら completedAt は null でなければならない。
    if status != TaskStatus.DONE.value and completed_at is not None:
        violated.append("I-1")
    # I-2: done なら completedAt が記録されていなければならない。
    if status == TaskStatus.DONE.value and completed_at is None:
        violated.append("I-2")
    # I-3: pbi タスクは pbiId 必須。
    if task_type == TaskType.PBI.value and pbi_id is None:
        violated.append("I-3")
    # I-4: team タスクは pbiId を持たない（判別は taskType で行う）。
    if task_type == TaskType.TEAM.value and pbi_id is not None:
        violated.append("I-4")
    return violated


def completion_changes(
    *,
    current_status: str,
    current_completed_at: str | None,
    target_status: str,
    clock: Clock | None = None,
) -> dict[str, str | None]:
    """状態変更に伴い ``completedAt`` へ加える差分を返す（I-1・I-2 を保つ）。

    * ``done`` へ**入った**とき（直前が done でない）→ ``completedAt`` に現在時刻を刻む（I-2）。
    * ``done`` から**出た**とき（対象が done でなく、いま completedAt を持つ）→ ``null`` に
      戻す（I-1。完了取り消し）。
    * それ以外（done のまま・未完了のまま）→ 差分なし（完了地は不変。二重に刻まない）。

    完了地の刻印をこの1関数に閉じ、ボード（B-23）やプランニング（B-22）が各所で now() を
    撒かないようにする。時刻は差し替え可能にしておく（既定は :class:`SystemClock`）。
    """
    clock = clock or SystemClock()
    if target_status == TaskStatus.DONE.value and current_status != TaskStatus.DONE.value:
        return {"completedAt": isoformat_utc(clock.now())}
    if target_status != TaskStatus.DONE.value and current_completed_at is not None:
        return {"completedAt": None}
    return {}


def new_task_data(
    *,
    task_type: TaskType,
    title: str,
    pbi_id: str | None = None,
    todo: str = "",
    memo: str = "",
    assignee_id: str | None = None,
) -> Document:
    """新規タスクの**ドメインフィールド**を組み立てる（共通フィールドは repo が付与）。

    作成時は必ず ``todo`` 状態・``completedAt=null``（提案書 図5 の始点。I-1 を満たす）。
    ``sprintId`` はプランニング（B-22）が、``rank`` はボード（B-23）が後で付ける。ここでは
    ``null`` を置く。``taskType`` と ``pbiId`` の整合（I-3・I-4）は :func:`check_invariants`
    で確かめる（呼び出し側＝API 層が作成前に検証する）。
    """
    return {
        "taskType": task_type.value,
        "pbiId": pbi_id,
        "sprintId": None,
        "status": TaskStatus.TODO.value,
        "completedAt": None,
        "title": title,
        "todo": todo,
        "memo": memo,
        "assigneeId": assignee_id,
        "rank": None,
        "isBlocked": False,
        "blockedReason": "",
    }


def create_task(
    repo: Repository,
    *,
    product_id: str,
    actor: str,
    task_type: TaskType,
    title: str,
    pbi_id: str | None = None,
    todo: str = "",
    memo: str = "",
    assignee_id: str | None = None,
) -> Document:
    """タスクを1件作成し、``_etag`` 付きの保存結果を返す（id は ``tsk_<ULID>``）。

    不変条件（I-3・I-4）と親 PBI の存在確認は API 層が作成前に済ませる。ここはドメイン
    フィールドを組み立ててポートに渡すだけ（共通フィールド付与はポートが行う — B-07）。
    """
    data = new_task_data(
        task_type=task_type,
        title=title,
        pbi_id=pbi_id,
        todo=todo,
        memo=memo,
        assignee_id=assignee_id,
    )
    return repo.create(
        product_id=product_id,
        doc_type=DocumentType.TASK,
        data=data,
        actor=actor,
    )


def get_task(repo: Repository, *, product_id: str, task_id: str) -> Document | None:
    """``product_id`` パーティションからタスクをポイントリードする。

    未作成・論理削除済みは ``None``（ポート契約どおり存在を漏らさない）。id が task 以外の
    型を指していた場合も ``None``（``tsk_<id>`` 以外を誤って掴まない防波堤）。
    """
    doc = repo.get(product_id, task_id)
    if doc is None or doc.get("type") != DocumentType.TASK.value:
        return None
    return doc


def list_tasks(repo: Repository, product_id: str) -> list[Document]:
    """パーティション内の全タスクを ``rank, id`` 順で返す（論理削除済みは除外）。

    バックログ集約（:mod:`app.api.backlog`）が PBI 配下タスクを ``pbiId`` で束ねるための
    土台。パーティションを 1 回舐めるだけで、``PBI 一覧 → 各 PBI のタスク`` の N+1 を作らない
    （B-17 が用意した join point にこれを流し込む）。``rank`` 未設定のタスクは id（=作成順の
    ULID）で整列する。
    """
    return repo.query(product_id=product_id, doc_type=DocumentType.TASK)
