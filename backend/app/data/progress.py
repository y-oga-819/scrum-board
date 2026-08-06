"""進捗の集計（2本バー＋営業日マーカー。B-24・提案書 05章）。

デイリースクラムで「このペースで計画通り終わるか」を判断するための計器。提案書 05章は
**性質の異なる2つの問いを2本のバーに分ける**:

* **計画タスク**（``taskType='pbi'``）— Q1「計画通り終わりそうか」。時間との対比が要る。
* **チームタスク**（``taskType='team'``）— Q2「計画外に食われていないか」。構成比。

マーカー位置は **経過営業日 ÷ 総営業日**（暦日で数えると週末に必ず遅れて見えるため営業日で
数える）。営業日は土日に加えて**日本の祝日も除外**する（D-25。祝日は :mod:`jpholiday` に委ねる
——春分／秋分・ハッピーマンデー・振替休日・国民の休日を自前で誤ると1日静かにずれる）。

ここは **純関数**に閉じる（データ層は HTTP を知らない）。「今日」は引数で受け取り
（:func:`compute_progress` の ``today``）、固定してテストできる（D-19 の設計含意 #2・
:mod:`app.data.clock`）。件数は集約 GET が既に引いたスプリントのタスク列から数えるだけで、
追加のクエリを撃たない（``GET /board`` の N+1 を作らない — B-23）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import jpholiday

from .documents import Document
from .tasks import TaskStatus, TaskType


@dataclass(frozen=True)
class Bar:
    """1本のバーの分子・分母（完了 ``done`` / 総数 ``total``）。

    「当初件数」という基準値は持たない（提案書 05章）。判断に要るのは2本の長さの対比と
    マーカーとの位置関係で、基準値がなくても成立する。分母が増えて達成率が下がるのは
    解像度が上がった健全な進行であり、異常ではない。
    """

    done: int
    total: int


@dataclass(frozen=True)
class ProgressSummary:
    """スプリントの進捗集計（2本バー＋営業日マーカーの分子分母）。

    ``elapsed_business_days`` / ``total_business_days`` は期間（``startDate`` /
    ``endDate``）が両方そろって初めて数えられる。片方でも未設定なら **``None``**——
    マーカーを描かない（ありもしない位置をでっち上げない — P-1）。
    """

    planned: Bar
    team: Bar
    elapsed_business_days: int | None
    total_business_days: int | None


def _bar_for(tasks: list[Document], task_type: TaskType) -> Bar:
    """``task_type`` のタスクの完了／総数を数える。

    入力はあるスプリントに属するタスク（``sprintId`` は集約 GET が既に一致で絞っている）。
    種別の判定は ``pbiId`` の有無ではなく **``taskType``**（I-4 と同じ規律）。完了は
    ``status='done'``。
    """
    total = 0
    done = 0
    for task in tasks:
        if task.get("taskType") != task_type.value:
            continue
        total += 1
        if task.get("status") == TaskStatus.DONE.value:
            done += 1
    return Bar(done=done, total=total)


def is_business_day(day: date) -> bool:
    """``day`` が営業日（平日かつ日本の祝日でない）なら ``True``（D-25）。

    週末（土日）と日本の祝日を除く。祝日判定は :mod:`jpholiday`（振替休日・国民の休日を含む）。
    """
    if day.weekday() >= 5:  # 5=土, 6=日
        return False
    return not jpholiday.is_holiday(day)


def business_days_between(start: date, end: date) -> int:
    """``start`` から ``end`` までの営業日数（**両端を含む**）。``end < start`` なら 0。"""
    if end < start:
        return 0
    day = start
    count = 0
    while day <= end:
        if is_business_day(day):
            count += 1
        day += timedelta(days=1)
    return count


def _parse_iso_date(value: object) -> date | None:
    """``"2026-08-06"`` 形式の ISO 日付を :class:`date` に。空・型不一致・不正は ``None``。"""
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def compute_progress(
    tasks: list[Document],
    *,
    start_date: object,
    end_date: object,
    today: date,
) -> ProgressSummary:
    """スプリントのタスク列と期間・今日から進捗集計を作る（純関数。B-24）。

    ``tasks`` はそのスプリントに属するタスク（``GET /board`` が引いたもの）。``start_date`` /
    ``end_date`` はスプリントの ISO 日付（未設定なら ``None`` 相当）。``today`` は「今日」の
    暦日（JST。:func:`~app.data.clock.jst_date`）。

    マーカーの分子（経過営業日）は ``start`` から ``min(today, end)`` までの営業日数で、
    ``today < start`` なら 0、``today >= end`` なら総営業日数に張り付く（区間 [0, total] に
    収める）。期間が未設定なら営業日は ``None``（マーカーは描かない）。
    """
    planned = _bar_for(tasks, TaskType.PBI)
    team = _bar_for(tasks, TaskType.TEAM)

    start = _parse_iso_date(start_date)
    end = _parse_iso_date(end_date)
    if start is None or end is None or end < start:
        return ProgressSummary(
            planned=planned,
            team=team,
            elapsed_business_days=None,
            total_business_days=None,
        )

    total = business_days_between(start, end)
    if today < start:
        elapsed = 0
    elif today >= end:
        elapsed = total
    else:
        elapsed = business_days_between(start, today)
    return ProgressSummary(
        planned=planned,
        team=team,
        elapsed_business_days=elapsed,
        total_business_days=total,
    )
