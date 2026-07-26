"""層3（Cosmos 契約）テストの接続フィクスチャ（B-11・D-19）。

フェイクでは代替できない領域だけをここで実サービス相当（エミュレータ）に当てる:

- ``_etag`` / ``If-Match`` / **412**（同時更新の検出はサーバー側の挙動）
- **インデックス除外パス**が実際に効いていること
- （将来）**トランザクショナルバッチの原子性**

接続情報は環境変数から読む。**未設定ならモジュールごと skip** する（日常の
``make test-backend`` は Cosmos なしで緑のまま）。CI の層3ジョブだけがエミュレータを
起動し、**ready ポーリング**の後にこれらを走らせる。
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from azure.cosmos import ContainerProxy, CosmosClient

from app.data.cosmos import CosmosRepository
from app.data.provisioning import ensure_container

REQUIRED_ENV = ("COSMOS_ENDPOINT", "COSMOS_KEY")


def _missing_env() -> list[str]:
    return [key for key in REQUIRED_ENV if not os.environ.get(key)]


@pytest.fixture(scope="session")
def cosmos_container() -> Iterator[ContainerProxy]:
    """エミュレータ上のコンテナを1度だけ用意する（PK ``/productId`` ＋除外パス）。

    本番と同じ :func:`app.data.provisioning.ensure_container` を通す。これにより
    「除外パスが実サービスで実際に適用されるか」を層3で裏取りできる。
    """
    missing = _missing_env()
    if missing:
        pytest.skip(f"Cosmos 未構成のため層3をスキップ（未設定: {', '.join(missing)}）")

    # エミュレータは自己署名証明書を使うため既定で検証を切る。実サービスに
    # 当てたいときだけ COSMOS_TLS_VERIFY=1 を渡す。
    verify = os.environ.get("COSMOS_TLS_VERIFY", "0") == "1"
    client = CosmosClient(
        url=os.environ["COSMOS_ENDPOINT"],
        credential=os.environ["COSMOS_KEY"],
        connection_verify=verify,
    )
    database = client.create_database_if_not_exists(
        id=os.environ.get("COSMOS_DATABASE", "scrumboard-contract"),
    )
    try:
        yield ensure_container(database)
    finally:
        client.close()


@pytest.fixture
def repo(cosmos_container: ContainerProxy) -> CosmosRepository:
    """契約対象の本番 Repository（フェイクと同じポートを実装）。"""
    return CosmosRepository(cosmos_container)


@pytest.fixture
def product_id() -> str:
    """テストごとに固有のパーティション。相互干渉と後片付けの手間を避ける。"""
    return f"prd_contract_{uuid.uuid4().hex[:12]}"
