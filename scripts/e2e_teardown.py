#!/usr/bin/env python3
"""E2E の隔離パーティションを物理削除して後片付けする（EX-1・D-22）。

seeding（:mod:`scripts.e2e_seed`）が作った ``prd_test_<runId>`` を**物理削除**する。
論理削除（``isDeleted``）はアプリの復旧価値のための機構であり、テストの後片付けとは
目的が違う（D-21）。ここでは実ドキュメントを消してパーティションを空にする。

    COSMOS_ENDPOINT=... COSMOS_KEY=... COSMOS_DATABASE=... COSMOS_TLS_VERIFY=0 \
        E2E_RUN_ID=<id> python scripts/e2e_teardown.py

**ガードレール（D-21）**: ``prd_test_`` で始まらない productId は削除しない。teardown が
本番パーティションを消す事故を型で塞ぐ。CI ではエミュレータ自体が使い捨てなので保険だが、
共有エミュレータや誤設定に対する最後の砦として seeding と同じ関門を通す。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ``app`` を import できるよう backend/ を sys.path に載せる（実行時の cwd に依存しない）。
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.data.cosmos import CosmosRepository  # noqa: E402

# seeding（e2e_seed.py）と同じ接頭辞・ガードを**あえて再掲**する（D-21）。teardown 単独でも
# 「prd_test_ 以外は消さない」関門が閉じているべきで、他スクリプトの import に依存させない。
E2E_PARTITION_PREFIX = "prd_test_"


class UnsafePartitionError(Exception):
    """``prd_test_`` 以外の productId を消そうとした（本番パーティション削除を型で塞ぐ）。"""


def product_id_for(run_id: str) -> str:
    """``runId`` からこのランの隔離パーティション id を作る（seeding と同じ規約）。"""
    return f"{E2E_PARTITION_PREFIX}{run_id}"


def run(repo: CosmosRepository, *, product_id: str) -> str:
    """``prd_test_<runId>`` パーティションを物理削除し、消した件数のサマリを返す。"""
    if not product_id.startswith(E2E_PARTITION_PREFIX):
        raise UnsafePartitionError(
            f"teardown は '{E2E_PARTITION_PREFIX}' で始まる productId しか消さない"
            f"（受け取った値: '{product_id}'）。本番パーティション削除を防ぐガードレール（D-21）。"
        )
    removed = repo.purge_partition(product_id)
    return f"purged: product={product_id} removed={removed}"


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
    repo = create_repository(settings)
    summary = run(repo, product_id=product_id_for(run_id))
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
