"""``CosmosRepository`` の実 SDK 呼び出しに関する単体テスト（モック）。

フェイク（:class:`~app.data.fake.InMemoryRepository`）では表面化しないが実サービスでは
効く挙動を、``ContainerProxy`` をモックして固定する。ここで守るのは「SDK に正しい
引数を渡しているか」であって、Cosmos 自体の挙動（層3・実サービス）ではない。
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.data.cosmos import CosmosRepository
from app.data.documents import DocumentType


def test_query_across_partitions_enables_cross_partition_query() -> None:
    # partition_key を渡さない横断クエリは、この SDK では
    # ``enable_cross_partition_query=True`` を明示しないと
    # BadRequest("Cross partition query is required but disabled") で落ちる。
    # フェイクでは出ず実サービスで初めて出たため、フラグを渡すことを固定する。
    container = MagicMock()
    container.query_items.return_value = iter([])
    repo = CosmosRepository(container)

    repo.query_across_partitions(doc_type=DocumentType.MEMBER, equals={"userId": "oid-x"})

    assert container.query_items.call_count == 1
    kwargs = container.query_items.call_args.kwargs
    assert kwargs.get("enable_cross_partition_query") is True
    # 横断クエリに partition_key は渡さない（渡すと単一パーティションに絞られる）。
    assert "partition_key" not in kwargs
