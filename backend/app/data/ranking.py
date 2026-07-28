"""文字列ランクの生成（並び替え B-16・提案書 06章）。

並び順は要素間の**相対的な関係**なのに、ドキュメント DB は各要素を独立に保存する。
相対情報を絶対値（1 つの文字列フィールド ``rank``）に落とし、``ORDER BY rank, id`` で
全端末が同じ並びになるようにする。方式は**文字列ランク（fractional indexing）**:
2 要素の間に新しいキーを作れ、1 件の移動で**更新は 1 ドキュメントだけ**で済む。
整数 order（後続全件更新）や浮動小数（同じ隙間への連続挿入で精度が尽きる）と違い、
同じ隙間へ何度挿しても**キーが 1 文字ずつ伸びるだけで壊れない**（提案書 06章の表）。

生成は :mod:`fractional_indexing` に委ねる。境界条件（先頭・末尾・キー枯渇）を自前で
誤ると順序が静かに壊れ、しかも「並び替えたのに戻る」という報告からしか気づけない
（提案書 06章）。ここはその薄いラッパで、**採用した設計判断だけ**を固定する:

* **文字集合は Base36**（``0-9a-z``）。桁部から大文字を外し、``Z`` と ``a`` の比較順という
  不確実性を減らす（提案書 06章）。ただし後述の**先頭挿入**では例外がある。
* **タイブレーカーは id**。2 人が同じ位置へ同時挿入すると文字列ランクでも同一キーが
  生まれるため、並びの最終確定は ``ORDER BY rank, id``（ULID の id）に委ねる。ここでは
  キー生成だけを担い、同一キーの発生自体は許容する。

.. warning::

   fractional-indexing は桁部（body）に ``digits`` を使うが、整数部の**長さヘッダ**
   （先頭 1 文字）は ``digits`` と無関係に ``a-z``／``A-Z`` を用いる。したがって
   **末尾より後ろ**（``rank_after``）ではヘッダが ``a→b→…`` と伸び、**先頭より前**
   （``rank_before``）ではヘッダが ``a→Z→Y→…`` と**大文字へ**降りる。つまり実際に
   保存され得る ``rank`` の文字集合は、先頭 1 文字に限り ``0-9A-Za-z`` を含む。
   序数（コードポイント）比較では ``0-9 < A-Z < a-z`` の順で常に正しく整列するが、
   これは **Cosmos の ``ORDER BY`` が序数比較であること**に依存する。Base36 が消すはず
   だった「大文字小文字の比較順」の不確実性を、このライブラリは先頭ヘッダで一部残す。
   ゆえに B-16 冒頭の**実サービスでの照合順序検証（Q-E）は必須**で、その検証は
   大文字ヘッダを含むランクも対象にする（:mod:`scripts.verify_rank_ordering`）。
"""

from __future__ import annotations

from fractional_indexing import FIError, generate_key_between

from .errors import InvalidRankBoundsError

# Base36（``0-9a-z``）。昇順のコードポイント順に並んでいることがライブラリの前提
# （``digits must be in ascending character code order``）。桁部に大文字を混ぜない。
RANK_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def rank_between(before: str | None, after: str | None) -> str:
    """``before`` と ``after`` の**間**に入る新しいランクを返す。

    ``before`` は直前（1 つ上・rank が小さい方）の要素のランク、``after`` は直後
    （1 つ下・rank が大きい方）の要素のランク。端は ``None`` で表す（先頭挿入は
    ``before=None``、末尾挿入は ``after=None``、要素が 1 つも無ければ両方 ``None``）。

    ``before >= after`` のように順序が破れている入力は
    :class:`~app.data.errors.InvalidRankBoundsError`（422）にする。ライブラリの
    :class:`~fractional_indexing.FIError` をドメイン例外へ翻訳し、データ層が
    fractional-indexing の存在を外へ漏らさないようにする。
    """
    try:
        return generate_key_between(before, after, RANK_DIGITS)
    except FIError as exc:
        raise InvalidRankBoundsError(
            f"ランクの前後関係が不正です（before={before!r}, after={after!r}）"
        ) from exc


def first_rank() -> str:
    """要素が 1 つも無いところに置く最初のランク（``rank_between(None, None)``）。"""
    return rank_between(None, None)


def rank_after(last: str | None) -> str:
    """末尾（``last`` の後ろ）に追加するランク。``last=None`` なら :func:`first_rank`。"""
    return rank_between(last, None)


def rank_before(first: str | None) -> str:
    """先頭（``first`` の前）に追加するランク。``first=None`` なら :func:`first_rank`。"""
    return rank_between(None, first)
