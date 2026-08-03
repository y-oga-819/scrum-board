"""スプリントのドメイン規則とデータアクセスのテスト（B-21）。

状態遷移の正当性（planned → active → closed）・期間判定・連番採番と、生成／参照が
ポート契約（共通フィールド付与・論理削除除外・型による防波堤）に乗っていることを確かめる。
"""

from __future__ import annotations

import pytest

from app.data.fake import InMemoryRepository
from app.data.pbis import create_pbi
from app.data.sprints import (
    SprintStatus,
    create_sprint,
    get_sprint,
    is_valid_period,
    is_valid_transition,
    list_sprints,
    new_sprint_data,
    next_number,
)

PRODUCT = "prd_sandbox"
ACTOR = "oid-author"


# --- 状態遷移（純関数） -------------------------------------------------------

_FORWARD_STEPS = [
    (SprintStatus.PLANNED, SprintStatus.ACTIVE),
    (SprintStatus.ACTIVE, SprintStatus.CLOSED),
]


@pytest.mark.parametrize(("current", "target"), _FORWARD_STEPS)
def test_forward_adjacent_transitions_are_valid(
    current: SprintStatus, target: SprintStatus
) -> None:
    assert is_valid_transition(current, target) is True


@pytest.mark.parametrize("status", list(SprintStatus))
def test_same_status_is_valid(status: SprintStatus) -> None:
    # status を据え置く PATCH（ゴール・期間だけ直す）は冪等に許す。
    assert is_valid_transition(status, status) is True


# 飛ばし（隣接でない前進）と逆流はすべて不正。
_INVALID_TRANSITIONS = [
    (SprintStatus.PLANNED, SprintStatus.CLOSED),
    (SprintStatus.ACTIVE, SprintStatus.PLANNED),
    (SprintStatus.CLOSED, SprintStatus.ACTIVE),
    (SprintStatus.CLOSED, SprintStatus.PLANNED),
]


@pytest.mark.parametrize(("current", "target"), _INVALID_TRANSITIONS)
def test_invalid_transitions_are_rejected(current: SprintStatus, target: SprintStatus) -> None:
    assert is_valid_transition(current, target) is False


# --- 期間判定（純関数） -------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("2026-08-03", "2026-08-14", True),  # 開始 < 終了
        ("2026-08-03", "2026-08-03", True),  # 同日（1日スプリント）は許す
        ("2026-08-14", "2026-08-03", False),  # 逆転は不正
        (None, "2026-08-14", True),  # 片方未設定は判定しない
        ("2026-08-03", None, True),
        (None, None, True),
    ],
)
def test_is_valid_period(start: str | None, end: str | None, expected: bool) -> None:
    assert is_valid_period(start, end) is expected


# --- 連番採番 ----------------------------------------------------------------


def test_next_number_starts_at_one() -> None:
    repo = InMemoryRepository()
    assert next_number(repo, PRODUCT) == 1


def test_next_number_increments_past_max() -> None:
    repo = InMemoryRepository()
    create_sprint(repo, product_id=PRODUCT, actor=ACTOR)
    create_sprint(repo, product_id=PRODUCT, actor=ACTOR)
    assert next_number(repo, PRODUCT) == 3


def test_next_number_is_per_partition() -> None:
    repo = InMemoryRepository()
    create_sprint(repo, product_id=PRODUCT, actor=ACTOR)
    # 別プロダクトの番号は独立して 1 から始まる。
    assert next_number(repo, "prd_scrum_board") == 1


def test_next_number_ignores_other_types() -> None:
    repo = InMemoryRepository()
    create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title="PBI")
    assert next_number(repo, PRODUCT) == 1


# --- new_sprint_data（ドメインフィールド） -----------------------------------


def test_new_sprint_data_defaults_to_planned() -> None:
    data = new_sprint_data()
    assert data["status"] == "planned"
    assert data["number"] is None  # 採番は create_sprint が打つプレースホルダ
    assert data["goal"] == ""
    assert data["startDate"] is None
    assert data["endDate"] is None


# --- create / get / list ------------------------------------------------------


def test_create_sprint_stamps_common_fields_and_number() -> None:
    repo = InMemoryRepository()
    doc = create_sprint(
        repo,
        product_id=PRODUCT,
        actor=ACTOR,
        goal="ログインを通す",
        start_date="2026-08-03",
        end_date="2026-08-14",
    )
    assert doc["id"].startswith("spr_")
    assert doc["type"] == "sprint"
    assert doc["productId"] == PRODUCT
    assert doc["number"] == 1
    assert doc["status"] == "planned"
    assert doc["goal"] == "ログインを通す"
    assert doc["startDate"] == "2026-08-03"
    assert doc["endDate"] == "2026-08-14"
    assert doc["createdBy"] == ACTOR
    assert doc["_etag"]  # ストアが採番する


def test_get_sprint_returns_stored_document() -> None:
    repo = InMemoryRepository()
    created = create_sprint(repo, product_id=PRODUCT, actor=ACTOR)
    fetched = get_sprint(repo, product_id=PRODUCT, sprint_id=created["id"])
    assert fetched is not None
    assert fetched["id"] == created["id"]


def test_get_sprint_missing_is_none() -> None:
    repo = InMemoryRepository()
    assert get_sprint(repo, product_id=PRODUCT, sprint_id="spr_missing") is None


def test_get_sprint_rejects_non_sprint_id() -> None:
    # 別型（PBI）の id を渡しても掴まない（型の防波堤）。
    repo = InMemoryRepository()
    pbi = create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title="PBI")
    assert get_sprint(repo, product_id=PRODUCT, sprint_id=pbi["id"]) is None


def test_list_sprints_orders_by_number() -> None:
    repo = InMemoryRepository()
    first = create_sprint(repo, product_id=PRODUCT, actor=ACTOR)
    second = create_sprint(repo, product_id=PRODUCT, actor=ACTOR)
    third = create_sprint(repo, product_id=PRODUCT, actor=ACTOR)
    numbers = [s["number"] for s in list_sprints(repo, PRODUCT)]
    assert numbers == [1, 2, 3]
    ids = [s["id"] for s in list_sprints(repo, PRODUCT)]
    assert ids == [first["id"], second["id"], third["id"]]


def test_list_sprints_excludes_soft_deleted() -> None:
    repo = InMemoryRepository()
    keep = create_sprint(repo, product_id=PRODUCT, actor=ACTOR)
    drop = create_sprint(repo, product_id=PRODUCT, actor=ACTOR)
    repo.soft_delete(product_id=PRODUCT, doc_id=drop["id"], actor=ACTOR, if_match=drop["_etag"])
    ids = [s["id"] for s in list_sprints(repo, PRODUCT)]
    assert ids == [keep["id"]]
