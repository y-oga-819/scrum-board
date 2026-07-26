"""プロダクトの生成と予約 productId（B-08・D-21）。

``product`` ドキュメントは**自分自身のパーティションの根**である。すなわち
``id == productId``（例: ``prd_sandbox`` の product は パーティション ``prd_sandbox``
に id ``prd_sandbox`` で置く）。単一コンテナ／PK ``/productId`` の設計上、これで
「そのプロダクトのデータはすべて同じパーティションに集まる」が成り立つ（提案書 06章）。

``_system`` は ``user`` / ``migration`` を置く**予約パーティション**であり、
**productId として払い出してはならない**（提案書 04章の予約語・D-21）。ここに
その規則を一元化し、マイグレーション（B-08）と将来のプロジェクト作成（B-32）が
同じ関門を通るようにする。``if reserved:`` の判定を各所に散らさない。
"""

from __future__ import annotations

from .documents import SYSTEM_PARTITION, Document, DocumentType
from .errors import ReservedProductIdError
from .repository import Repository

# マイグレーションが作る2つのプロダクト（D-21）。B-10 のブートストラップ
# （サンドボックスへ自動アサイン）と本番登録スクリプトがこの ID を参照する。
SANDBOX_PRODUCT_ID = "prd_sandbox"
SCRUM_BOARD_PRODUCT_ID = "prd_scrum_board"

# productId として払い出さない予約語。いまは ``_system`` のみ（D-21）。
RESERVED_PRODUCT_IDS: frozenset[str] = frozenset({SYSTEM_PARTITION})


def is_reserved_product_id(product_id: str) -> bool:
    """``product_id`` が予約語（払い出し禁止）なら ``True``。"""
    return product_id in RESERVED_PRODUCT_IDS


def get_product(repo: Repository, product_id: str) -> Document | None:
    """``product`` ドキュメントをポイントリードする（``id == productId``）。

    論理削除済み・未作成なら ``None``。所属一覧の表示名解決（B-10 の ``/api/me``）で
    使う。``id == productId`` の規約をここに閉じ、呼び出し側に漏らさない。
    """
    return repo.get(product_id, product_id)


def create_product(
    repo: Repository,
    *,
    product_id: str,
    name: str,
    actor: str,
) -> Document:
    """``product`` ドキュメントを1件作成する（``id == productId``）。

    予約語（``_system`` など）を productId に使おうとしたら
    :class:`~app.data.errors.ReservedProductIdError`（422）で弾く。id 重複は
    ポート契約どおり :class:`~app.data.errors.ConflictError`（409）。
    """
    if is_reserved_product_id(product_id):
        raise ReservedProductIdError(
            f"'{product_id}' は予約語のため productId に使えない",
        )
    return repo.create(
        product_id=product_id,
        doc_type=DocumentType.PRODUCT,
        data={"name": name},
        actor=actor,
        doc_id=product_id,
    )
