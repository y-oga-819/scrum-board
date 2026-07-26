"""プロダクト生成と予約 productId のテスト（B-08・D-21）。

``product`` は自分自身のパーティションの根（``id == productId``）であること、
``_system`` を productId に払い出そうとしたら弾かれることを確かめる。
"""

from __future__ import annotations

import pytest

from app.data.documents import SYSTEM_PARTITION
from app.data.errors import ReservedProductIdError
from app.data.fake import InMemoryRepository
from app.data.products import (
    RESERVED_PRODUCT_IDS,
    SANDBOX_PRODUCT_ID,
    create_product,
    is_reserved_product_id,
)


def test_system_partition_is_reserved() -> None:
    assert is_reserved_product_id(SYSTEM_PARTITION) is True
    assert SYSTEM_PARTITION in RESERVED_PRODUCT_IDS


def test_normal_product_id_is_not_reserved() -> None:
    assert is_reserved_product_id(SANDBOX_PRODUCT_ID) is False
    assert is_reserved_product_id("prd_anything") is False


def test_create_product_stores_self_partitioned_document(repo: InMemoryRepository) -> None:
    doc = create_product(repo, product_id="prd_x", name="X", actor="oid")
    # product は id == productId（自分自身のパーティションの根）。
    assert doc["id"] == "prd_x"
    assert doc["productId"] == "prd_x"
    assert doc["type"] == "product"
    assert doc["name"] == "X"
    # 実際に同じパーティションからポイントリードで引ける。
    assert repo.get("prd_x", "prd_x") == doc


def test_create_product_rejects_reserved_id(repo: InMemoryRepository) -> None:
    with pytest.raises(ReservedProductIdError):
        create_product(repo, product_id=SYSTEM_PARTITION, name="nope", actor="oid")
    # 予約語は1件も書かれない。
    assert repo.get(SYSTEM_PARTITION, SYSTEM_PARTITION) is None
