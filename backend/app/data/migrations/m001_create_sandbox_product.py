"""001 — サンドボックスプロダクトを作成する（B-08・D-21）。

``prd_sandbox`` は**サインインした全員が自動で ``member`` になる練習場**（B-10）。
ここではプロダクトそのものだけを作る。``member`` は作らない（D-21）。
"""

from __future__ import annotations

from ..products import SANDBOX_PRODUCT_ID, create_product
from ..repository import Repository
from .runner import Migration


def apply(repo: Repository, *, actor: str) -> None:
    create_product(
        repo,
        product_id=SANDBOX_PRODUCT_ID,
        name="サンドボックス",
        actor=actor,
    )


MIGRATION = Migration(
    version="001",
    description="サンドボックスプロダクト（prd_sandbox）を作成する",
    apply=apply,
)
