"""``scripts/e2e_seed.py`` / ``scripts/e2e_teardown.py`` の中核の検証（EX-1・D-22）。

Cosmos 接続と物理削除の消え方は実サービス／エミュレータの領分（層3の
``test_purge_partition``）。ここではフェイク Repository で **seeding の冪等性** と、
両スクリプトの **``prd_test_`` ガードレール**（本番パーティションへの投入・削除を拒否）
だけを確かめる。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from app.data.fake import InMemoryRepository
from app.data.members import get_member
from app.data.products import SANDBOX_PRODUCT_ID, get_product

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str):
    """scripts/<name>.py を独立モジュールとして読み込む（scripts はパッケージではない）。"""
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


e2e_seed = _load("e2e_seed")
e2e_teardown = _load("e2e_teardown")

RUN_ID = "abc123"
OID = "oid-e2e"


def test_seed_creates_isolated_product_and_admin_member() -> None:
    repo = InMemoryRepository()
    product_id = e2e_seed.product_id_for(RUN_ID)

    summary = e2e_seed.run(repo, product_id=product_id, oid=OID)

    assert product_id.startswith("prd_test_")
    assert get_product(repo, product_id) is not None
    member = get_member(repo, product_id=product_id, oid=OID)
    assert member is not None and member["role"] == "admin"
    assert OID in summary


def test_seed_is_rerunnable() -> None:
    repo = InMemoryRepository()
    product_id = e2e_seed.product_id_for(RUN_ID)

    e2e_seed.run(repo, product_id=product_id, oid=OID)
    # 二度目でも 409 で落ちず、同じ1件に収束する（同一ランの再試行に耐える）。
    e2e_seed.run(repo, product_id=product_id, oid=OID)

    assert get_member(repo, product_id=product_id, oid=OID) is not None


def test_seed_refuses_non_test_partition() -> None:
    repo = InMemoryRepository()
    # 本番・サンドボックスの productId には投入させない（D-21 のガードレール）。
    with pytest.raises(e2e_seed.UnsafePartitionError):
        e2e_seed.run(repo, product_id=SANDBOX_PRODUCT_ID, oid=OID)


def test_teardown_refuses_non_test_partition() -> None:
    # repo に触れる前にガードで弾く（本番パーティション削除を型で塞ぐ）。None でも到達しない。
    with pytest.raises(e2e_teardown.UnsafePartitionError):
        e2e_teardown.run(None, product_id=SANDBOX_PRODUCT_ID)  # type: ignore[arg-type]
