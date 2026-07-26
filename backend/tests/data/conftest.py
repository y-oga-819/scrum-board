"""データ層テストの共通フィクスチャ。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.data.clock import Clock
from app.data.fake import InMemoryRepository


class FixedClock:
    """固定時刻を返すテスト用時計（D-19：時刻を固定して検証する）。"""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def set(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(datetime(2026, 8, 3, 9, 12, 0, tzinfo=UTC))


@pytest.fixture
def repo(clock: Clock) -> InMemoryRepository:
    """契約テスト対象の Repository。

    層3（B-11）で同じ契約を ``CosmosRepository`` にも通せるよう、テストは
    このフィクスチャ越しにポートだけを触る（実装の内部に触れない）。
    """
    return InMemoryRepository(clock=clock)
