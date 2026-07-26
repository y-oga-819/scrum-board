"""層3: ``_etag`` / ``If-Match`` / 412（B-11・D-19）。

同時更新の検出は**サーバー側の挙動**であり、フェイクでは本物を保証できない。
ここが層3の一丁目一番地（提案書 06章の「更新が黙って消える」を塞ぐ土台）。
"""

from __future__ import annotations

import pytest

from app.data.documents import DocumentType
from app.data.errors import PreconditionFailedError

pytestmark = pytest.mark.cosmos


def test_fresh_if_match_replaces(repo, product_id) -> None:
    created = repo.create(
        product_id=product_id,
        doc_type=DocumentType.TASK,
        data={"title": "元のタイトル", "status": "todo"},
        actor="tester",
    )
    updated = repo.replace(
        product_id=product_id,
        doc_id=created["id"],
        changes={"title": "更新後"},
        actor="tester",
        if_match=created["_etag"],
    )
    assert updated["title"] == "更新後"
    # etag は更新のたびに変わる（次の楽観排他の鍵）。
    assert updated["_etag"] != created["_etag"]


def test_stale_if_match_on_replace_raises_412(repo, product_id) -> None:
    created = repo.create(
        product_id=product_id,
        doc_type=DocumentType.TASK,
        data={"title": "元", "status": "todo"},
        actor="tester",
    )
    stale_etag = created["_etag"]

    # 1人目の更新は成功し、etag が進む。
    repo.replace(
        product_id=product_id,
        doc_id=created["id"],
        changes={"title": "1人目"},
        actor="user-a",
        if_match=stale_etag,
    )

    # 2人目が「読んだときの etag（stale）」で更新すると 412。片方の更新が消えない。
    with pytest.raises(PreconditionFailedError):
        repo.replace(
            product_id=product_id,
            doc_id=created["id"],
            changes={"title": "2人目"},
            actor="user-b",
            if_match=stale_etag,
        )


def test_stale_if_match_on_soft_delete_raises_412(repo, product_id) -> None:
    created = repo.create(
        product_id=product_id,
        doc_type=DocumentType.TASK,
        data={"title": "消す対象", "status": "todo"},
        actor="tester",
    )
    stale_etag = created["_etag"]
    repo.replace(
        product_id=product_id,
        doc_id=created["id"],
        changes={"title": "先に更新"},
        actor="user-a",
        if_match=stale_etag,
    )

    with pytest.raises(PreconditionFailedError):
        repo.soft_delete(
            product_id=product_id,
            doc_id=created["id"],
            actor="user-b",
            if_match=stale_etag,
        )
