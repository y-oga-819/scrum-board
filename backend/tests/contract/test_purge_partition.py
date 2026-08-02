"""層3: E2E teardown の物理削除（EX-1・D-22）。

``purge_partition`` は ``isDeleted`` に関わらずパーティション配下を実削除する。
論理削除（``soft_delete``）とは目的が違い、フェイクでは実 Cosmos の消え方を保証
できないため層3で確かめる。
"""

from __future__ import annotations

import pytest

from app.data.documents import DocumentType

pytestmark = pytest.mark.cosmos


def test_purge_removes_all_items_including_soft_deleted(repo, product_id) -> None:
    live = repo.create(
        product_id=product_id,
        doc_type=DocumentType.TASK,
        data={"title": "生きてる", "status": "todo"},
        actor="tester",
    )
    gone = repo.create(
        product_id=product_id,
        doc_type=DocumentType.TASK,
        data={"title": "論理削除済み", "status": "todo"},
        actor="tester",
    )
    # 1件は論理削除しておく。物理削除は isDeleted に関わらず消すことを確かめる。
    repo.soft_delete(
        product_id=product_id,
        doc_id=gone["id"],
        actor="tester",
        if_match=gone["_etag"],
    )

    removed = repo.purge_partition(product_id)

    assert removed == 2
    # 物理削除後はポイントリードでも見えない（論理削除の「存在しない扱い」とは別物）。
    assert repo.get(product_id, live["id"]) is None
    # 再実行は 0 件（冪等・空パーティションで例外を投げない）。
    assert repo.purge_partition(product_id) == 0
