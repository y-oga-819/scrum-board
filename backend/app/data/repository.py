"""Repository ポート（B-07・D-19 の設計含意 #1）。

**Repository を抽象化し、テスト用フェイクに差し替えられる**ことがテスト戦略の要。
これが無いと層1・2まで Cosmos を要求し、CI が分単位になる（D-19）。同一のポートに
:class:`~app.data.fake.InMemoryRepository`（層1・2）と
:class:`~app.data.cosmos.CosmosRepository`（本番・層3）が乗る。

ポートが構造的に保証すること（＝呼び出し側が忘れられないこと）:

* **共通フィールドの付与** — ``create`` / ``replace`` が :mod:`.documents` で一元的に打つ。
* **論理削除の除外** — ``get`` / ``query`` は常に ``NOT isDeleted`` を掛ける。削除済みを
  読む経路を API として提供しない（``includeDeleted`` のようなパラメータを作らない。D-20）。
* **楽観排他** — ``replace`` / ``soft_delete`` は ``if_match`` を **必須引数**にし、
  無条件更新の経路を型で塞ぐ（D-20：欠落は 428・不一致は 412）。

同期 API にしている（``async`` にしない）。単一チーム・低トラフィックで、Cosmos の
同期 SDK と噛み合い、``aiohttp`` を持ち込まずに済む。DB を触る FastAPI ハンドラは
``def`` で書き、スレッドプールに逃がす（B-15 以降）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from .documents import Document, DocumentType

# ``ORDER BY rank, id``（提案書 06章）。並びはサーバーが保証する（D-20）。
DEFAULT_ORDER: tuple[str, ...] = ("rank", "id")


class Repository(Protocol):
    """単一コンテナ（PK ``/productId``）への読み書きポート。

    ``product_id`` は全メソッドで明示する。パーティションキーであり認可の単位
    （B-09）でもあるため、暗黙解決にしない（D-20）。
    """

    def create(
        self,
        *,
        product_id: str,
        doc_type: DocumentType,
        data: Document,
        actor: str,
        doc_id: str | None = None,
    ) -> Document:
        """共通フィールドを付与して1件作成し、``_etag`` 付きの保存結果を返す。

        ``doc_id`` を渡さなければ ``<接頭辞>_<ULID>`` を採番する。決定的 ID を持つ型
        （``usr_<oid>`` など。D-21）は ``doc_id`` を明示する。id 重複は
        :class:`~app.data.errors.ConflictError`（409）。
        """
        ...

    def get(self, product_id: str, doc_id: str) -> Document | None:
        """ポイントリード。存在し **かつ未削除**なら返す。無ければ ``None``。

        論理削除済みは ``None`` 扱い（存在の有無を漏らさない。D-20）。
        """
        ...

    def query(
        self,
        *,
        product_id: str,
        doc_type: DocumentType,
        equals: Mapping[str, object] | None = None,
        order_by: Sequence[str] = DEFAULT_ORDER,
    ) -> list[Document]:
        """パーティション内を型で絞って取得する。常に ``NOT isDeleted`` を掛ける。

        ``equals`` は各フィールドの等値条件（値 ``None`` は「その項目が null」を意味する。
        提案書のクエリ例 ``sprintId=null`` 等）。``order_by`` は既定で ``rank, id``。
        """
        ...

    def query_across_partitions(
        self,
        *,
        doc_type: DocumentType,
        equals: Mapping[str, object] | None = None,
    ) -> list[Document]:
        """**全パーティションを横断**して型で絞る（クロスパーティションクエリ）。

        ``get`` / ``query`` と違いパーティションキーを取らない。RU コストが高く、
        パーティション数に比例してスケールしないため、**使ってよい場面を限る**:
        「ユーザーの所属プロダクト一覧」（B-10 の ``GET /api/me``）のように、
        **セッション開始時に一度きり・件数が小さいと分かっている**横断だけ。
        毎リクエスト通る認可判定はこれを使わずポイントリードで済ませる（D-21）。

        ``NOT isDeleted`` は常に掛かる（``query`` と同じ）。横断ソートは高価なので
        ``order_by`` は取らない。並びが要る呼び出し側が受け取ってから決める。
        """
        ...

    def replace(
        self,
        *,
        product_id: str,
        doc_id: str,
        changes: Document,
        actor: str,
        if_match: str,
    ) -> Document:
        """楽観排他つき更新。``if_match`` が現行 ``_etag`` と一致したときだけ書く。

        不一致は :class:`~app.data.errors.PreconditionFailedError`（412）、対象が
        無ければ（削除済み含む）:class:`~app.data.errors.NotFoundError`（404）。
        ``changes`` の不変フィールドは無視される（:func:`.documents.stamp_update`）。
        """
        ...

    def soft_delete(
        self,
        *,
        product_id: str,
        doc_id: str,
        actor: str,
        if_match: str,
    ) -> None:
        """論理削除（``isDeleted=True``）。楽観排他は ``replace`` と同じ契約。

        物理削除はしない（誤操作の復旧価値。D-07）。以後 ``get`` / ``query`` からは
        見えなくなる。
        """
        ...
