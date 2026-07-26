"""002 — 本番プロダクト（スクラムボード）を作成する（B-08・D-21）。

``prd_scrum_board`` はこのアプリ自身のバックログを管理する本番。**権限付与は
スクリプトで明示的に**行う（D-21）ため、ここでも ``member`` は作らない。
プロダクトの器だけを用意する。
"""

from __future__ import annotations

from ..products import SCRUM_BOARD_PRODUCT_ID, create_product
from ..repository import Repository
from .runner import Migration


def apply(repo: Repository, *, actor: str) -> None:
    create_product(
        repo,
        product_id=SCRUM_BOARD_PRODUCT_ID,
        name="スクラムボード",
        actor=actor,
    )


MIGRATION = Migration(
    version="002",
    description="本番プロダクト（prd_scrum_board）を作成する",
    apply=apply,
)
