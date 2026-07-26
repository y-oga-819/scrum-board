"""メンバーシップによる認可（B-09・D-21）。

認証（:mod:`app.auth`：あなたは誰か）とは軸が違う。ここは **あなたがこのプロダクトを
触ってよいか** を、``member`` のポイントリード1件（``mbr_<oid>``。D-21）で判定する。

product スコープのエンドポイント（``/api/products/{product_id}/…``。D-20）は
:func:`require_member` に依存するだけで、非メンバーを 403 で弾ける。判定を各ハンドラに
撒かない（``if not member:`` を書き散らさない — D-21「分岐ではなく差し替え／依存で表現」）。

``current_user`` が 401（未認証・トークン不正）を先に処理し、ここは「認証は済んでいるが
このプロダクトの member ではない」を 403 に振り分ける。RFC 9457 形式への整形は B-12。
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from .auth import AuthenticatedUser, current_user
from .data import Repository
from .data.members import Role, get_member


@dataclass(frozen=True)
class Membership:
    """認可を通過したユーザーの、そのプロダクトでの立場。

    ``role`` を載せておくことで、管理操作だけを絞る将来のチェック（B-33 の共同管理者）が
    メンバーの再取得なしに書ける。
    """

    product_id: str
    oid: str
    role: Role


def get_repository(request: Request) -> Repository:
    """lifespan が ``app.state`` に置いたリポジトリを取り出す（:mod:`app.main`）。

    Cosmos 未構成（DB 無しで起動した M1 相当）なら 503。認可はデータ層を要するため、
    リポジトリが無ければ判定そのものが成立しない。テストは ``dependency_overrides`` か
    ``app.state.repository`` の差し替えでフェイクを注入する。
    """
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    return repository


def require_member(
    product_id: str,
    user: AuthenticatedUser = Depends(current_user),
    repository: Repository = Depends(get_repository),
) -> Membership:
    """``product_id`` のメンバーであることを要求する依存。非メンバーは 403（D-20）。

    ``product_id`` はパス（``/api/products/{product_id}/…``）から解決される。存在しない／
    論理削除済みの member は :func:`~app.data.members.get_member` が ``None`` を返し、
    ここで 403 になる（存在の有無を漏らさない D-20 と整合）。
    """
    member = get_member(repository, product_id=product_id, oid=user.oid)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this product",
        )
    return Membership(
        product_id=product_id,
        oid=user.oid,
        role=Role(member["role"]),
    )
