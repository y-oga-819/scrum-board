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
    split_pbi,
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


# --- 分割（B-19） ------------------------------------------------------------


def test_split_sets_parent_reference(repo: InMemoryRepository) -> None:
    parent = create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title="大きな PBI")

    child = split_pbi(
        repo, product_id=PRODUCT, actor=ACTOR, parent_pbi_id=parent["id"], title="切り出し"
    )

    # 子は分割元を参照する（辿るための唯一の参照）。
    assert child["parentPbiId"] == parent["id"]
    # それ以外は通常の PBI（状態は new から・独立して並び替え／編集できる）。
    assert child["id"].startswith("pbi_")
    assert child["type"] == "pbi"
    assert child["status"] == "new"
    assert child["title"] == "切り出し"
    # 分割元は書き換えない（参照は子→親の一方向のみ）。
    reloaded_parent = get_pbi(repo, product_id=PRODUCT, pbi_id=parent["id"])
    assert reloaded_parent is not None
    assert reloaded_parent["parentPbiId"] is None


def test_split_appends_child_at_backlog_end(repo: InMemoryRepository) -> None:
    parent = create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title="親")
    other = create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title="別の PBI")

    child = split_pbi(repo, product_id=PRODUCT, actor=ACTOR, parent_pbi_id=parent["id"], title="子")

    # 末尾採番（create_pbi と同じ経路）。位置ではなく parentPbiId で辿らせる。
    assert child["rank"] > other["rank"] > parent["rank"]


def test_split_keeps_optional_fields(repo: InMemoryRepository) -> None:
    parent = create_pbi(repo, product_id=PRODUCT, actor=ACTOR, title="親")
    ac = [{"id": "ac1", "text": "満たす", "checked": False}]

    child = split_pbi(
        repo,
        product_id=PRODUCT,
        actor=ACTOR,
        parent_pbi_id=parent["id"],
        title="子",
        description="説明",
        acceptance_criteria=ac,
        estimate=5,
    )

    assert child["description"] == "説明"
    assert child["acceptanceCriteria"] == ac
    assert child["estimate"] == 5


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
