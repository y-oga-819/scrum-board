"""``user`` ドメイン（B-10・D-21）の契約テスト。

``id = usr_<oid>`` のポイントリード可能性・``_system`` パーティションへの配置・
二重作成の 409 を、フェイク Repository の観測可能な振る舞いだけで検証する。
"""

from __future__ import annotations

import pytest

from app.data.documents import SYSTEM_PARTITION
from app.data.errors import ConflictError
from app.data.fake import InMemoryRepository
from app.data.users import create_user, get_user, user_id

OID = "00000000-1111-2222-3333-444444444444"


def test_user_id_is_deterministic_from_oid() -> None:
    # ポイントリードの鍵。oid から一意に決まり、usr 接頭辞を持つ（D-21）。
    assert user_id(OID) == f"usr_{OID}"
    assert user_id(OID) == user_id(OID)


def test_create_user_stamps_claims_in_system_partition(repo: InMemoryRepository) -> None:
    doc = create_user(
        repo, oid=OID, display_name="Ada Lovelace", email="ada@example.com", actor=OID
    )

    assert doc["id"] == user_id(OID)
    assert doc["type"] == "user"
    # user はどのプロダクトにも属さない → 予約パーティション _system に置く（D-21）。
    assert doc["productId"] == SYSTEM_PARTITION
    assert doc["oid"] == OID
    assert doc["displayName"] == "Ada Lovelace"
    assert doc["email"] == "ada@example.com"
    assert doc["_etag"]  # ストアが採番している


def test_create_user_tolerates_missing_claims(repo: InMemoryRepository) -> None:
    # name / preferred_username が無いトークンでも user は作れる（形は保つ）。
    doc = create_user(repo, oid=OID, display_name=None, email=None, actor=OID)

    assert doc["displayName"] is None
    assert doc["email"] is None


def test_get_user_point_reads_the_created_user(repo: InMemoryRepository) -> None:
    create_user(repo, oid=OID, display_name="Ada", email=None, actor=OID)

    found = get_user(repo, OID)

    assert found is not None
    assert found["oid"] == OID


def test_unknown_user_reads_as_none(repo: InMemoryRepository) -> None:
    # 未登録は None（→ 初回サインインで作成する）。
    assert get_user(repo, OID) is None


def test_duplicate_user_conflicts(repo: InMemoryRepository) -> None:
    # id が oid から決定的なので二重作成は 409（onboarding が握りつぶす前提）。
    create_user(repo, oid=OID, display_name="Ada", email=None, actor=OID)

    with pytest.raises(ConflictError):
        create_user(repo, oid=OID, display_name="Ada", email=None, actor=OID)
