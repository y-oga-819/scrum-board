"""``member`` ドメイン（B-09・D-21）の契約テスト。

``id = mbr_<oid>`` のポイントリード可能性・``oid`` をキーにすること・二重作成の 409 を、
フェイク Repository の観測可能な振る舞いだけで検証する（実装内部に触れない）。
"""

from __future__ import annotations

import pytest

from app.data.errors import ConflictError
from app.data.fake import InMemoryRepository
from app.data.members import (
    Role,
    create_member,
    get_member,
    is_member,
    member_id,
    upsert_member,
)

OID = "00000000-1111-2222-3333-444444444444"
PRODUCT = "prd_sandbox"
ACTOR = OID


def test_member_id_is_deterministic_from_oid() -> None:
    # ポイントリードの鍵。oid から一意に決まり、mbr 接頭辞を持つ（D-21）。
    assert member_id(OID) == f"mbr_{OID}"
    assert member_id(OID) == member_id(OID)


def test_create_member_stamps_userid_and_role(repo: InMemoryRepository) -> None:
    doc = create_member(repo, product_id=PRODUCT, oid=OID, role=Role.MEMBER, actor=ACTOR)

    assert doc["id"] == member_id(OID)
    assert doc["type"] == "member"
    assert doc["productId"] == PRODUCT
    # oid をキーにする（メールアドレスをキーにしない — 提案書08章）。
    assert doc["userId"] == OID
    assert doc["role"] == "member"
    assert doc["_etag"]  # ストアが採番している


def test_get_member_point_reads_the_created_member(repo: InMemoryRepository) -> None:
    create_member(repo, product_id=PRODUCT, oid=OID, role=Role.ADMIN, actor=ACTOR)

    found = get_member(repo, product_id=PRODUCT, oid=OID)

    assert found is not None
    assert found["role"] == "admin"
    assert is_member(repo, product_id=PRODUCT, oid=OID) is True


def test_non_member_reads_as_none(repo: InMemoryRepository) -> None:
    # メンバーでなければポイントリードは None（→ 認可は 403 に振る）。
    assert get_member(repo, product_id=PRODUCT, oid=OID) is None
    assert is_member(repo, product_id=PRODUCT, oid=OID) is False


def test_membership_is_scoped_to_its_product(repo: InMemoryRepository) -> None:
    # サンドボックスの member は本番プロダクトのメンバー資格にならない（D-21）。
    create_member(repo, product_id=PRODUCT, oid=OID, role=Role.MEMBER, actor=ACTOR)

    assert is_member(repo, product_id="prd_scrum_board", oid=OID) is False


def test_duplicate_member_conflicts(repo: InMemoryRepository) -> None:
    # id が oid から決定的なので二重作成は 409（B-10 が握りつぶす前提）。
    create_member(repo, product_id=PRODUCT, oid=OID, role=Role.MEMBER, actor=ACTOR)

    with pytest.raises(ConflictError):
        create_member(repo, product_id=PRODUCT, oid=OID, role=Role.MEMBER, actor=ACTOR)


# --- upsert（本番登録スクリプトの再実行可能性。B-10・D-21） --------------------------


def test_upsert_creates_when_absent(repo: InMemoryRepository) -> None:
    doc = upsert_member(repo, product_id=PRODUCT, oid=OID, role=Role.ADMIN)

    assert doc["id"] == member_id(OID)
    assert doc["role"] == "admin"


def test_upsert_updates_role_when_present(repo: InMemoryRepository) -> None:
    # 再実行で role を昇格できる（member → admin）。楽観排他つきの更新（D-20）。
    create_member(repo, product_id=PRODUCT, oid=OID, role=Role.MEMBER, actor=ACTOR)

    doc = upsert_member(repo, product_id=PRODUCT, oid=OID, role=Role.ADMIN)

    assert doc["role"] == "admin"
    reread = get_member(repo, product_id=PRODUCT, oid=OID)
    assert reread is not None
    assert reread["role"] == "admin"


def test_upsert_is_noop_when_role_unchanged(repo: InMemoryRepository) -> None:
    # role が同じなら etag を回さない（無駄な書き込みをしない）。
    created = create_member(repo, product_id=PRODUCT, oid=OID, role=Role.ADMIN, actor=ACTOR)

    again = upsert_member(repo, product_id=PRODUCT, oid=OID, role=Role.ADMIN)

    assert again["_etag"] == created["_etag"]


def test_soft_deleted_member_is_not_a_member(repo: InMemoryRepository) -> None:
    # 論理削除された member はメンバー扱いしない（認可が静かに通り続けない）。
    doc = create_member(repo, product_id=PRODUCT, oid=OID, role=Role.MEMBER, actor=ACTOR)
    repo.soft_delete(product_id=PRODUCT, doc_id=doc["id"], actor=ACTOR, if_match=doc["_etag"])

    assert get_member(repo, product_id=PRODUCT, oid=OID) is None
    assert is_member(repo, product_id=PRODUCT, oid=OID) is False
