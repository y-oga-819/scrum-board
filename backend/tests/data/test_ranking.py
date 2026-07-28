"""文字列ランク生成の単体テスト（並び替え B-16・提案書 06章）。

検証するのは**設計判断が実装に落ちたか**（提案書 12章）:

* 2 要素の間・末尾の後・先頭の前に、順序を保つキーを作れる。
* 同じ隙間へ連続挿入してもキーが伸びるだけで**壊れない**（順序が単調のまま）。
* 桁部は Base36（``0-9a-z``）に収まる。
* 前後関係が破れた入力は :class:`~app.data.errors.InvalidRankBoundsError`（422）。

``ORDER BY rank, id`` のうち **rank 部分がコードポイント順で正しく並ぶ**ことをここで固定
する。Cosmos が本当にコードポイント順で ``ORDER BY`` するか（Q-E）は実サービスでしか
確かめられないため、そちらは :mod:`scripts.verify_rank_ordering` に分ける（D-19）。
"""

from __future__ import annotations

import pytest

from app.data.errors import InvalidRankBoundsError
from app.data.ranking import (
    RANK_DIGITS,
    first_rank,
    rank_after,
    rank_before,
    rank_between,
)


def test_first_rank_is_stable() -> None:
    # 空の並びに置く最初のキー。両端 None は「要素が 1 つも無い」を表す。
    assert first_rank() == rank_between(None, None)
    # 桁部は Base36 に収まる（先頭の 'a' はヘッダ、'0' は桁部）。
    assert set(first_rank()) <= set(RANK_DIGITS) | set("abcdefghijklmnopqrstuvwxyz")


def test_between_is_strictly_ordered() -> None:
    a = first_rank()
    b = rank_after(a)
    mid = rank_between(a, b)
    # 序数比較で a < mid < b（Cosmos の ORDER BY もこの順を返すことが Q-E の前提）。
    assert a < mid < b


def test_rank_after_grows_monotonically() -> None:
    # 末尾へ 10 件追加すると単調増加する（末尾追加＝作成時の採番。B-16）。
    ranks: list[str] = []
    last: str | None = None
    for _ in range(10):
        last = rank_after(last)
        ranks.append(last)
    assert ranks == sorted(ranks)
    assert len(set(ranks)) == 10  # 重複しない


def test_repeated_insertion_into_same_gap_does_not_break() -> None:
    # 同じ隙間へ 50 回連続挿入しても順序が壊れない（浮動小数と違い精度が尽きない）。
    lo = first_rank()
    hi = rank_after(lo)
    inserted: list[str] = []
    for _ in range(50):
        # 常に lo と「現在の最小の後続」の間へ挿し続ける（同じ隙間を攻める）。
        mid = rank_between(lo, hi)
        assert lo < mid < hi
        inserted.append(mid)
        hi = mid
    # すべて lo と元の hi の間に収まり、降順に詰まっていく（単調）。
    assert inserted == sorted(inserted, reverse=True)


def test_rank_before_prepends() -> None:
    first = first_rank()
    before = rank_before(first)
    assert before < first


def test_invalid_bounds_raise_domain_error() -> None:
    a = first_rank()
    b = rank_after(a)
    # before >= after は順序が破れている。ライブラリの FIError をドメイン例外へ翻訳する。
    with pytest.raises(InvalidRankBoundsError):
        rank_between(b, a)
    with pytest.raises(InvalidRankBoundsError):
        rank_between(a, a)


def test_body_uses_base36_digits() -> None:
    # 桁部（先頭ヘッダを除く）は Base36 のみ。大文字が桁部に混ざらないことを固定する
    # （先頭ヘッダは a-z/A-Z を使い得る。ranking.py の警告参照）。
    a = first_rank()
    b = rank_after(a)
    mid = rank_between(a, b)
    body = mid[1:]  # 先頭 1 文字は整数長ヘッダ
    assert set(body) <= set(RANK_DIGITS)
