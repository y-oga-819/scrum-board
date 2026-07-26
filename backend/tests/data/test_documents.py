"""共通フィールド付与（stamp_new / stamp_update）のテスト。"""

from __future__ import annotations

from datetime import UTC, datetime

from app.data.documents import DocumentType, stamp_new, stamp_update

from .conftest import FixedClock


def test_stamp_new_sets_common_fields() -> None:
    clock = FixedClock(datetime(2026, 8, 3, 9, 12, 0, tzinfo=UTC))
    doc = stamp_new(
        {"title": "ログイン機能"},
        doc_type=DocumentType.PBI,
        product_id="prd_001",
        doc_id="pbi_X",
        actor="oid-123",
        clock=clock,
    )
    assert doc == {
        "title": "ログイン機能",
        "id": "pbi_X",
        "type": "pbi",
        "productId": "prd_001",
        "isDeleted": False,
        "createdAt": "2026-08-03T09:12:00Z",
        "createdBy": "oid-123",
        "updatedAt": "2026-08-03T09:12:00Z",
        "updatedBy": "oid-123",
    }


def test_stamp_new_does_not_mutate_input() -> None:
    source = {"title": "x"}
    stamp_new(
        source,
        doc_type=DocumentType.TASK,
        product_id="prd_001",
        doc_id="tsk_1",
        actor="oid",
        clock=FixedClock(datetime(2026, 8, 3, tzinfo=UTC)),
    )
    assert source == {"title": "x"}


def test_stamp_update_touches_only_update_meta_and_changes() -> None:
    created = FixedClock(datetime(2026, 8, 3, 9, 0, 0, tzinfo=UTC))
    current = stamp_new(
        {"status": "new"},
        doc_type=DocumentType.PBI,
        product_id="prd_001",
        doc_id="pbi_X",
        actor="creator",
        clock=created,
    )
    later = FixedClock(datetime(2026, 8, 5, 14, 2, 0, tzinfo=UTC))
    updated = stamp_update(current, {"status": "ready"}, actor="editor", clock=later)

    assert updated["status"] == "ready"
    assert updated["updatedAt"] == "2026-08-05T14:02:00Z"
    assert updated["updatedBy"] == "editor"
    # createdAt/By は不変。
    assert updated["createdAt"] == "2026-08-03T09:00:00Z"
    assert updated["createdBy"] == "creator"


def test_stamp_update_ignores_immutable_fields() -> None:
    clock = FixedClock(datetime(2026, 8, 3, tzinfo=UTC))
    current = stamp_new(
        {},
        doc_type=DocumentType.PBI,
        product_id="prd_001",
        doc_id="pbi_X",
        actor="creator",
        clock=clock,
    )
    tampered = stamp_update(
        current,
        {"id": "pbi_EVIL", "type": "task", "productId": "prd_other", "createdBy": "x"},
        actor="editor",
        clock=clock,
    )
    assert tampered["id"] == "pbi_X"
    assert tampered["type"] == "pbi"
    assert tampered["productId"] == "prd_001"
    assert tampered["createdBy"] == "creator"
