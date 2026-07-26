"""ドキュメントの型と共通フィールド付与（B-07）。

単一コンテナ／PK ``/productId`` に全エンティティを同居させる（提案書 04章・D-08）。
どのエンティティも **共通フィールド**を持つ:

    {
      "id": "pbi_01JXYZ...",   # ULID（型接頭辞付き。ids.py）
      "type": "pbi",           # DocumentType
      "productId": "prd_001",  # ← パーティションキー
      "isDeleted": false,      # 論理削除（D-07）
      "createdAt": "...", "createdBy": "<entra oid>",
      "updatedAt": "...", "updatedBy": "<entra oid>"
    }

付与を **1 箇所**（:func:`stamp_new` / :func:`stamp_update`）に集約し、フェイクと
Cosmos の両実装がこれを呼ぶ。実装ごとに共通フィールドの作り方がずれると、
「フェイクでは通るが本番で欠ける」という D-19 が最も警戒する形になる。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from .clock import Clock, isoformat_utc

# ``user`` / ``migration`` を置く予約パーティション（D-21）。productId として払い出さない。
SYSTEM_PARTITION = "_system"

# ドキュメント本体（Cosmos アイテムは JSON オブジェクト）。エンティティ別の
# Pydantic モデルは各 CRUD（B-15 / B-20 …）で被せる。データ層は汎用の dict を扱う。
Document = dict[str, Any]


class DocumentType(StrEnum):
    """``type`` フィールドの値（提案書 04章）。"""

    PRODUCT = "product"
    PBI = "pbi"
    TASK = "task"
    SPRINT = "sprint"
    DAILY_NOTE = "dailyNote"
    RETRO_ACTION = "retroAction"
    MEMBER = "member"
    USER = "user"
    MIGRATION = "migration"


def stamp_new(
    data: Document,
    *,
    doc_type: DocumentType,
    product_id: str,
    doc_id: str,
    actor: str,
    clock: Clock,
) -> Document:
    """新規作成時の共通フィールドを付与した **新しい dict** を返す。

    ``data`` は破壊しない（呼び出し側の値を汚さない）。``id`` / ``type`` /
    ``productId`` / ``isDeleted`` / ``createdAt`` / ``createdBy`` /
    ``updatedAt`` / ``updatedBy`` を上書きで確定させる。
    ``_etag`` はストア（Cosmos／フェイク）が採番するため、ここでは触らない。
    """
    now = isoformat_utc(clock.now())
    stamped = dict(data)
    stamped.update(
        {
            "id": doc_id,
            "type": doc_type.value,
            "productId": product_id,
            "isDeleted": False,
            "createdAt": now,
            "createdBy": actor,
            "updatedAt": now,
            "updatedBy": actor,
        }
    )
    return stamped


# 作成時に確定し、更新で書き換えてはならない不変フィールド。
_IMMUTABLE_ON_UPDATE = ("id", "type", "productId", "createdAt", "createdBy")


def stamp_update(
    current: Document,
    changes: Document,
    *,
    actor: str,
    clock: Clock,
) -> Document:
    """既存ドキュメントに ``changes`` を反映し、更新メタを付与した新しい dict を返す。

    不変フィールド（``id`` / ``type`` / ``productId`` / ``createdAt`` /
    ``createdBy``）は ``changes`` に入っていても無視して現行値を保つ。
    ``updatedAt`` / ``updatedBy`` を今の時刻・操作者で更新する。論理削除の
    切り替えは呼び出し側が ``changes`` に ``isDeleted`` を含めて行う。
    """
    merged = dict(current)
    for key, value in changes.items():
        if key in _IMMUTABLE_ON_UPDATE or key == "_etag":
            continue
        merged[key] = value
    merged["updatedAt"] = isoformat_utc(clock.now())
    merged["updatedBy"] = actor
    return merged
