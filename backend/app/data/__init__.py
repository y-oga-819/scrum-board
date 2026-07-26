"""データアクセス基盤（B-07）。

単一コンテナ（PK ``/productId``）への読み書きを **Repository ポート**として抽象化し、
テスト用フェイクと本番 Cosmos を差し替えられるようにする（D-19）。共通フィールド付与・
論理削除の除外・``_etag`` 楽観排他を一元化して、呼び出し側が忘れられない形にする。
"""

from __future__ import annotations

from .clock import Clock, SystemClock
from .documents import SYSTEM_PARTITION, Document, DocumentType
from .errors import (
    ConflictError,
    DataError,
    NotFoundError,
    PreconditionFailedError,
    PreconditionRequiredError,
)
from .fake import InMemoryRepository
from .ids import new_id
from .repository import DEFAULT_ORDER, Repository

__all__ = [
    "DEFAULT_ORDER",
    "SYSTEM_PARTITION",
    "Clock",
    "ConflictError",
    "DataError",
    "Document",
    "DocumentType",
    "InMemoryRepository",
    "NotFoundError",
    "PreconditionFailedError",
    "PreconditionRequiredError",
    "Repository",
    "SystemClock",
    "new_id",
]
