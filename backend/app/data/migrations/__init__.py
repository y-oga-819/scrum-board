"""マイグレーション一式（B-08・D-21）。

具体的なマイグレーションを **version 昇順**に束ねた :data:`MIGRATIONS` と、それを
適用するランナー（:func:`run_migrations`）を公開する。新しいマイグレーションは
``mNNN_*.py`` を追加し、その ``MIGRATION`` を下のタプルに **末尾へ**足す。
"""

from __future__ import annotations

from .m001_create_sandbox_product import MIGRATION as _M001
from .m002_create_scrum_board_product import MIGRATION as _M002
from .runner import MIGRATION_ACTOR, Migration, applied_versions, run_migrations

# 適用順（version 昇順）。ランナーは version でソートし直すが、宣言も順に並べる。
MIGRATIONS: tuple[Migration, ...] = (_M001, _M002)

__all__ = [
    "MIGRATIONS",
    "MIGRATION_ACTOR",
    "Migration",
    "applied_versions",
    "run_migrations",
]
