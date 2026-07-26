"""ULID 生成と型接頭辞のテスト。"""

from __future__ import annotations

from app.data.documents import DocumentType
from app.data.ids import ULID_LENGTH, generate_ulid, new_id, prefix_for

_CROCKFORD = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")


def test_ulid_has_fixed_length_and_crockford_alphabet() -> None:
    ulid = generate_ulid()
    assert len(ulid) == ULID_LENGTH == 26
    assert set(ulid) <= _CROCKFORD


def test_ulids_are_unique() -> None:
    ulids = {generate_ulid() for _ in range(1000)}
    assert len(ulids) == 1000


def test_ulid_is_time_sortable() -> None:
    earlier = generate_ulid(now_ms=1)
    later = generate_ulid(now_ms=2)
    # 時刻部分（先頭10文字）が単調に増えるため、文字列比較で時系列になる。
    assert earlier[:10] < later[:10]


def test_new_id_carries_type_prefix() -> None:
    doc_id = new_id(DocumentType.PBI)
    assert doc_id.startswith("pbi_")
    assert len(doc_id) == len("pbi_") + ULID_LENGTH


def test_every_type_has_a_prefix() -> None:
    # 全型に接頭辞がある（KeyError を出さない）。
    prefixes = {prefix_for(t) for t in DocumentType}
    assert len(prefixes) == len(list(DocumentType))
