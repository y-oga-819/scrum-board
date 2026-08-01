"""タスクのドメイン規則・不変条件・データアクセスの単体テスト（B-20）。

不変条件 I-1〜I-4 を集約する :func:`~app.data.tasks.check_invariants` と、完了地の刻印
（:func:`~app.data.tasks.completion_changes`）、生成・取得・一覧を、Cosmos なしのフェイク
Repository で検証する（層1・2。D-19）。「どの条件で弾いたか」までを固定する。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.data.documents import DocumentType
from app.data.fake import InMemoryRepository
from app.data.tasks import (
    TaskStatus,
    TaskType,
    check_invariants,
    completion_changes,
    create_task,
    get_task,
    list_tasks,
    new_task_data,
)

from .conftest import FixedClock

PRODUCT = "prd_sandbox"
ACTOR = "oid-actor"
PBI_ID = "pbi_01HZZZ"


# --- 不変条件 I-1〜I-4（check_invariants） -----------------------------------


def _team_task(**overrides: object) -> dict:
    """不変条件をすべて満たす最小の team タスク。差分だけ上書きする。"""
    base = new_task_data(task_type=TaskType.TEAM, title="調査")
    base.update(overrides)
    return base


def test_valid_team_task_has_no_violations() -> None:
    assert check_invariants(_team_task()) == []


def test_valid_pbi_task_has_no_violations() -> None:
    doc = new_task_data(task_type=TaskType.PBI, title="実装", pbi_id=PBI_ID)
    assert check_invariants(doc) == []


def test_i1_incomplete_task_with_completed_at() -> None:
    doc = _team_task(status=TaskStatus.DOING.value, completedAt="2026-08-03T09:00:00Z")
    assert "I-1" in check_invariants(doc)


def test_i2_done_task_without_completed_at() -> None:
    doc = _team_task(status=TaskStatus.DONE.value, completedAt=None)
    assert "I-2" in check_invariants(doc)


def test_i3_pbi_task_without_pbi_id() -> None:
    doc = _team_task(taskType=TaskType.PBI.value, pbiId=None)
    assert "I-3" in check_invariants(doc)


def test_i4_team_task_with_pbi_id() -> None:
    # 判別は taskType で行う（pbiId の有無ではない）。team なのに pbiId があれば I-4。
    doc = _team_task(taskType=TaskType.TEAM.value, pbiId=PBI_ID)
    assert "I-4" in check_invariants(doc)


def test_done_task_with_completed_at_is_valid() -> None:
    doc = _team_task(status=TaskStatus.DONE.value, completedAt="2026-08-03T09:00:00Z")
    assert check_invariants(doc) == []


def test_check_invariants_reports_each_broken_rule() -> None:
    # 複数同時違反も列挙する（I-2 と I-3 を同時に破る文書）。
    doc = _team_task(taskType=TaskType.PBI.value, pbiId=None, status=TaskStatus.DONE.value)
    violated = set(check_invariants(doc))
    assert {"I-2", "I-3"} <= violated


# --- 完了地の刻印（completion_changes） --------------------------------------


def test_entering_done_stamps_completed_at() -> None:
    clock = FixedClock(datetime(2026, 8, 3, 9, 0, 0, tzinfo=UTC))
    changes = completion_changes(
        current_status=TaskStatus.DOING.value,
        current_completed_at=None,
        target_status=TaskStatus.DONE.value,
        clock=clock,
    )
    assert changes == {"completedAt": "2026-08-03T09:00:00Z"}


def test_leaving_done_clears_completed_at() -> None:
    changes = completion_changes(
        current_status=TaskStatus.DONE.value,
        current_completed_at="2026-08-03T09:00:00Z",
        target_status=TaskStatus.DOING.value,
    )
    assert changes == {"completedAt": None}


def test_staying_done_does_not_restamp() -> None:
    # 既に done のまま status を送り直しても完了地は動かさない（不変）。
    changes = completion_changes(
        current_status=TaskStatus.DONE.value,
        current_completed_at="2026-08-03T09:00:00Z",
        target_status=TaskStatus.DONE.value,
    )
    assert changes == {}


def test_staying_incomplete_has_no_changes() -> None:
    changes = completion_changes(
        current_status=TaskStatus.TODO.value,
        current_completed_at=None,
        target_status=TaskStatus.DOING.value,
    )
    assert changes == {}


# --- 生成・取得・一覧 --------------------------------------------------------


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository()


def test_create_team_task_without_parent(repo: InMemoryRepository) -> None:
    doc = create_task(
        repo, product_id=PRODUCT, actor=ACTOR, task_type=TaskType.TEAM, title="環境整備"
    )
    assert doc["id"].startswith("tsk_")
    assert doc["type"] == "task"
    assert doc["taskType"] == "team"
    assert doc["pbiId"] is None
    assert doc["status"] == "todo"
    assert doc["completedAt"] is None
    assert doc["sprintId"] is None
    assert doc["isBlocked"] is False
    assert check_invariants(doc) == []


def test_create_pbi_task_with_parent(repo: InMemoryRepository) -> None:
    doc = create_task(
        repo,
        product_id=PRODUCT,
        actor=ACTOR,
        task_type=TaskType.PBI,
        title="実装",
        pbi_id=PBI_ID,
    )
    assert doc["taskType"] == "pbi"
    assert doc["pbiId"] == PBI_ID


def test_get_task_returns_created(repo: InMemoryRepository) -> None:
    created = create_task(
        repo, product_id=PRODUCT, actor=ACTOR, task_type=TaskType.TEAM, title="x"
    )
    fetched = get_task(repo, product_id=PRODUCT, task_id=created["id"])
    assert fetched is not None
    assert fetched["id"] == created["id"]


def test_get_task_missing_is_none(repo: InMemoryRepository) -> None:
    assert get_task(repo, product_id=PRODUCT, task_id="tsk_missing") is None


def test_get_task_rejects_non_task_id(repo: InMemoryRepository) -> None:
    # PBI の id を渡しても task として掴まない（型の防波堤）。
    pbi = repo.create(
        product_id=PRODUCT, doc_type=DocumentType.PBI, data={"title": "p"}, actor=ACTOR
    )
    assert get_task(repo, product_id=PRODUCT, task_id=pbi["id"]) is None


def test_list_tasks_orders_by_id_when_rank_absent(repo: InMemoryRepository) -> None:
    # rank 未設定なので id（作成順の ULID）で整列する。
    a = create_task(repo, product_id=PRODUCT, actor=ACTOR, task_type=TaskType.TEAM, title="A")
    b = create_task(repo, product_id=PRODUCT, actor=ACTOR, task_type=TaskType.TEAM, title="B")
    ids = [t["id"] for t in list_tasks(repo, PRODUCT)]
    assert ids == sorted([a["id"], b["id"]])


def test_list_tasks_excludes_other_partitions(repo: InMemoryRepository) -> None:
    create_task(repo, product_id=PRODUCT, actor=ACTOR, task_type=TaskType.TEAM, title="here")
    create_task(
        repo, product_id="prd_other", actor=ACTOR, task_type=TaskType.TEAM, title="elsewhere"
    )
    titles = [t["title"] for t in list_tasks(repo, PRODUCT)]
    assert titles == ["here"]
