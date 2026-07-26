"""本番の Repository 実装（Azure Cosmos DB）。

:class:`~app.data.repository.Repository` ポートを実 Cosmos で満たす。フェイク
（:mod:`.fake`）と **観測可能な振る舞いを揃える**のが狙いで、契約テスト（層3・
B-11）がエミュレータ上で同じ期待を検証する。ここでしか確かめられないのは
``_etag`` / ``If-Match`` / 412（同時更新の検出はサーバー側の挙動）とインデックス
除外パスの RU 削減であり、それが層3の存在理由（D-19）。

共通フィールドの付与（:func:`.documents.stamp_new` / ``stamp_update``）と論理削除の
除外はフェイクと同じ関数・同じ SQL 生成を通す。実装ごとにずれない。

同期 SDK を使う（ポートが同期。:mod:`.repository` の方針）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from azure.core import MatchConditions
from azure.cosmos import ContainerProxy, exceptions

from .clock import Clock, SystemClock
from .documents import Document, DocumentType, stamp_new, stamp_update
from .errors import ConflictError, NotFoundError, PreconditionFailedError
from .ids import new_id
from .repository import DEFAULT_ORDER


class CosmosRepository:
    """単一コンテナ（PK ``/productId``）に対する Repository 実装。"""

    def __init__(self, container: ContainerProxy, clock: Clock | None = None) -> None:
        self._container = container
        self._clock: Clock = clock or SystemClock()

    def create(
        self,
        *,
        product_id: str,
        doc_type: DocumentType,
        data: Document,
        actor: str,
        doc_id: str | None = None,
    ) -> Document:
        resolved_id = doc_id if doc_id is not None else new_id(doc_type)
        body = stamp_new(
            data,
            doc_type=doc_type,
            product_id=product_id,
            doc_id=resolved_id,
            actor=actor,
            clock=self._clock,
        )
        try:
            return dict(self._container.create_item(body=body))
        except exceptions.CosmosResourceExistsError as exc:
            raise ConflictError(
                f"document already exists: {product_id}/{resolved_id}",
            ) from exc

    def get(self, product_id: str, doc_id: str) -> Document | None:
        try:
            found = dict(self._container.read_item(item=doc_id, partition_key=product_id))
        except exceptions.CosmosResourceNotFoundError:
            return None
        if found.get("isDeleted"):
            # 論理削除済みは「存在しない」と同じ扱い（D-20）。
            return None
        return found

    def query(
        self,
        *,
        product_id: str,
        doc_type: DocumentType,
        equals: Mapping[str, object] | None = None,
        order_by: Sequence[str] = DEFAULT_ORDER,
    ) -> list[Document]:
        sql, params = _build_query(doc_type, equals or {}, order_by)
        items = self._container.query_items(
            query=sql,
            parameters=params,
            partition_key=product_id,
        )
        return [dict(item) for item in items]

    def query_across_partitions(
        self,
        *,
        doc_type: DocumentType,
        equals: Mapping[str, object] | None = None,
    ) -> list[Document]:
        # partition_key を渡さない＝全パーティション横断（SDK が自動でファンアウトする）。
        # RU が高くスケールしないため、呼び出しは限定する（ポート docstring・D-21）。
        # 横断ソートは高価なので ORDER BY は付けない（並びは呼び出し側で決める）。
        sql, params = _build_query(doc_type, equals or {}, order_by=())
        items = self._container.query_items(query=sql, parameters=params)
        return [dict(item) for item in items]

    def replace(
        self,
        *,
        product_id: str,
        doc_id: str,
        changes: Document,
        actor: str,
        if_match: str,
    ) -> Document:
        return self._conditional_write(
            product_id=product_id,
            doc_id=doc_id,
            changes=changes,
            actor=actor,
            if_match=if_match,
        )

    def soft_delete(
        self,
        *,
        product_id: str,
        doc_id: str,
        actor: str,
        if_match: str,
    ) -> None:
        self._conditional_write(
            product_id=product_id,
            doc_id=doc_id,
            changes={"isDeleted": True},
            actor=actor,
            if_match=if_match,
        )

    def _conditional_write(
        self,
        *,
        product_id: str,
        doc_id: str,
        changes: Document,
        actor: str,
        if_match: str,
    ) -> Document:
        """現行を読み、``changes`` を反映し、``If-Match`` 付きで置換する。

        ``if_match`` は **呼び出し側が持つ etag** を使う（読み直した etag ではない）。
        呼び出し側の読み取りから今までの間に他者が更新していれば 412 になる。
        """
        try:
            current = dict(self._container.read_item(item=doc_id, partition_key=product_id))
        except exceptions.CosmosResourceNotFoundError as exc:
            raise NotFoundError(f"document not found: {product_id}/{doc_id}") from exc
        if current.get("isDeleted"):
            raise NotFoundError(f"document not found: {product_id}/{doc_id}")
        updated = stamp_update(current, changes, actor=actor, clock=self._clock)
        try:
            return dict(
                self._container.replace_item(
                    item=doc_id,
                    body=updated,
                    etag=if_match,
                    match_condition=MatchConditions.IfNotModified,
                )
            )
        except exceptions.CosmosAccessConditionFailedError as exc:
            raise PreconditionFailedError(
                f"etag mismatch for {product_id}/{doc_id}",
            ) from exc


def _build_query(
    doc_type: DocumentType,
    equals: Mapping[str, object],
    order_by: Sequence[str],
) -> tuple[str, list[dict[str, object]]]:
    """``NOT isDeleted`` を必ず含むパラメータ化クエリを組み立てる。

    等値条件の値 ``None`` は ``IS_NULL(c.field)`` に変換する（提案書の ``sprintId=null``
    などに対応。フィールド未定義でも一致する）。フィールド名はコード内の定数由来で
    ユーザー入力ではないが、値は必ずパラメータに載せる。
    """
    conditions = ["c.type = @type", "NOT c.isDeleted"]
    params: list[dict[str, object]] = [{"name": "@type", "value": doc_type.value}]
    for index, (field, value) in enumerate(equals.items()):
        if value is None:
            conditions.append(f"IS_NULL(c.{field})")
            continue
        name = f"@p{index}"
        conditions.append(f"c.{field} = {name}")
        params.append({"name": name, "value": value})
    sql = f"SELECT * FROM c WHERE {' AND '.join(conditions)}"
    if order_by:
        sql += " ORDER BY " + ", ".join(f"c.{field}" for field in order_by)
    return sql, params
