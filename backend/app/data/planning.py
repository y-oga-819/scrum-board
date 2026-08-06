"""プランニングのドメイン操作（B-22・D-15・D-20）。

プランニングは「どの PBI を今スプリントで回すか」を決める操作。要点は、**PBI 自身は
スプリントへの参照を持たない**こと（提案書 04章・D-08）——「PBI が今スプリントにいる」は
配下タスクの ``sprintId`` から**導出**できるため、二重に持たない。したがってプランニングの
実体は**配下タスクの ``sprintId`` の付け外し**であり、その規則をこのモジュールに一元化する
（D-20。複数ドキュメントを1つの規則で同時に更新する操作を汎用 ``PATCH`` に分解すると、
規則がクライアント側に漏れる）。

* :func:`plan_pbi_into_sprint` — PBI を取り込む。配下の**未完了**タスクに ``sprintId=S`` を
  付ける。**タスクが1件も無ければ「タスク分解」タスクを1件生成**する（D-15。タスクの無い
  PBI をスプリントに置けるようにし、「どこにも表示されない状態」を作らない。その場で分解
  すれば即完了でき、後回しならスプリント中の作業として妥当）。
* :func:`unplan_pbi_from_sprint` — 取り込みを外す。このスプリントにいる**未完了**タスクの
  ``sprintId`` を ``null`` に戻す。**完了タスクは動かさない**（I-5。完了地を保持する。単一
  文書では表せない操作級の不変条件をここで担保する——B-25 の終了処理と同じ切り分け）。

``sprintId`` を動かすのはこの2操作だけ（タスクの汎用 ``PATCH`` は ``sprintId`` を載せない —
B-20/D-20）。スプリント・PBI の実在確認と HTTP への翻訳（403/404）は API 層
（:mod:`app.api.planning`）が担い、ここはドメインの語彙だけを扱う（データ層は HTTP を
知らない）。生成した／付け替えたタスク文書の列を返し、API 層が件数や結果を扱えるようにする。
"""

from __future__ import annotations

from .documents import Document, DocumentType
from .repository import Repository
from .tasks import TaskStatus, TaskType, new_task_data

# タスク0件の PBI を取り込んだときに生成する受け皿タスクの名前（D-15）。「やる作業はあるが、
# まだ分解できていない」という実在の状態を、特別な状態を作らず最小の形で表す。
DECOMPOSITION_TASK_TITLE = "タスク分解"


def _pbi_tasks(repo: Repository, product_id: str, pbi_id: str) -> list[Document]:
    """ある PBI 配下の pbi タスクを引く（論理削除済みはポートが除外する）。

    判別は ``taskType``（``pbiId`` の有無ではない — I-4）。``sprintId`` の付け外しはこの
    集合の未完了分にだけ効く。
    """
    return repo.query(
        product_id=product_id,
        doc_type=DocumentType.TASK,
        equals={"taskType": TaskType.PBI.value, "pbiId": pbi_id},
    )


def _is_incomplete(task: Document) -> bool:
    """未完了（``done`` でない）なら ``True``。完了タスクは ``sprintId`` を動かさない（I-5）。"""
    return task.get("status") != TaskStatus.DONE.value


def plan_pbi_into_sprint(
    repo: Repository,
    *,
    product_id: str,
    sprint_id: str,
    pbi_id: str,
    actor: str,
) -> list[Document]:
    """PBI をスプリント ``sprint_id`` に取り込む。更新／生成したタスク文書の列を返す。

    * 配下に pbi タスクがあれば、その**未完了**タスクに ``sprintId=sprint_id`` を付ける。
      既にこのスプリントにいるタスクは飛ばす（再取り込みで二重書きしない＝冪等）。
    * 配下に pbi タスクが**1件も無ければ**、「タスク分解」タスクを1件だけ生成する（D-15）。
      2回目以降の取り込みでは生成済みの分解タスクが未完了で残るため、追加生成はされない。
    """
    tasks = _pbi_tasks(repo, product_id, pbi_id)
    if not tasks:
        return [
            _create_decomposition_task(
                repo, product_id=product_id, sprint_id=sprint_id, pbi_id=pbi_id, actor=actor
            )
        ]
    changed: list[Document] = []
    for task in tasks:
        if not _is_incomplete(task) or task.get("sprintId") == sprint_id:
            continue
        changed.append(
            repo.replace(
                product_id=product_id,
                doc_id=task["id"],
                changes={"sprintId": sprint_id},
                actor=actor,
                if_match=task["_etag"],
            )
        )
    return changed


def unplan_pbi_from_sprint(
    repo: Repository,
    *,
    product_id: str,
    sprint_id: str,
    pbi_id: str,
    actor: str,
) -> list[Document]:
    """PBI をスプリント ``sprint_id`` から外す。``sprintId`` を戻したタスク文書の列を返す。

    このスプリントにいる**未完了**タスクだけを ``sprintId=null`` に戻す。**完了タスクは
    動かさない**（I-5。他スプリントのタスクにも触れない——``sprintId`` が一致するものだけ）。
    """
    changed: list[Document] = []
    for task in _pbi_tasks(repo, product_id, pbi_id):
        if not _is_incomplete(task) or task.get("sprintId") != sprint_id:
            continue
        changed.append(
            repo.replace(
                product_id=product_id,
                doc_id=task["id"],
                changes={"sprintId": None},
                actor=actor,
                if_match=task["_etag"],
            )
        )
    return changed


def _create_decomposition_task(
    repo: Repository,
    *,
    product_id: str,
    sprint_id: str,
    pbi_id: str,
    actor: str,
) -> Document:
    """「タスク分解」タスクを1件作り、スプリントに入れて返す（D-15）。

    通常の pbi タスクと同じ（``todo`` から始まり、親 PBI を ``pbiId`` で指す）。唯一の違いは
    生成と同時に ``sprintId`` を打つこと——取り込みと同じ操作の中で生まれるので、宙に浮いた
    タスク（``sprintId=null``）を経由しない。
    """
    data = new_task_data(task_type=TaskType.PBI, title=DECOMPOSITION_TASK_TITLE, pbi_id=pbi_id)
    data["sprintId"] = sprint_id
    return repo.create(
        product_id=product_id,
        doc_type=DocumentType.TASK,
        data=data,
        actor=actor,
    )
