"""注入可能な時計（D-19 の設計含意 #2）。

「今」を実装から切り出しておく。共通フィールドの ``createdAt`` / ``updatedAt``
（B-07）だけでなく、営業日マーカー（B-24）とスプリント期間・終了処理（B-25）は
**日付を固定できないとテストで検証できない**。後から入れると全面改修になるため、
データ層の最初（B-07）で織り込む。

本番は :class:`SystemClock`（UTC）。テストは固定時刻を返す実装を差し替える。
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

# 「今日」を数えるタイムゾーン（B-24 の営業日マーカー）。日本チームのスプリントを前提に
# **Asia/Tokyo 固定**とする（D-25）。``createdAt`` 等の保存は UTC（:func:`isoformat_utc`）の
# ままで、これは「暦日として今日はいつか」を決めるためだけに使う。
JST = ZoneInfo("Asia/Tokyo")


class Clock(Protocol):
    """現在時刻を返すポート。実装を差し替えてテストで時刻を固定する。"""

    def now(self) -> datetime:
        """タイムゾーン付き（aware）の現在時刻を返す。"""
        ...


class SystemClock:
    """本番実装。UTC の実時刻を返す。"""

    def now(self) -> datetime:
        return datetime.now(UTC)


def isoformat_utc(moment: datetime) -> str:
    """``2026-08-03T09:12:00Z`` 形式（UTC・末尾 Z）に整える。

    共通フィールドの ``createdAt`` / ``updatedAt`` はこの形で持つ（提案書 04章）。
    naive な時刻は UTC とみなす。
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def jst_date(moment: datetime) -> date:
    """``moment``（aware な時刻）を **Asia/Tokyo の暦日**に落とす（B-24・D-25）。

    :class:`SystemClock` は UTC を返すため、そのまま ``.date()`` を取ると日本時間の
    深夜〜朝（UTC では前日）で「今日」が1日ずれる。営業日マーカーは「日本のチームにとって
    今日が何日か」で数えるので、JST に変換してから日付にする。naive な時刻は UTC とみなす。
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(JST).date()
