"""コンテナの用意（B-07）。

provision-azure.sh（B-05）は Cosmos **アカウントとデータベース**までを作り、
コンテナは「B-07 で PK ``/productId`` 付きで作る」としてここに委ねている。
コンテナ作成は次の2点をアプリ側のコードで担保したいためスクリプトに置かない:

* **PK ``/productId``** — 単一コンテナ設計（D-08）の要。
* **インデックス除外パス** ``description`` / ``memo`` / ``minutes`` — 既定で全プロパティに
  索引が張られる。長文を除くと書き込み RU が目に見えて減る（提案書 06章）。

:func:`ensure_container` は ``create_container_if_not_exists`` で冪等。マイグレーション
機構（B-08）が起動／デプロイ時に呼ぶ。
"""

from __future__ import annotations

from typing import Any

from azure.cosmos import ContainerProxy, DatabaseProxy, PartitionKey

CONTAINER_NAME = "documents"
PARTITION_KEY_PATH = "/productId"

# 長文フィールドは索引から外す（提案書 06章）。``/?`` はそのパス直下の値を指す。
INDEX_EXCLUDED_PATHS: tuple[str, ...] = (
    "/description/?",
    "/memo/?",
    "/minutes/?",
)


def container_indexing_policy() -> dict[str, Any]:
    """除外パスを設定したインデックスポリシー。

    既定の「全パスを索引」を保ちつつ、長文3フィールドだけを除外する。
    ``/*`` を includedPaths に残すことで、他フィールドは従来どおり索引される。
    """
    return {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": [{"path": path} for path in INDEX_EXCLUDED_PATHS],
    }


def ensure_container(database: DatabaseProxy) -> ContainerProxy:
    """コンテナを冪等に用意して返す（PK ``/productId`` ＋除外パス設定済み）。"""
    return database.create_container_if_not_exists(
        id=CONTAINER_NAME,
        partition_key=PartitionKey(path=PARTITION_KEY_PATH),
        indexing_policy=container_indexing_policy(),
    )
