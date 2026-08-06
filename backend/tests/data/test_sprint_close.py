"""スプリント終了処理のドメイン操作の単体テスト（B-25・I-5）。

持ち越し対象の抽出（未完了だけ・完了は含めない — I-5）と、締め処理（未完了を次スプリントへ
移し、完了は動かさず、スプリントを ``closed`` にする）を、Cosmos なしのフェイク Repository で
検証する（層1・2。D-19）。プランニングの「外す」（B-22）と対になる切り分け（未完了だけを
動かす）をここでも確かめる。
"""

from __future__ import annotations

import pytest

from app.data.fake import InMemoryRepository
from app.data.sprint_close import carry_over_targets, close_sprint
from app.data.sprints import SprintStatus, create_sprint, get_sprint
from app.data.tasks import TaskStatus, TaskType, create_task, get_task

PRODUCT = "prd_sandbox"
ACTOR = "oid-actor"
PBI_ID = "pbi_01HZZZ"


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository()


def _sprint(repo: InMemoryRepository) -> dict:
    """アクティブなスプリントを1件作る（締めの対象は実行中のスプリント）。"""
    doc = create_sprint(repo, product_id=PRODUCT, actor=ACTOR, goal="回す")
    return repo.replace(
        product_id=PRODUCT,
        doc_id=doc["id"],
        changes={"status": SprintStatus.ACTIVE.value},
        actor=ACTOR,
        if_match=doc["_etag"],
    )


def _task_in_sprint(repo: InMemoryRepository, sprint_id: str, *, title: str) -> dict:
    """スプリントに属する pbi タスクを1件作る（作成直後に ``sprintId`` を打つ）。"""
    task = create_task(
        repo, product_id=PRODUCT, actor=ACTOR, task_type=TaskType.PBI, title=title, pbi_id=PBI_ID
    )
    return repo.replace(
        product_id=PRODUCT,
        doc_id=task["id"],
        changes={"sprintId": sprint_id},
        actor=ACTOR,
        if_match=task["_etag"],
    )


def _fetch(repo: InMemoryRepository, task_id: str) -> dict:
    doc = get_task(repo, product_id=PRODUCT, task_id=task_id)
    assert doc is not None
    return doc


def _mark_done(repo: InMemoryRepository, task: dict) -> dict:
    return repo.replace(
        product_id=PRODUCT,
        doc_id=task["id"],
        changes={"status": TaskStatus.DONE.value, "completedAt": "2026-08-06T00:00:00Z"},
        actor=ACTOR,
        if_match=task["_etag"],
    )


# --- 持ち越し対象のプレビュー（carry_over_targets） ---------------------------


def test_carry_over_targets_lists_only_incomplete(repo: InMemoryRepository) -> None:
    sprint = _sprint(repo)
    todo = _task_in_sprint(repo, sprint["id"], title="未着手")
    done = _mark_done(repo, _task_in_sprint(repo, sprint["id"], title="済"))
    targets = carry_over_targets(repo, product_id=PRODUCT, sprint_id=sprint["id"])
    ids = {t["id"] for t in targets}
    assert todo["id"] in ids
    assert done["id"] not in ids  # I-5: 完了タスクは持ち越し対象に含めない。


def test_carry_over_targets_is_read_only(repo: InMemoryRepository) -> None:
    # プレビューは状態を変えない（事実を見せるだけ — P-1）。
    sprint = _sprint(repo)
    todo = _task_in_sprint(repo, sprint["id"], title="未着手")
    carry_over_targets(repo, product_id=PRODUCT, sprint_id=sprint["id"])
    assert _fetch(repo, todo["id"])["sprintId"] == sprint["id"]
    unchanged = get_sprint(repo, product_id=PRODUCT, sprint_id=sprint["id"])
    assert unchanged is not None
    assert unchanged["status"] == "active"


# --- 締め処理（close_sprint） ------------------------------------------------


def test_close_moves_incomplete_to_next_sprint(repo: InMemoryRepository) -> None:
    sprint = _sprint(repo)
    nxt = _sprint(repo)
    todo = _task_in_sprint(repo, sprint["id"], title="未着手")
    carried = close_sprint(
        repo, product_id=PRODUCT, sprint=sprint, next_sprint_id=nxt["id"], actor=ACTOR
    )
    assert [t["id"] for t in carried] == [todo["id"]]
    assert _fetch(repo, todo["id"])["sprintId"] == nxt["id"]


def test_close_does_not_move_done_tasks(repo: InMemoryRepository) -> None:
    # I-5: 完了タスクは持ち越さない・sprintId を変えない（完了地を凍結する）。
    sprint = _sprint(repo)
    nxt = _sprint(repo)
    done = _mark_done(repo, _task_in_sprint(repo, sprint["id"], title="済"))
    close_sprint(repo, product_id=PRODUCT, sprint=sprint, next_sprint_id=nxt["id"], actor=ACTOR)
    assert _fetch(repo, done["id"])["sprintId"] == sprint["id"]


def test_close_marks_sprint_closed(repo: InMemoryRepository) -> None:
    sprint = _sprint(repo)
    nxt = _sprint(repo)
    close_sprint(repo, product_id=PRODUCT, sprint=sprint, next_sprint_id=nxt["id"], actor=ACTOR)
    closed = get_sprint(repo, product_id=PRODUCT, sprint_id=sprint["id"])
    assert closed is not None
    assert closed["status"] == SprintStatus.CLOSED.value


def test_close_does_not_touch_other_sprints_tasks(repo: InMemoryRepository) -> None:
    # 別スプリントにいるタスクには触れない（sprintId が一致する未完了だけを動かす）。
    sprint = _sprint(repo)
    nxt = _sprint(repo)
    other = _task_in_sprint(repo, nxt["id"], title="次のスプリントの作業")
    close_sprint(repo, product_id=PRODUCT, sprint=sprint, next_sprint_id=nxt["id"], actor=ACTOR)
    assert _fetch(repo, other["id"])["sprintId"] == nxt["id"]
