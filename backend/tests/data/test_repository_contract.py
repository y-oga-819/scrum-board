"""Repository ポートの契約テスト（B-07）。

ポートだけを触り、実装の内部を仮定しない。層3（B-11）で同じ期待を
``CosmosRepository`` にも通せるよう、``repo`` フィクスチャ越しに検証する。

確かめること:
* 共通フィールド付与（作成で id/type/isDeleted/タイムスタンプが載る）
* ``NOT isDeleted`` の除外が get / query の両方で効く
* ``_etag`` 楽観排他（一致で通り、不一致で 412、欠落は型で塞がれている）
* id 重複が 409、対象なしが 404
"""

from __future__ import annotations

import pytest

from app.data.documents import DocumentType
from app.data.errors import ConflictError, NotFoundError, PreconditionFailedError
from app.data.fake import InMemoryRepository

PRODUCT = "prd_001"


def _create_pbi(repo: InMemoryRepository, **data: object):
    return repo.create(
        product_id=PRODUCT,
        doc_type=DocumentType.PBI,
        data={"title": "t", "rank": "m", **data},
        actor="oid-1",
    )


def test_create_stamps_common_fields_and_etag(repo: InMemoryRepository) -> None:
    doc = _create_pbi(repo)
    assert doc["id"].startswith("pbi_")
    assert doc["type"] == "pbi"
    assert doc["productId"] == PRODUCT
    assert doc["isDeleted"] is False
    assert doc["createdAt"] == "2026-08-03T09:12:00Z"
    assert doc["createdBy"] == "oid-1"
    assert doc["_etag"]


def test_create_accepts_explicit_deterministic_id(repo: InMemoryRepository) -> None:
    # usr_<oid> / mbr_<oid> など決定的 ID（D-21）。
    doc = repo.create(
        product_id="_system",
        doc_type=DocumentType.USER,
        data={"oid": "abc"},
        actor="abc",
        doc_id="usr_abc",
    )
    assert doc["id"] == "usr_abc"


def test_get_returns_created_document(repo: InMemoryRepository) -> None:
    created = _create_pbi(repo)
    fetched = repo.get(PRODUCT, created["id"])
    assert fetched == created


def test_get_missing_returns_none(repo: InMemoryRepository) -> None:
    assert repo.get(PRODUCT, "pbi_nope") is None


def test_get_scoped_by_product(repo: InMemoryRepository) -> None:
    created = _create_pbi(repo)
    # 別パーティションからは見えない（PK スコープ）。
    assert repo.get("prd_other", created["id"]) is None


def test_duplicate_id_raises_conflict(repo: InMemoryRepository) -> None:
    repo.create(
        product_id=PRODUCT,
        doc_type=DocumentType.PBI,
        data={},
        actor="oid",
        doc_id="pbi_dup",
    )
    with pytest.raises(ConflictError):
        repo.create(
            product_id=PRODUCT,
            doc_type=DocumentType.PBI,
            data={},
            actor="oid",
            doc_id="pbi_dup",
        )


# --- 論理削除の除外 --------------------------------------------------------------


def test_soft_delete_hides_from_get(repo: InMemoryRepository) -> None:
    created = _create_pbi(repo)
    repo.soft_delete(
        product_id=PRODUCT,
        doc_id=created["id"],
        actor="oid",
        if_match=created["_etag"],
    )
    assert repo.get(PRODUCT, created["id"]) is None


def test_soft_delete_hides_from_query(repo: InMemoryRepository) -> None:
    keep = _create_pbi(repo, rank="a")
    drop = _create_pbi(repo, rank="b")
    repo.soft_delete(
        product_id=PRODUCT,
        doc_id=drop["id"],
        actor="oid",
        if_match=drop["_etag"],
    )
    ids = [d["id"] for d in repo.query(product_id=PRODUCT, doc_type=DocumentType.PBI)]
    assert ids == [keep["id"]]


# --- query -----------------------------------------------------------------------


def test_query_filters_by_type(repo: InMemoryRepository) -> None:
    _create_pbi(repo)
    repo.create(
        product_id=PRODUCT,
        doc_type=DocumentType.TASK,
        data={"rank": "a"},
        actor="oid",
    )
    pbis = repo.query(product_id=PRODUCT, doc_type=DocumentType.PBI)
    assert len(pbis) == 1
    assert pbis[0]["type"] == "pbi"


def test_query_orders_by_rank_then_id(repo: InMemoryRepository) -> None:
    b = _create_pbi(repo, rank="b", title="B")
    a2 = repo.create(
        product_id=PRODUCT,
        doc_type=DocumentType.PBI,
        data={"rank": "a", "title": "A2"},
        actor="oid",
        doc_id="pbi_zzz",
    )
    a1 = repo.create(
        product_id=PRODUCT,
        doc_type=DocumentType.PBI,
        data={"rank": "a", "title": "A1"},
        actor="oid",
        doc_id="pbi_aaa",
    )
    ordered = repo.query(product_id=PRODUCT, doc_type=DocumentType.PBI)
    # rank 昇順、同 rank は id をタイブレーカーに（D-18）。
    assert [d["id"] for d in ordered] == [a1["id"], a2["id"], b["id"]]


