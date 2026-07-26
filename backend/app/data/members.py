"""メンバーと認可の土台（B-09・D-21）。

``member`` は「ある user が、あるプロダクトに、ある role で属している」ことを表す。
パーティションは所属先の ``productId``、id は **``mbr_<oid>``**（決定的）。

``id = mbr_<oid>`` にすることの意味（D-21）:

* 認可チェック（「あなたはこのプロダクトのメンバーか」）が **ポイントリード1件**で済む。
  すべての product スコープの API が毎リクエスト通る最頻出の処理を、最も安い操作
  （約1 RU）にする。クロスパーティションクエリを撒かない。
* ``oid`` をキーにする（提案書08章「メールアドレスは変わり得るのでキーにしない」）。

ここが持つのは member の生成・参照と、``member`` ドキュメントの ID 規約だけ。
「メンバーでなければ 403」という認可の判断そのものは :mod:`app.authz` が担う
（データ層は HTTP を知らない）。初回サインインでの自動作成（サンドボックスへの
member 付与）と本番プロジェクトへの明示登録スクリプトは B-10 で足す（D-21）。
"""

from __future__ import annotations

from enum import StrEnum

from .documents import Document, DocumentType
from .ids import prefix_for
from .repository import Repository


class Role(StrEnum):
    """member の役割（D-21：2種のみ）。

    * ``admin`` — メンバー管理ができる
    * ``member`` — それ以外すべて

    スクラム上の役割（PO / SM / Developer）は持たない。アプリの振る舞いが変わらない
    ためメタデータに過ぎず、必要になれば後から足せる（P-3）。共同管理者（B-33）も
    ``admin`` を複数人に付けるだけで表現し、新しい role を作らない（D-21）。
    """

    ADMIN = "admin"
    MEMBER = "member"


def member_id(oid: str) -> str:
    """``oid`` から決定的な member の id（``mbr_<oid>``）を導く。

    ポイントリード可能にするための鍵（D-21）。接頭辞は :mod:`app.data.ids` の
    対応表から引き、ID 規約を一元化する。
    """
    return f"{prefix_for(DocumentType.MEMBER)}_{oid}"


def get_member(repo: Repository, *, product_id: str, oid: str) -> Document | None:
    """``product_id`` パーティションから ``mbr_<oid>`` をポイントリードする。

    メンバーでなければ（論理削除済みを含む）``None``。認可判定の中核であり、
    毎リクエスト・1件のポイントリードで済む（D-21）。
    """
    return repo.get(product_id, member_id(oid))


def is_member(repo: Repository, *, product_id: str, oid: str) -> bool:
    """``oid`` が ``product_id`` のメンバーなら ``True``。"""
    return get_member(repo, product_id=product_id, oid=oid) is not None


def create_member(
    repo: Repository,
    *,
    product_id: str,
    oid: str,
    role: Role,
    actor: str,
) -> Document:
    """``mbr_<oid>`` を1件作成する（``userId == oid``）。

    id が ``oid`` から決定的に決まるため、二重作成は
    :class:`~app.data.errors.ConflictError`（409）。初回サインインの同時実行で起きる
    この 409 は B-10 側で握りつぶす（create-if-absent と等価。D-21）。
    """
    return repo.create(
        product_id=product_id,
        doc_type=DocumentType.MEMBER,
        data={"userId": oid, "role": role.value},
        actor=actor,
        doc_id=member_id(oid),
    )
