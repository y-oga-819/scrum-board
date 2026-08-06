"""プランニングのドメイン操作の単体テスト（B-22・D-15・D-20）。

配下タスクの ``sprintId`` の付け外し（取り込み／外す）と、タスク0件の PBI を取り込んだとき
の「タスク分解」自動生成（D-15）、完了タスクを動かさないこと（I-5）を、Cosmos なしのフェイク
Repository で検証する（層1・2。D-19）。
"""

from __future__ import annotations

import pytest

from app.data.fake import InMemoryRepository
from app.data.planning import (
    DECOMPOSITION_TASK_TITLE,
    plan_pbi_into_sprint,
    unplan_pbi_from_sprint,
)
from app.data.tasks import TaskStatus, TaskType, create_task, get_task, list_tasks

PRODUCT = "prd_sandbox"
ACTOR = "oid-actor"
SPRINT = "spr_01SPRINT"
OTHER_SPRINT = "spr_02OTHER"
PBI_ID = "pbi_01HZZZ"


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository()


def _pbi_task(repo: InMemoryRepository, *, title: str = "実装", pbi_id: str = PBI_ID) -> dict:
    return create_task(
        repo, product_id=PRODUCT, actor=ACTOR, task_type=TaskType.PBI, title=title, pbi_id=pbi_id
    )


def _fetch(repo: InMemoryRepository, task_id: str) -> dict:
    """タスクを引いて非 None を保証して返す（テストの索引を型で安全にする）。"""
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


# --- 取り込み（plan_pbi_into_sprint） ----------------------------------------


def test_include_assigns_sprint_id_to_incomplete_tasks(repo: InMemoryRepository) -> None:
    a = _pbi_task(repo, title="A")
    b = _pbi_task(repo, title="B")
    plan_pbi_into_sprint(repo, product_id=PRODUCT, sprint_id=SPRINT, pbi_id=PBI_ID, actor=ACTOR)
    assert _fetch(repo, a["id"])["sprintId"] == SPRINT
    assert _fetch(repo, b["id"])["sprintId"] == SPRINT


def test_include_zero_tasks_generates_one_decomposition_task(repo: InMemoryRepository) -> None:
    # D-15: タスク0件の PBI を取り込むと「タスク分解」タスクが1件生成され、スプリントに入る。
    created = plan_pbi_into_sprint(
        repo, product_id=PRODUCT, sprint_id=SPRINT, pbi_id=PBI_ID, actor=ACTOR
    )
    assert len(created) == 1
    task = created[0]
    assert task["title"] == DECOMPOSITION_TASK_TITLE
    assert task["taskType"] == TaskType.PBI.value
    assert task["pbiId"] == PBI_ID
    assert task["sprintId"] == SPRINT
    assert task["status"] == TaskStatus.TODO.value


def test_include_is_idempotent_and_does_not_duplicate_decomposition(
    repo: InMemoryRepository,
) -> None:
    # 2回取り込んでも「タスク分解」は増えない（生成済みが未完了で残るため）。
    plan_pbi_into_sprint(repo, product_id=PRODUCT, sprint_id=SPRINT, pbi_id=PBI_ID, actor=ACTOR)
    plan_pbi_into_sprint(repo, product_id=PRODUCT, sprint_id=SPRINT, pbi_id=PBI_ID, actor=ACTOR)
    tasks = list_tasks(repo, PRODUCT)
    assert len(tasks) == 1
    assert tasks[0]["sprintId"] == SPRINT


def test_include_skips_done_tasks(repo: InMemoryRepository) -> None:
    # 完了タスクは取り込みで sprintId を付けられない（未完了だけが対象。I-5 と対）。
    done = _mark_done(repo, _pbi_task(repo, title="済"))
    plan_pbi_into_sprint(repo, product_id=PRODUCT, sprint_id=SPRINT, pbi_id=PBI_ID, actor=ACTOR)
    assert _fetch(repo, done["id"])["sprintId"] is None


def test_include_only_touches_the_given_pbi(repo: InMemoryRepository) -> None:
    mine = _pbi_task(repo, title="mine", pbi_id=PBI_ID)
    other = _pbi_task(repo, title="other", pbi_id="pbi_OTHER")
    plan_pbi_into_sprint(repo, product_id=PRODUCT, sprint_id=SPRINT, pbi_id=PBI_ID, actor=ACTOR)
    assert _fetch(repo, mine["id"])["sprintId"] == SPRINT
    assert _fetch(repo, other["id"])["sprintId"] is None


# --- 外す（unplan_pbi_from_sprint） ------------------------------------------


def test_exclude_resets_incomplete_tasks_to_null(repo: InMemoryRepository) -> None:
    _pbi_task(repo, title="A")
    plan_pbi_into_sprint(repo, product_id=PRODUCT, sprint_id=SPRINT, pbi_id=PBI_ID, actor=ACTOR)
    unplan_pbi_from_sprint(repo, product_id=PRODUCT, sprint_id=SPRINT, pbi_id=PBI_ID, actor=ACTOR)
    for task in list_tasks(repo, PRODUCT):
        assert task["sprintId"] is None


def test_exclude_does_not_move_done_tasks(repo: InMemoryRepository) -> None:
    # I-5: 完了タスクは sprintId を保持したまま動かさない。
    incomplete = _pbi_task(repo, title="未完了")
    plan_pbi_into_sprint(repo, product_id=PRODUCT, sprint_id=SPRINT, pbi_id=PBI_ID, actor=ACTOR)
    # 取り込み後の版で done にする（sprintId=SPRINT を持つ完了タスクを作る）。
    in_sprint = _fetch(repo, incomplete["id"])
    done = _mark_done(repo, in_sprint)
    assert done["sprintId"] == SPRINT
    unplan_pbi_from_sprint(repo, product_id=PRODUCT, sprint_id=SPRINT, pbi_id=PBI_ID, actor=ACTOR)
    # 完了タスクの sprintId は据え置き（I-5）。
    assert _fetch(repo, done["id"])["sprintId"] == SPRINT


def test_exclude_only_touches_matching_sprint(repo: InMemoryRepository) -> None:
    # 別スプリントにいるタスクには触れない（sprintId が一致するものだけを戻す）。
    task = _pbi_task(repo, title="A")
    plan_pbi_into_sprint(
        repo, product_id=PRODUCT, sprint_id=OTHER_SPRINT, pbi_id=PBI_ID, actor=ACTOR
    )
    unplan_pbi_from_sprint(repo, product_id=PRODUCT, sprint_id=SPRINT, pbi_id=PBI_ID, actor=ACTOR)
    assert _fetch(repo, task["id"])["sprintId"] == OTHER_SPRINT