def test_query_equals_filter_including_null(repo: InMemoryRepository) -> None:
    assigned = repo.create(
        product_id=PRODUCT,
        doc_type=DocumentType.TASK,
        data={"rank": "a", "sprintId": "spr_1"},
        actor="oid",
    )
    waiting = repo.create(
        product_id=PRODUCT,
        doc_type=DocumentType.TASK,
        data={"rank": "b", "sprintId": None},
        actor="oid",
    )
    in_sprint = repo.query(
        product_id=PRODUCT, doc_type=DocumentType.TASK, equals={"sprintId": "spr_1"}
    )
    unassigned = repo.query(
        product_id=PRODUCT, doc_type=DocumentType.TASK, equals={"sprintId": None}
    )
    assert [d["id"] for d in in_sprint] == [assigned["id"]]
    assert [d["id"] for d in unassigned] == [waiting["id"]]


# --- クロスパーティションクエリ（所属プロダクト列挙。B-10） ------------------------


def test_query_across_partitions_spans_all_partitions(repo: InMemoryRepository) -> None:
    # 同じ oid の member を別々のプロダクト（別パーティション）に作る。
    repo.create(
        product_id="prd_sandbox",
        doc_type=DocumentType.MEMBER,
        data={"userId": "oid-1", "role": "member"},
        actor="oid-1",
        doc_id="mbr_oid-1",
    )
    repo.create(
        product_id="prd_scrum_board",
        doc_type=DocumentType.MEMBER,
        data={"userId": "oid-1", "role": "admin"},
        actor="oid-1",
        doc_id="mbr_oid-1",
    )
    # 別ユーザーの member はノイズとして除外されること。
    repo.create(
        product_id="prd_sandbox",
        doc_type=DocumentType.MEMBER,
        data={"userId": "oid-2", "role": "member"},
        actor="oid-2",
        doc_id="mbr_oid-2",
    )

    found = repo.query_across_partitions(doc_type=DocumentType.MEMBER, equals={"userId": "oid-1"})

    products = {d["productId"] for d in found}
    assert products == {"prd_sandbox", "prd_scrum_board"}


def test_query_across_partitions_filters_by_type(repo: InMemoryRepository) -> None:
    repo.create(
        product_id="prd_a",
        doc_type=DocumentType.MEMBER,
        data={"userId": "oid-1", "role": "member"},
        actor="oid-1",
        doc_id="mbr_oid-1",
    )
    _create_pbi(repo)  # 別型は横断でも拾わない

    found = repo.query_across_partitions(doc_type=DocumentType.MEMBER)
    assert [d["type"] for d in found] == ["member"]


def test_query_across_partitions_excludes_soft_deleted(repo: InMemoryRepository) -> None:
    created = repo.create(
        product_id="prd_a",
        doc_type=DocumentType.MEMBER,
        data={"userId": "oid-1", "role": "member"},
        actor="oid-1",
        doc_id="mbr_oid-1",
    )
    repo.soft_delete(
        product_id="prd_a", doc_id=created["id"], actor="oid-1", if_match=created["_etag"]
    )

    assert repo.query_across_partitions(doc_type=DocumentType.MEMBER) == []


# --- 楽観排他 --------------------------------------------------------------------


def test_replace_with_matching_etag_updates_and_rotates_etag(repo: InMemoryRepository) -> None:
    created = _create_pbi(repo, status="new")
    updated = repo.replace(
        product_id=PRODUCT,
        doc_id=created["id"],
        changes={"status": "ready"},
        actor="editor",
        if_match=created["_etag"],
    )
    assert updated["status"] == "ready"
    assert updated["updatedBy"] == "editor"
    assert updated["_etag"] != created["_etag"]


def test_replace_with_stale_etag_raises_412(repo: InMemoryRepository) -> None:
    created = _create_pbi(repo, status="new")
    # 先に誰かが更新して etag が回る。
    repo.replace(
        product_id=PRODUCT,
        doc_id=created["id"],
        changes={"status": "ready"},
        actor="first",
        if_match=created["_etag"],
    )
    # 元の（古い）etag で更新しようとすると 412。更新が黙って消えない。
    with pytest.raises(PreconditionFailedError):
        repo.replace(
            product_id=PRODUCT,
            doc_id=created["id"],
            changes={"status": "inProgress"},
            actor="second",
            if_match=created["_etag"],
        )


def test_replace_missing_document_raises_404(repo: InMemoryRepository) -> None:
    with pytest.raises(NotFoundError):
        repo.replace(
            product_id=PRODUCT,
            doc_id="pbi_nope",
            changes={"status": "ready"},
            actor="oid",
            if_match='"whatever"',
        )


def test_soft_delete_with_stale_etag_raises_412(repo: InMemoryRepository) -> None:
    created = _create_pbi(repo)
    repo.replace(
        product_id=PRODUCT,
        doc_id=created["id"],
        changes={"status": "ready"},
        actor="first",
        if_match=created["_etag"],
    )
    with pytest.raises(PreconditionFailedError):
        repo.soft_delete(
            product_id=PRODUCT,
            doc_id=created["id"],
            actor="second",
            if_match=created["_etag"],
        )


def test_returned_documents_are_copies(repo: InMemoryRepository) -> None:
    created = _create_pbi(repo)
    created["title"] = "mutated outside"
    # 返り値を外で書き換えてもストアは汚れない。
    fetched = repo.get(PRODUCT, created["id"])
    assert fetched is not None
    assert fetched["title"] == "t"
