"""ドキュメント ID の生成（ULID）と型ごとの接頭辞。

提案書 04章の共通フィールドは ``"id": "pbi_01JXYZ..."`` の形をとる。すなわち
**``<型の接頭辞>_<ULID>``**。ULID は時系列にソート可能で、``ORDER BY rank, id`` の
タイブレーカー（提案書 06章・D-18）として使える。

一部の型は ID が **決定的**であり ULID を使わない（``usr_<oid>`` / ``mbr_<oid>`` /
``mig_001`` / ``prd_sandbox`` など。D-21）。それらは呼び出し側が明示 ID を渡すため、
ここでは ULID 由来の ID を作る :func:`new_id` と、接頭辞の対応表だけを持つ。

ULID は外部依存を増やさないよう自前で実装する（Crockford Base32・128bit =
48bit ミリ秒 + 80bit 乱数、26 文字）。
"""

from __future__ import annotations

import os
import time

from .documents import DocumentType

# Crockford Base32（I/L/O/U を除く 32 文字）。ULID の標準アルファベット。
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

_TIME_CHARS = 10  # 48bit ミリ秒
_RANDOM_CHARS = 16  # 80bit 乱数
ULID_LENGTH = _TIME_CHARS + _RANDOM_CHARS  # 26

# 型 → ID 接頭辞。ID を見ただけで型が分かるようにする（デバッグ・ログで効く）。
_PREFIXES: dict[DocumentType, str] = {
    DocumentType.PRODUCT: "prd",
    DocumentType.PBI: "pbi",
    DocumentType.TASK: "tsk",
    DocumentType.SPRINT: "spr",
    DocumentType.DAILY_NOTE: "dly",
    DocumentType.RETRO_ACTION: "rta",
    DocumentType.MEMBER: "mbr",
    DocumentType.USER: "usr",
    DocumentType.MIGRATION: "mig",
}


def prefix_for(doc_type: DocumentType) -> str:
    """型に対応する ID 接頭辞（``pbi`` など）。"""
    return _PREFIXES[doc_type]


def _encode(value: int, length: int) -> str:
    """``value`` を Crockford Base32 の ``length`` 文字に符号化する（ビッグエンディアン）。"""
    out = ["0"] * length
    for i in range(length - 1, -1, -1):
        out[i] = _CROCKFORD[value & 0x1F]
        value >>= 5
    return "".join(out)


def generate_ulid(now_ms: int | None = None) -> str:
    """26 文字の ULID を生成する。

    ``now_ms`` を渡せば時刻部分を固定できる（テスト用）。乱数部分は常にランダム。
    """
    if now_ms is None:
        now_ms = time.time_ns() // 1_000_000
    time_part = _encode(now_ms & ((1 << 48) - 1), _TIME_CHARS)
    random_part = _encode(int.from_bytes(os.urandom(10), "big"), _RANDOM_CHARS)
    return time_part + random_part


def new_id(doc_type: DocumentType, *, now_ms: int | None = None) -> str:
    """``<接頭辞>_<ULID>`` 形式の新しい ID を作る。"""
    return f"{prefix_for(doc_type)}_{generate_ulid(now_ms=now_ms)}"
