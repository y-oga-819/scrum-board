"""PBI のドメイン規則とデータアクセスのテスト（B-15）。

状態遷移の正当性（提案書 図6）と、生成・参照がポート契約（共通フィールド付与・
論理削除除外・型による防波堤）に乗っていることを確かめる。
"""

from __future__ import annotations

import pytest

from app.data.documents import DocumentType
from app.data.fake import InMemoryRepository
from app.data.members import Role, create_member
from app.data.pbis import (
    PbiStatus,
    create_pbi,
    get_pbi,
    is_valid_transition,
    new_pbi_data,
)

PRODUCT = "prd_sandbox"
ACTOR = "oid-author"


# --- 状態遷移（純関数・提案書 図6） -------------------------------------------

# 正当な前進（隣接1つ次）。
_FORWARD_STEPS = [
    (PbiStatus.NEW, PbiStatus.READY),
    (PbiStatus.READY, PbiStatus.IN_PROGRESS),
    (PbiStatus.IN_PROGRESS, PbiStatus.DONE),
]


@pytest.mark.parametrize(("current", "target"), _FORWARD_STEPS)
def test_forward_adjacent_transitions_are_valid(current: PbiStatus, target: PbiStatus) -> None:
    assert is_valid_transition(current, target) is True


@pytest.mark.parametrize("status", list(PbiStatus))
def test_same_status_is_valid(status: PbiStatus) -> None:
    # status を据え置く PATCH は冪等に許す（不正な「遷移」ではない）。
    assert is_valid_transition(status, status) is True


# 飛ばし（隣接でない前進）と逆流はすべて不正。
_INVALID_TRANSITIONS = [
    (PbiStatus.NEW, PbiStatus.IN_PROGRESS),
    (PbiStatus.NEW, PbiStatus.DONE),
    (PbiStatus.READY, PbiStatus.DONE),
    (PbiStatus.READY, PbiStatus.NEW),
    (PbiStatus.IN_PROGRESS, PbiStatus.READY),
    (PbiStatus.IN_PROGRESS, PbiStatus.NEW),
    (PbiStatus.DONE, PbiStatus.IN_PROGRESS),
    (PbiStatus.DONE, PbiStatus.NEW),
]


@pytest.mark.parametrize(("current", "target"), _INVALID_TRANSITIONS)
def test_skips_and_backward_transitions_are_invalid(current: PbiStatus, target: PbiStatus) -> None:
    assert is_valid_transition(current, target) is False


# --- ドメインフィールドの既定 ------------------------------------------------


def test_new_pbi_defaults() -> None:
    data = new_pbi_data(title="ログイン機能")
    assert data["status"] == "new"  # 始点は必ず new（図6）
    assert data["title"] == "ログイン機能"
    assert data["description"] == ""
    assert data["acceptanceCriteria"] == []
    assert data["estimate"] is None  # 任意・未設定（D-06）
    # 後続の PBI が所有するフィールドは null から始まる。
    assert data["rank"] is None  # 採番は B-16
    assert data["completedAt"] is None  # 刻印は B-25
    assert data["completedSprintId"] is None  # 刻印は B-25
    assert data["parentPbiId"] is None  # 分割は B-19


def test_new_pbi_keeps_provided_acceptance_criteria() -> None:
    ac = [{"id": "ac1", "text": "サインインできる", "checked": False}]
    data = new_pbi_data(title="X", acceptance_criteria=ac, estimate=13)
    assert data["acceptanceCriteria"] == ac
    assert data["estimate"] == 13


# --- 生成・参照（ポート契約） ------------------------------------------------


def test_create_pbi_stamps_common_fields(repo: InMemoryRepository) -> None:
    doc = create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title="ログイン機能")
    assert doc["id"].startswith("pbi_")  # 型接頭辞つき ULID
    assert doc["type"] == "pbi"
    assert doc["productId"] == PRODUCT
    assert doc["isDeleted"] is False
    assert doc["createdBy"] == ACTOR
    assert "_etag" in doc  # 楽観排他のための版
    # 実際に同じパーティションから引ける。
    assert get_pbi(repo, product_id=PRODUCT, pbi_id=doc["id"]) == doc


def test_get_pbi_excludes_deleted(repo: InMemoryRepository) -> None:
    doc = create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title="消す")
    repo.soft_delete(product_id=PRODUCT, doc_id=doc["id"], actor=ACTOR, if_match=doc["_etag"])
    # 論理削除済みは存在しない扱い（D-20：存在の有無を漏らさない）。
    assert get_pbi(repo, product_id=PRODUCT, pbi_id=doc["id"]) is None


def test_get_pbi_rejects_non_pbi_id(repo: InMemoryRepository) -> None:
    # 同じパーティションの別型（member）の id を渡しても PBI としては引かない。
    member = create_member(repo, product_id=PRODUCT, oid="oid-x", role=Role.MEMBER, actor=ACTOR)
    assert get_pbi(repo, product_id=PRODUCT, pbi_id=member["id"]) is None


def test_get_pbi_missing_is_none(repo: InMemoryRepository) -> None:
    assert get_pbi(repo, product_id=PRODUCT, pbi_id="pbi_missing") is None


# --- 作成時の rank 採番（B-16） ----------------------------------------------


def test_create_pbi_appends_rank_at_end(repo: InMemoryRepository) -> None:
    # 新規 PBI はバックログの末尾に採番される（後から作るほど rank が大きい）。
    first = create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title="1つめ")
    second = create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title="2つめ")
    third = create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title="3つめ")

    assert first["rank"] is not None
    assert first["rank"] < second["rank"] < third["rank"]


def test_create_pbi_rank_matches_query_order(repo: InMemoryRepository) -> None:
    # 作成順に採番されるので、既定の ORDER BY rank, id が作成順と一致する。
    titles = ["a", "b", "c", "d"]
    for title in titles:
        create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title=title)

    ordered = repo.query(product_id=PRODUCT, doc_type=DocumentType.PBI)
    assert [doc["title"] for doc in ordered] == titles


def test_last_rank_is_none_on_empty_partition(repo: InMemoryRepository) -> None:
    from app.data.pbis import last_rank

    assert last_rank(repo, PRODUCT) is None


# --- バックログ集約（B-17） --------------------------------------------------


def test_list_backlog_orders_by_rank(repo: InMemoryRepository) -> None:
    from app.data.pbis import list_backlog

    titles = ["a", "b", "c"]
    for title in titles:
        create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title=title)

    # 末尾採番なので作成順 = rank 順 = 優先順位順。並びの正はサーバー（D-20）。
    assert [doc["title"] for doc in list_backlog(repo, PRODUCT)] == titles


def test_list_backlog_excludes_deleted(repo: InMemoryRepository) -> None:
    from app.data.pbis import list_backlog

    kept = create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title="残す")
    dropped = create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title="消す")
    repo.soft_delete(
        product_id=PRODUCT, doc_id=dropped["id"], actor=ACTOR, if_match=dropped["_etag"]
    )

    assert [doc["id"] for doc in list_backlog(repo, PRODUCT)] == [kept["id"]]
