"""初回サインインのブートストラップと所属一覧（B-10・D-21）。

フェイク Repository の観測可能な振る舞いだけで、次を検証する:

* 初回サインインで user と **サンドボックスの member** が作られる（403 で詰まらない）
* 冪等（二度目は何もしない）／同時実行の 409 を握りつぶす
* 所属一覧が横断で集まり、表示名が解決され、productId 昇順で安定する
"""

from __future__ import annotations

import pytest

from app.auth.resolver import AuthenticatedUser
from app.data.documents import DocumentType
from app.data.fake import InMemoryRepository
from app.data.members import Role, create_member, get_member
from app.data.products import (
    SANDBOX_PRODUCT_ID,
    SCRUM_BOARD_PRODUCT_ID,
    create_product,
)
from app.data.users import create_user, get_user, user_id
from app.onboarding import ensure_bootstrapped, list_products

OID = "oid-newcomer"


def _user(oid: str = OID) -> AuthenticatedUser:
    return AuthenticatedUser(oid=oid, display_name="New Comer", email="new@example.com")


@pytest.fixture
def repo() -> InMemoryRepository:
    repository = InMemoryRepository()
    # 本番相当: マイグレーションが両プロダクトを作った状態から始める。
    create_product(repository, product_id=SANDBOX_PRODUCT_ID, name="サンドボックス", actor="sys")
    create_product(
        repository, product_id=SCRUM_BOARD_PRODUCT_ID, name="スクラムボード", actor="sys"
    )
    return repository


# --- ブートストラップ --------------------------------------------------------------


def test_first_sign_in_creates_user_and_sandbox_membership(repo: InMemoryRepository) -> None:
    ensure_bootstrapped(repo, _user())

    # user が _system に作られ、クレームが載る。
    stored_user = get_user(repo, OID)
    assert stored_user is not None
    assert stored_user["id"] == user_id(OID)
    assert stored_user["displayName"] == "New Comer"

    # サインインできた人には居場所がある（サンドボックスの member）。403 で詰まらない。
    member = get_member(repo, product_id=SANDBOX_PRODUCT_ID, oid=OID)
    assert member is not None
    assert member["role"] == "member"


def test_bootstrap_is_idempotent(repo: InMemoryRepository) -> None:
    # 毎 /api/me から呼べるよう、二度目以降は何も起こさず例外も出さない。
    ensure_bootstrapped(repo, _user())
    ensure_bootstrapped(repo, _user())

    users = repo.query_across_partitions(doc_type=DocumentType.USER)
    assert len([u for u in users if u["oid"] == OID]) == 1


def test_bootstrap_does_not_grant_production_membership(repo: InMemoryRepository) -> None:
    # 本番プロダクトへは自動で入れない（権限は緩めない — D-21）。
    ensure_bootstrapped(repo, _user())

    assert get_member(repo, product_id=SCRUM_BOARD_PRODUCT_ID, oid=OID) is None


def test_bootstrap_swallows_concurrent_conflict(repo: InMemoryRepository) -> None:
    # 別リクエストが先に user/member を作った状態でも 409 を握りつぶして続行する。
    ensure_bootstrapped(repo, _user())
    # 2回目は get が既存を見つけて create に到達しないが、created 済みでも例外ゼロを確認。
    ensure_bootstrapped(repo, _user())  # 例外が出ないこと自体がアサーション


class _AlwaysAbsentRepo(InMemoryRepository):
    """``get`` が常に「居ない」と答える Repository。

    同時サインインの真の競合を再現する: 別リクエストが既に作り終えているのに、
    こちらの get はまだ ``None`` を見る（TOCTOU）。``create`` は実際の store を見て
    重複を検出し 409 を投げる。id が決定的なので必ず衝突する（D-21）。
    """

    def get(self, product_id: str, doc_id: str):  # noqa: ANN201
        return None


def test_bootstrap_swallows_concurrent_creation_race() -> None:
    # get が「まだ居ない」と見えたのに create が 409 になる競合でも、握りつぶして
    # 続行する。握りつぶさなければ初回サインインが 500 で落ちる（D-21）。
    repo = _AlwaysAbsentRepo()
    # 先客がユーザーとサンドボックス member を作り終えている状態。
    create_user(repo, oid=OID, display_name="first", email=None, actor="race")
    create_member(repo, product_id=SANDBOX_PRODUCT_ID, oid=OID, role=Role.MEMBER, actor="race")

    # user・member の両方の create が 409 を投げるが、例外は外に漏れない。
    ensure_bootstrapped(repo, _user())


def test_existing_user_keeps_original_claims(repo: InMemoryRepository) -> None:
    # 既存 user は上書きしない（表示名の再取得はしない）。
    ensure_bootstrapped(repo, _user())
    ensure_bootstrapped(
        repo, AuthenticatedUser(oid=OID, display_name="Renamed", email="x@example.com")
    )

    assert get_user(repo, OID)["displayName"] == "New Comer"


# --- 所属一覧 ----------------------------------------------------------------------


def test_list_products_returns_sandbox_after_bootstrap(repo: InMemoryRepository) -> None:
    ensure_bootstrapped(repo, _user())

    products = list_products(repo, OID)

    assert len(products) == 1
    assert products[0].product_id == SANDBOX_PRODUCT_ID
    assert products[0].name == "サンドボックス"
    assert products[0].role is Role.MEMBER


def test_list_products_spans_multiple_products_sorted(repo: InMemoryRepository) -> None:
    ensure_bootstrapped(repo, _user())
    # スクリプト相当: 本番プロダクトへ admin として登録。
    create_member(
        repo, product_id=SCRUM_BOARD_PRODUCT_ID, oid=OID, role=Role.ADMIN, actor="sys"
    )

    products = list_products(repo, OID)

    # productId 昇順で安定（prd_sandbox < prd_scrum_board）。
    assert [(p.product_id, p.role) for p in products] == [
        (SANDBOX_PRODUCT_ID, Role.MEMBER),
        (SCRUM_BOARD_PRODUCT_ID, Role.ADMIN),
    ]


def test_list_products_empty_for_unknown_user(repo: InMemoryRepository) -> None:
    assert list_products(repo, "nobody") == []


def test_list_products_falls_back_to_id_when_name_missing() -> None:
    # product ドキュメントが無くても所属は所属。表示名は productId で代替し欠落させない。
    repo = InMemoryRepository()
    create_member(
        repo, product_id="prd_orphan", oid=OID, role=Role.MEMBER, actor="sys"
    )

    products = list_products(repo, OID)

    assert products[0].name == "prd_orphan"
