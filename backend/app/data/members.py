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

# member 以外の更新経路と同じ actor 規約。スクリプトによる登録は人ではなく手続き。
SCRIPT_ACTOR = "system:add-member"


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


def memberships_for_user(repo: Repository, oid: str) -> list[Document]:
    """``oid`` が属するすべてのプロダクトの ``member`` を横断で集める（B-10）。

    member は所属先の productId パーティションに散らばるため、**クロスパーティション
    クエリ**でしか集められない。``GET /api/me`` の所属一覧に使う（セッション開始時に
    一度きり・小件数）。認可の点判定にはこれを使わない — それは ``mbr_<oid>`` の
    ポイントリードで済ませる（D-21）。
    """
    return repo.query_across_partitions(doc_type=DocumentType.MEMBER, equals={"userId": oid})


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


def upsert_member(
    repo: Repository,
    *,
    product_id: str,
    oid: str,
    role: Role,
    actor: str = SCRIPT_ACTOR,
) -> Document:
    """``mbr_<oid>`` を作る。既にあれば role を更新する（**再実行可能** — D-21）。

    本番プロジェクトへの登録スクリプト（``scripts/add_member.py``）が使う。メンバーの
    増加で必ず再実行されるため、二度目以降は既存を role 更新で上書きし、role が同じ
    なら何もしない（無駄な etag 回転を避ける）。更新は楽観排他つき（``if_match``）で、
    同時実行が黙って消えない（D-20）。
    """
    existing = get_member(repo, product_id=product_id, oid=oid)
    if existing is None:
        return create_member(repo, product_id=product_id, oid=oid, role=role, actor=actor)
    if existing["role"] == role.value:
        return existing
    return repo.replace(
        product_id=product_id,
        doc_id=existing["id"],
        changes={"role": role.value},
        actor=actor,
        if_match=existing["_etag"],
    )
