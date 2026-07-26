"""Cosmos 接続の構成値と Repository の組み立て（B-07）。

環境変数から接続情報を読み、コンテナを冪等に用意して
:class:`~app.data.cosmos.CosmosRepository` を返す。App Service には
provision-azure.sh（B-05）が ``COSMOS_ENDPOINT`` / ``COSMOS_DATABASE`` を流し込む。
鍵は ``COSMOS_KEY``（当面はキー接続。将来マネージド ID へ寄せる余地を残す）。

実際に呼ぶのはデータを要する工程から（B-08 マイグレーション以降）。認証だけの
M1 では DB を触らないため、``main.py`` はここに依存しない（未設定でも起動する）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from azure.cosmos import CosmosClient

from .clock import Clock
from .cosmos import CosmosRepository
from .provisioning import ensure_container


@dataclass(frozen=True)
class CosmosSettings:
    """Cosmos への接続に必要な値。"""

    endpoint: str
    key: str
    database: str

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint) and bool(self.key) and bool(self.database)


def cosmos_settings_from_env() -> CosmosSettings:
    """環境変数から ``CosmosSettings`` を作る（未設定は空文字）。"""
    return CosmosSettings(
        endpoint=os.environ.get("COSMOS_ENDPOINT", ""),
        key=os.environ.get("COSMOS_KEY", ""),
        database=os.environ.get("COSMOS_DATABASE", ""),
    )


def create_repository(
    settings: CosmosSettings,
    *,
    clock: Clock | None = None,
) -> CosmosRepository:
    """接続してコンテナを用意し、本番 Repository を返す。

    ``create_container_if_not_exists`` により、コンテナが無ければ PK ``/productId`` ＋
    除外パス付きで作る（B-07）。既にあれば何もしない。
    """
    client = CosmosClient(url=settings.endpoint, credential=settings.key)
    database = client.get_database_client(settings.database)
    container = ensure_container(database)
    return CosmosRepository(container, clock=clock)
