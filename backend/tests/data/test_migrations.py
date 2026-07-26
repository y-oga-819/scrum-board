"""マイグレーション機構のテスト（B-08・D-21）。

B-08 の完了条件を一つずつ確かめる:

* 未適用のものだけが version 昇順に適用される
* 適用後に ``_system`` へ ``mig_<version>`` が記録される
* サンドボックス（``prd_sandbox``）と本番（``prd_scrum_board``）の product が作られる
* マイグレーションは ``member`` と ``user`` を作らない
* 冪等（再実行で何も起きない・重複を作らない）

フェイク Repository で回す（Cosmos 不要。D-19 の層1・2）。
"""

from __future__ import annotations

import pytest

from app.data.documents import SYSTEM_PARTITION, DocumentType
from app.data.errors import ReservedProductIdError
from app.data.fake import InMemoryRepository
from app.data.migrations import MIGRATIONS, applied_versions, run_migrations
from app.data.migrations.runner import MIGRATION_ACTOR, Migration
from app.data.products import (
    SANDBOX_PRODUCT_ID,
    SCRUM_BOARD_PRODUCT_ID,
    create_product,
)


def test_run_from_empty_applies_all_in_order(repo: InMemoryRepository) -> None:
    applied = run_migrations(repo)
    # 宣言順（＝ version 昇順）にすべて適用される。
    assert applied == ["001", "002"]
    assert applied_versions(repo) == {"001", "002"}


def test_creates_both_products(repo: InMemoryRepository) -> None:
    run_migrations(repo)
    sandbox = repo.get(SANDBOX_PRODUCT_ID, SANDBOX_PRODUCT_ID)
    scrum_board = repo.get(SCRUM_BOARD_PRODUCT_ID, SCRUM_BOARD_PRODUCT_ID)
    assert sandbox is not None and sandbox["type"] == "product"
    assert sandbox["name"] == "サンドボックス"
    assert scrum_board is not None and scrum_board["type"] == "product"
    assert scrum_board["name"] == "スクラムボード"


def test_records_migration_document_with_version_and_applied_at(
    repo: InMemoryRepository, clock: object
) -> None:
    run_migrations(repo, clock=clock)  # type: ignore[arg-type]
    record = repo.get(SYSTEM_PARTITION, "mig_001")
    assert record is not None
    assert record["type"] == "migration"
    assert record["version"] == "001"
    # appliedAt は注入した固定時計から（D-19：時刻を固定して検証する）。
    assert record["appliedAt"] == "2026-08-03T09:12:00Z"
    assert record["createdBy"] == MIGRATION_ACTOR


def test_does_not_create_member_or_user(repo: InMemoryRepository) -> None:
    run_migrations(repo)
    # どのパーティションにも member / user は生まれない（D-21）。
    for product_id in (SYSTEM_PARTITION, SANDBOX_PRODUCT_ID, SCRUM_BOARD_PRODUCT_ID):
        assert repo.query(product_id=product_id, doc_type=DocumentType.MEMBER) == []
        assert repo.query(product_id=product_id, doc_type=DocumentType.USER) == []


def test_rerun_is_idempotent(repo: InMemoryRepository) -> None:
    run_migrations(repo)
    # 2度目は未適用が無いので何も適用されない（バージョン記録で冪等。id 重複の
    # 409 も起きない）。
    applied = run_migrations(repo)
    assert applied == []
    # 記録も product も重複しない。
    assert len(repo.query(product_id=SYSTEM_PARTITION, doc_type=DocumentType.MIGRATION)) == 2


def test_only_unapplied_are_applied(repo: InMemoryRepository) -> None:
    # 001 を先に適用済みにしておく（記録だけ入れる）。
    repo.create(
        product_id=SYSTEM_PARTITION,
        doc_type=DocumentType.MIGRATION,
        data={"version": "001", "appliedAt": "2026-01-01T00:00:00Z"},
        actor="prior",
        doc_id="mig_001",
    )
    applied = run_migrations(repo)
    # 002 だけが走る。
    assert applied == ["002"]
    # 001 の product（サンドボックス）は今回作られていない＝再適用していない。
    assert repo.get(SANDBOX_PRODUCT_ID, SANDBOX_PRODUCT_ID) is None
    assert repo.get(SCRUM_BOARD_PRODUCT_ID, SCRUM_BOARD_PRODUCT_ID) is not None


def test_applies_in_version_order_regardless_of_declaration_order(
    repo: InMemoryRepository,
) -> None:
    order: list[str] = []

    def make(version: str) -> Migration:
        def apply(r: InMemoryRepository, *, actor: str) -> None:
            order.append(version)

        return Migration(version=version, description=version, apply=apply)  # type: ignore[arg-type]

    # 宣言順は 002, 001 だが、version 昇順に適用される。
    applied = run_migrations(repo, migrations=(make("002"), make("001")))
    assert applied == ["001", "002"]
    assert order == ["001", "002"]


def test_registry_versions_are_unique_and_sorted() -> None:
    versions = [m.version for m in MIGRATIONS]
    assert versions == sorted(versions)
    assert len(versions) == len(set(versions))


def test_migration_body_uses_reserved_id_guard(repo: InMemoryRepository) -> None:
    # create_product 経由なので、うっかり _system を作るマイグレーションは書けない。
    # （ここでは関門が生きていることの確認。）
    with pytest.raises(ReservedProductIdError):
        create_product(repo, product_id=SYSTEM_PARTITION, name="x", actor="a")
