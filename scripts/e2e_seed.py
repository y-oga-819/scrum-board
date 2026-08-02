#!/usr/bin/env python3
"""E2E の既知の初期状態を作る（EX-1・D-22）。

E2E（D-19 の層4）は「テストのたびに初期状態を作り直す」前提（D-19）。エミュレータに
マイグレーションを全適用してから、**このランだけの隔離パーティション**
``prd_test_<runId>`` にプロダクトと E2E ユーザーの admin member を投入する。

    COSMOS_ENDPOINT=... COSMOS_KEY=... COSMOS_DATABASE=... COSMOS_TLS_VERIFY=0 \
        E2E_RUN_ID=<id> E2E_AUTH_OID=<oid> python scripts/e2e_seed.py

**隔離の要（D-21）**: fixtures は ``prd_test_`` で始まらない productId への投入を拒否する。
本番データ（``prd_sandbox`` / ``prd_scrum_board`` など）に E2E データを流し込む事故は、
一度起きると復旧できない。サンドボックスは人間の練習場であり E2E の置き場にしない。

teardown（物理削除）は :mod:`scripts.e2e_teardown` が担う。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ``app`` を import できるよう backend/ を sys.path に載せる（実行時の cwd に依存しない）。
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.data.members import Role, create_member, get_member  # noqa: E402
from app.data.migrations import run_migrations  # noqa: E402
from app.data.products import create_product, get_product  # noqa: E402
from app.data.repository import Repository  # noqa: E402

# E2E 隔離パーティションの接頭辞。これで始まらない productId への投入は拒否する（D-21）。
E2E_PARTITION_PREFIX = "prd_test_"
# 投入する E2E ユーザーの表示名（バックエンドの E2E_AUTH_NAME と揃えると自然）。
E2E_PRODUCT_NAME = "E2E テスト"
SEED_ACTOR = "system:e2e-seed"


class UnsafePartitionError(Exception):
    """``prd_test_`` 以外の productId に投入しようとした（本番への流し込みを型で塞ぐ）。"""


def product_id_for(run_id: str) -> str:
    """``runId`` からこのランの隔離パーティション id を作る。"""
    return f"{E2E_PARTITION_PREFIX}{run_id}"


def run(repo: Repository, *, product_id: str, oid: str) -> str:
    """マイグレーション適用 → ``prd_test_<runId>`` にプロダクトと admin member を作る。

    再実行可能: 既にプロダクトがあればマイグレーション・作成をスキップして member だけ
    整える（同一ランでの二重実行や再試行で落ちない）。何をしたかの1行サマリを返す。
    """
    if not product_id.startswith(E2E_PARTITION_PREFIX):
        raise UnsafePartitionError(
            f"E2E fixtures は '{E2E_PARTITION_PREFIX}' で始まる productId にしか投入しない"
            f"（受け取った値: '{product_id}'）。本番データへの流し込みを防ぐガードレール（D-21）。"
        )
    # D-21: エミュレータにマイグレーションを全適用してから fixtures を投入する。
    run_migrations(repo)
    if get_product(repo, product_id) is None:
        create_product(repo, product_id=product_id, name=E2E_PRODUCT_NAME, actor=SEED_ACTOR)
    if get_member(repo, product_id=product_id, oid=oid) is None:
        create_member(repo, product_id=product_id, oid=oid, role=Role.ADMIN, actor=SEED_ACTOR)
    return f"seeded: product={product_id} oid={oid} role=admin"


def _require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        print(f"{name} を設定してください。", file=sys.stderr)
        raise SystemExit(2)
    return value


def main() -> int:
    from app.data.settings import cosmos_settings_from_env, create_repository

    settings = cosmos_settings_from_env()
    if not settings.is_configured:
        print(
            "COSMOS_ENDPOINT / COSMOS_KEY / COSMOS_DATABASE を設定してください。",
            file=sys.stderr,
        )
        return 2

    run_id = _require_env("E2E_RUN_ID")
    oid = _require_env("E2E_AUTH_OID")

    repo = create_repository(settings)
    summary = run(repo, product_id=product_id_for(run_id), oid=oid)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
