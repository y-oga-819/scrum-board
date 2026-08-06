"""進捗集計（2本バー＋営業日マーカー）の単体テスト（B-24・提案書 05章）。

``compute_progress`` は純関数で、「今日」を引数で受けるため日付を固定して検証できる
（D-19）。件数（``taskType`` 別の完了／総数）、営業日計算（土日＋日本の祝日を除外）、
マーカーの分子（経過営業日）の clamp、期間未設定時の ``None`` を確かめる。
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.data.clock import jst_date
from app.data.progress import (
    business_days_between,
    compute_progress,
    is_business_day,
)


def _task(task_type: str, status: str) -> dict:
    """集計に効くフィールドだけを持つタスク（``sprintId`` は集約 GET が既に絞っている）。"""
    return {"type": "task", "taskType": task_type, "status": status}


# --- 2本バーの件数（taskType 別の完了／総数） --------------------------------------


def test_counts_planned_and_team_separately_by_task_type() -> None:
    tasks = [
        _task("pbi", "done"),
        _task("pbi", "doing"),
        _task("pbi", "todo"),
        _task("team", "done"),
        _task("team", "done"),
        _task("team", "todo"),
    ]
    summary = compute_progress(tasks, start_date=None, end_date=None, today=date(2026, 8, 6))
    assert (summary.planned.done, summary.planned.total) == (1, 3)
    assert (summary.team.done, summary.team.total) == (2, 3)


def test_empty_sprint_has_zero_bars() -> None:
    summary = compute_progress([], start_date=None, end_date=None, today=date(2026, 8, 6))
    assert (summary.planned.done, summary.planned.total) == (0, 0)
    assert (summary.team.done, summary.team.total) == (0, 0)


# --- 営業日（土日＋日本の祝日を除外。D-25） --------------------------------------


def test_is_business_day_excludes_weekend_and_holiday() -> None:
    assert is_business_day(date(2026, 8, 6)) is True  # 木
    assert is_business_day(date(2026, 8, 8)) is False  # 土
    assert is_business_day(date(2026, 8, 9)) is False  # 日
    assert is_business_day(date(2026, 8, 11)) is False  # 山の日（祝日）


def test_business_days_between_is_inclusive_and_skips_nonbusiness() -> None:
    # 2026-08-10(月)〜08-14(金): 08-11(火)が山の日で除外 → 月・水・木・金 = 4 営業日。
    assert business_days_between(date(2026, 8, 10), date(2026, 8, 14)) == 4


def test_business_days_between_returns_zero_when_end_before_start() -> None:
    assert business_days_between(date(2026, 8, 14), date(2026, 8, 10)) == 0


# --- マーカー（経過営業日 ÷ 総営業日）の clamp ------------------------------------

# 2026-08-03(月)〜08-14(金)の2週間スプリント。08-11(火)が山の日で祝日。
# 営業日: 3,4,5,6,7,10,12,13,14 → 総 9 営業日。
_START = "2026-08-03"
_END = "2026-08-14"


def _marker(today: date) -> tuple[int | None, int | None]:
    summary = compute_progress([], start_date=_START, end_date=_END, today=today)
    return summary.elapsed_business_days, summary.total_business_days


def test_marker_total_counts_business_days_only() -> None:
    assert _marker(date(2026, 8, 14)) == (9, 9)


def test_marker_zero_before_sprint_starts() -> None:
    assert _marker(date(2026, 8, 1)) == (0, 9)


def test_marker_counts_elapsed_business_days_inclusive_of_today() -> None:
    # 08-06(木)時点: 3,4,5,6 の 4 営業日が経過（今日を含む）。
    assert _marker(date(2026, 8, 6)) == (4, 9)


def test_marker_skips_holiday_between_start_and_today() -> None:
    # 08-12(水)時点: 3,4,5,6,7,10,12 = 7（08-11 の祝日は数えない）。
    assert _marker(date(2026, 8, 12)) == (7, 9)


def test_marker_clamps_to_total_after_sprint_ends() -> None:
    assert _marker(date(2026, 8, 20)) == (9, 9)


# --- 期間未設定ならマーカーを描かない（None） ------------------------------------


def test_no_business_days_when_period_missing() -> None:
    assert _marker_none(start=None, end=_END)
    assert _marker_none(start=_START, end=None)
    assert _marker_none(start=None, end=None)


def test_no_business_days_when_period_inverted() -> None:
    # 終了 < 開始（B-21 は作成時に弾くが、集計側も安全側に倒す）。
    assert _marker_none(start=_END, end=_START)


def test_no_business_days_when_date_is_malformed() -> None:
    # 不正な日付文字列は解釈できない → マーカーを描かない（例外で落とさない）。
    assert _marker_none(start="not-a-date", end=_END)
    assert _marker_none(start=_START, end="2026-13-40")


def _marker_none(*, start: object, end: object) -> bool:
    summary = compute_progress([], start_date=start, end_date=end, today=date(2026, 8, 6))
    return summary.elapsed_business_days is None and summary.total_business_days is None


# --- 「今日」は JST の暦日（UTC 深夜のずれを吸収。D-25） --------------------------


def test_jst_date_rolls_over_before_utc_midnight() -> None:
    # 2026-08-06 16:00Z = 2026-08-07 01:00 JST → 日本では既に 8/7。
    assert jst_date(datetime(2026, 8, 6, 16, 0, tzinfo=UTC)) == date(2026, 8, 7)
    # 2026-08-06 14:59Z = 2026-08-06 23:59 JST → まだ 8/6。
    assert jst_date(datetime(2026, 8, 6, 14, 59, tzinfo=UTC)) == date(2026, 8, 6)
