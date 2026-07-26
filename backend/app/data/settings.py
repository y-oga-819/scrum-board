"""Cosmos 接続の構成値と Repository の組み立て（B-07）。

環境変数から接続情報を読み、コンテナを冪等に用意して
:class:`~app.data.cosmos.CosmosRepository` を返す。App Service には
provision-azure.sh（B-05）が ``COSMOS_ENDPOINT`` / ``COSMOS_DATABASE`` を流し込む。
鍵は ``COSMOS_KEY``（当面はキー接続。将来マネージド ID へ寄せる余地を残す）。

**``CosmosClient`` はアプリのライフタイムで1個だけ生成して使い回す**（シングルトン）。
リクエストごとに作ると、生成のたびにアカウントのトポロジ探索（メタデータ往復）と
新規 TLS ハンドシェイクが走り、F1/B1 のコールドスタート環境では体感遅延に直結する。
コネクションプール（keep-alive）はクライアントが内部で持つため自前管理は不要。

そのため用途で入り口を2つに分ける。

* **長命なサーバー**（FastAPI）… :func:`create_client` でクライアントを1度だけ作り、
  ``main.py`` の lifespan が所有して使い回し、shutdown で ``close()`` する。
  リポジトリは :func:`build_repository` でそのクライアントから組む。
* **短命なプロセス**（スクリプト・マイグレーション CLI）… :func:`create_repository` で
  一括生成してよい。プロセス終了で接続は片付く。

実際に呼ぶのはデータを要する工程から（B-08 マイグレーション以降）。認証だけの
M1 では DB を触らないため、未設定なら DB 無しで起動する（lifespan が何もしない）。
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


def create_client(settings: CosmosSettings) -> CosmosClient:
    """``CosmosClient`` を生成する。**呼び出し側が1個だけ持って使い回す**こと。

    サーバーでは lifespan がこれを所有し、shutdown で ``close()`` する。
    """
    return CosmosClient(url=settings.endpoint, credential=settings.key)


def build_repository(
    client: CosmosClient,
    settings: CosmosSettings,
    *,
    clock: Clock | None = None,
) -> CosmosRepository:
    """既存クライアントからコンテナを用意し、本番 Repository を組む。

    ``create_container_if_not_exists`` により、コンテナが無ければ PK ``/productId`` ＋
    除外パス付きで作る（B-07）。既にあれば何もしない（冪等）。
    """
    database = client.get_database_client(settings.database)
    container = ensure_container(database)
    return CosmosRepository(container, clock=clock)


def create_repository(
    settings: CosmosSettings,
    *,
    clock: Clock | None = None,
) -> CosmosRepository:
    """短命プロセス向けの簡便版（クライアント生成＋リポジトリ構築を一括）。

    スクリプトやマイグレーション CLI のように**プロセスが短命**で、終了時に接続が
    自然に片付く場面で使う。長命なサーバーでは代わりに :func:`create_client` ＋
    :func:`build_repository` を lifespan で使い、クライアントを使い回す。
    """
    return build_repository(create_client(settings), settings, clock=clock)
