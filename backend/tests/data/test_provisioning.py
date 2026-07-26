"""コンテナのインデックスポリシー（除外パス）のテスト。

Cosmos に接続せず、ポリシー構築が仕様どおり（PK と除外パス）かだけを検証する。
実際の作成・RU 削減の確認は層3／実サービス（B-11 / B-31）。
"""

from __future__ import annotations

from app.data.provisioning import (
    INDEX_EXCLUDED_PATHS,
    PARTITION_KEY_PATH,
    container_indexing_policy,
)


def test_partition_key_is_product_id() -> None:
    assert PARTITION_KEY_PATH == "/productId"


def test_indexing_policy_excludes_long_text_fields() -> None:
    policy = container_indexing_policy()
    excluded = {p["path"] for p in policy["excludedPaths"]}
    assert excluded == {"/description/?", "/memo/?", "/minutes/?"}
    # 提案書 06章の3フィールドと一致。
    assert set(INDEX_EXCLUDED_PATHS) == excluded


def test_indexing_policy_still_indexes_everything_else() -> None:
    policy = container_indexing_policy()
    included = {p["path"] for p in policy["includedPaths"]}
    assert "/*" in included
