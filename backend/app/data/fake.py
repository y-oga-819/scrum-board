"""インメモリのフェイク Repository（層1・2用。D-19）。

Cosmos なしで層1・2を回すための差し替え実装。ポートの契約
（共通フィールド付与・``NOT isDeleted`` 除外・``_etag`` 楽観排他）を
**本番と同じ観測可能な振る舞い**で再現する。同じ契約テストがフェイクと
Cosmos の双方に通ることを狙う（Cosmos 側は層3・B-11）。

``_etag`` は Cosmos の挙動（更新のたびに変わる不透明な文字列）を模して、
書き込みごとに新しい UUID を採番する。値そのものに意味はなく、
「一致すれば通す／しなければ 412」という関係だけを再現する。
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy

from .clock import Clock, SystemClock
from .documents import Document, DocumentType, stamp_new, stamp_update
from .errors import ConflictError, NotFoundError, PreconditionFailedError
from .ids import new_id
from .repository import DEFAULT_ORDER


class InMemoryRepository:
    """辞書ベースの Repository。プロセス内・非永続。テスト専用。"""

    def __init__(self, clock: Clock | None = None) -> None:
        self._clock: Clock = clock or SystemClock()
        # (productId, id) -> ドキュメント（_etag 込み）。外に出すときは必ず複製する。
        self._store: dict[tuple[str, str], Document] = {}

    def _new_etag(self) -> str:
        return f'"{uuid.uuid4().hex}"'

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
        key = (product_id, resolved_id)
        if key in self._store:
            raise ConflictError(f"document already exists: {product_id}/{resolved_id}")
        stored = stamp_new(
            data,
            doc_type=doc_type,
            product_id=product_id,
            doc_id=resolved_id,
            actor=actor,
            clock=self._clock,
        )
        stored["_etag"] = self._new_etag()
        self._store[key] = stored
        return deepcopy(stored)

    def get(self, product_id: str, doc_id: str) -> Document | None:
        found = self._store.get((product_id, doc_id))
        if found is None or found.get("isDeleted"):
            return None
        return deepcopy(found)

    def query(
        self,
        *,
        product_id: str,
        doc_type: DocumentType,
        equals: Mapping[str, object] | None = None,
        order_by: Sequence[str] = DEFAULT_ORDER,
    ) -> list[Document]:
        equals = equals or {}
        results: list[Document] = []
        for (pid, _), doc in self._store.items():
            if pid != product_id:
                continue
            if doc.get("isDeleted"):
                continue
            if doc.get("type") != doc_type.value:
                continue
            if all(doc.get(field) == value for field, value in equals.items()):
                results.append(deepcopy(doc))
        # order_by のフィールドで昇順ソート。同 rank は id をタイブレーカーにする
        # （提案書 06章 ``ORDER BY rank, id``）。並びの正はサーバー保証（D-20）。
        fields = list(order_by)

        def sort_key(doc: Document) -> tuple[object, ...]:
            # 各フィールドを (None か, 値) の2要素に開く。None を常に先に寄せ、
            # 同型の値どうしだけを比較する。
            key: list[object] = []
            for field in fields:
                value = doc.get(field)
                key.append(value is None)
                key.append(value)
            return tuple(key)

        results.sort(key=sort_key)
        return results

    def _load_for_write(self, product_id: str, doc_id: str, if_match: str) -> Document:
        current = self._store.get((product_id, doc_id))
        if current is None or current.get("isDeleted"):
            # 削除済みは「存在しない」と同じ扱い（D-20）。
            raise NotFoundError(f"document not found: {product_id}/{doc_id}")
        if current.get("_etag") != if_match:
            raise PreconditionFailedError(
                f"etag mismatch for {product_id}/{doc_id}",
            )
        return current

    def replace(
        self,
        *,
        product_id: str,
        doc_id: str,
        changes: Document,
        actor: str,
        if_match: str,
    ) -> Document:
        current = self._load_for_write(product_id, doc_id, if_match)
        updated = stamp_update(current, changes, actor=actor, clock=self._clock)
        updated["_etag"] = self._new_etag()
        self._store[(product_id, doc_id)] = updated
        return deepcopy(updated)

    def soft_delete(
        self,
        *,
        product_id: str,
        doc_id: str,
        actor: str,
        if_match: str,
    ) -> None:
        current = self._load_for_write(product_id, doc_id, if_match)
        updated = stamp_update(current, {"isDeleted": True}, actor=actor, clock=self._clock)
        updated["_etag"] = self._new_etag()
        self._store[(product_id, doc_id)] = updated
