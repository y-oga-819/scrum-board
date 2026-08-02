"""初回サインインのブートストラップと所属一覧（B-10・D-21）。

認可（:mod:`app.authz`）は「メンバーでなければ 403」を素直に課す。それだけだと
**最初のメンバーが存在しない状態を抜けられない**（鶏卵問題）。D-21 はこれを、権限を
緩めずに解く: **サインインした全員が自動で入れる練習場（サンドボックス）を一枚挟む。**

初回サインインのフロー（D-21）:

    ① トークン検証（V-1〜V-4）        → oid を得る（:mod:`app.auth`）
    ② _system で usr_<oid> をポイントリード
    ③ 無ければ user を作成           ← displayName / email はトークンのクレーム
    ④ 同時に prd_sandbox へ mbr_<oid> を role=member で作成
    ⑤ GET /api/me が user と所属プロダクト一覧を返す

これで「サインインできた人には必ず居場所がある」＝ **403 で詰まる経路が無い**。
本番プロダクト（``prd_scrum_board``）への登録は緩めず、``scripts/add_member.py`` で
明示的に行う。

**競合の扱い**: ③④は同時サインインで衝突しうるが、id が oid から決定的なので、
重複作成の 409（:class:`~app.data.errors.ConflictError`）は握りつぶして続行する
（create-if-absent と等価。後勝ちでも同じものが1件できるだけで害がない）。
"""

from __future__ import annotations

from dataclasses import dataclass

from .auth import AuthenticatedUser
from .data import ConflictError, Repository
from .data.members import Role, create_member, get_member, memberships_for_user
from .data.products import SANDBOX_PRODUCT_ID, get_product
from .data.users import create_user, get_user


@dataclass(frozen=True)
class ProductMembership:
    """所属一覧の1要素（``GET /api/me`` の ``products``）。"""

    product_id: str
    name: str
    role: Role


def ensure_bootstrapped(
    repo: Repository,
    user: AuthenticatedUser,
    *,
    skip_sandbox: bool = False,
) -> None:
    """初回サインインなら user を作り、サンドボックスの member を与える（冪等）。

    既に居れば何もしない。作成が同時実行で衝突しても 409 を握りつぶすため、
    **何度呼んでも安全**（毎回の ``/api/me`` から呼べる）。

    ``skip_sandbox`` は E2E 用（D-22）。E2E ユーザーを ``prd_test_<runId>`` の member
    **だけ**にして ``/api/me`` の ``products`` を 1 件に絞り、バックログが確実にその
    プロダクトを選ぶようにする（サンドボックスが混ざると先頭に来て隔離が崩れる）。
    """
    _ensure_user(repo, user)
    if not skip_sandbox:
        _ensure_sandbox_membership(repo, user.oid)


def _ensure_user(repo: Repository, user: AuthenticatedUser) -> None:
    if get_user(repo, user.oid) is not None:
        return
    try:
        create_user(
            repo,
            oid=user.oid,
            display_name=user.display_name,
            email=user.email,
            actor=user.oid,
        )
    except ConflictError:
        # 同時実行で他リクエストが先に作った。id は oid から決定的なので同じ user が
        # 1件あるだけ。create-if-absent と等価（D-21）。
        pass


def _ensure_sandbox_membership(repo: Repository, oid: str) -> None:
    if get_member(repo, product_id=SANDBOX_PRODUCT_ID, oid=oid) is not None:
        return
    try:
        create_member(
            repo,
            product_id=SANDBOX_PRODUCT_ID,
            oid=oid,
            role=Role.MEMBER,
            actor=oid,
        )
    except ConflictError:
        pass


def list_products(repo: Repository, oid: str) -> list[ProductMembership]:
    """``oid`` が属するプロダクトを ``(productId, name, role)`` で返す（B-10）。

    member を横断で集め（:func:`~app.data.members.memberships_for_user`）、各プロダクト
    の表示名をポイントリードで解決する。productId 昇順で安定させる（フロントの
    セレクタ表示を決定的にする。並びの正はサーバー — D-20）。
    """
    memberships = memberships_for_user(repo, oid)
    products: list[ProductMembership] = []
    for membership in memberships:
        product_id = membership["productId"]
        product = get_product(repo, product_id)
        # product ドキュメントが未作成（マイグレーション未適用など）でも所属は所属。
        # 表示名が引けなければ productId をそのまま名前に使い、一覧から欠落させない。
        name = product["name"] if product is not None else product_id
        products.append(
            ProductMembership(
                product_id=product_id,
                name=name,
                role=Role(membership["role"]),
            )
        )
    products.sort(key=lambda p: p.product_id)
    return products
