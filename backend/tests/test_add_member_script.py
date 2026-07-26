"""``scripts/add_member.py`` の中核（``run`` / ``parse_args``）の検証（B-10・D-21）。

Cosmos 接続（``main`` の環境変数まわり）は実サービス／エミュレータの領分。ここでは
フェイク Repository で **再実行可能性**（既存なら role 更新）と **プロダクト存在チェック**
だけを確かめる。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from app.data.fake import InMemoryRepository
from app.data.members import Role, get_member
from app.data.products import SCRUM_BOARD_PRODUCT_ID, create_product

# scripts/add_member.py をモジュールとして読み込む（scripts はパッケージではない）。
_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "add_member.py"
_spec = importlib.util.spec_from_file_location("add_member", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
add_member = importlib.util.module_from_spec(_spec)
sys.modules["add_member"] = add_member
_spec.loader.exec_module(add_member)

OID = "oid-teammate"


@pytest.fixture
def repo() -> InMemoryRepository:
    repository = InMemoryRepository()
    create_product(
        repository, product_id=SCRUM_BOARD_PRODUCT_ID, name="スクラムボード", actor="sys"
    )
    return repository


def test_run_registers_new_member(repo: InMemoryRepository) -> None:
    summary = add_member.run(
        repo, product_id=SCRUM_BOARD_PRODUCT_ID, oid=OID, role=Role.ADMIN
    )

    member = get_member(repo, product_id=SCRUM_BOARD_PRODUCT_ID, oid=OID)
    assert member is not None
    assert member["role"] == "admin"
    assert "role=admin" in summary


def test_run_is_rerunnable_and_updates_role(repo: InMemoryRepository) -> None:
    # 1回目 member、2回目 admin。再実行で昇格できる（D-21）。
    add_member.run(repo, product_id=SCRUM_BOARD_PRODUCT_ID, oid=OID, role=Role.MEMBER)
    add_member.run(repo, product_id=SCRUM_BOARD_PRODUCT_ID, oid=OID, role=Role.ADMIN)

    member = get_member(repo, product_id=SCRUM_BOARD_PRODUCT_ID, oid=OID)
    assert member is not None
    assert member["role"] == "admin"


def test_run_rejects_unknown_product(repo: InMemoryRepository) -> None:
    # typo で無関係な productId のメンバーを作らせない。
    with pytest.raises(add_member.ProductNotFoundError):
        add_member.run(repo, product_id="prd_typo", oid=OID, role=Role.MEMBER)


def test_parse_args_defaults_role_to_member() -> None:
    args = add_member.parse_args(["--product", SCRUM_BOARD_PRODUCT_ID, "--oid", OID])
    assert args.role == "member"


def test_parse_args_rejects_unknown_role() -> None:
    # role は admin / member の2種のみ（D-21）。それ以外は argparse が弾く。
    with pytest.raises(SystemExit):
        add_member.parse_args(
            ["--product", SCRUM_BOARD_PRODUCT_ID, "--oid", OID, "--role", "owner"]
        )
