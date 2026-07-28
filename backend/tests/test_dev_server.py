"""``scripts/dev_server.py`` の開発ハーネスの検証。

開発機なので網羅はしない（CRUD の網羅は ``tests/api/test_pbis.py``）。ここが守るのは
**ハーネス自身が腐らないこと**——本番の部品で組めていて、フェイク DB とスタブ認証で
member 済みユーザーとして API が通る、という前提が壊れていないことだけを確かめる。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.data.members import get_member
from app.data.products import SANDBOX_PRODUCT_ID, SCRUM_BOARD_PRODUCT_ID, get_product

# scripts/dev_server.py をモジュールとして読み込む（scripts はパッケージではない）。
_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dev_server.py"
_spec = importlib.util.spec_from_file_location("dev_server", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
dev_server = importlib.util.module_from_spec(_spec)
sys.modules["dev_server"] = dev_server
_spec.loader.exec_module(dev_server)


def test_build_repository_is_migrated_with_admin_member() -> None:
    repo = dev_server.build_repository()
    # 本番と同じプロダクトがマイグレーションで揃う。
    assert get_product(repo, SANDBOX_PRODUCT_ID) is not None
    assert get_product(repo, SCRUM_BOARD_PRODUCT_ID) is not None
    # 開発ユーザーは両プロダクトの admin。
    for product_id in (SANDBOX_PRODUCT_ID, SCRUM_BOARD_PRODUCT_ID):
        member = get_member(repo, product_id=product_id, oid=dev_server.DEV_OID)
        assert member is not None
        assert member["role"] == "admin"


@pytest.fixture
def client() -> TestClient:
    return TestClient(dev_server.build_app())


def test_pbi_crud_works_without_signin(client: TestClient) -> None:
    # スタブ認証で member 済みユーザーとして扱われ、作成→取得が通る。
    created = client.post(f"/api/products/{SANDBOX_PRODUCT_ID}/pbis", json={"title": "ためし"})
    assert created.status_code == 201
    pbi = created.json()
    assert pbi["status"] == "new"
    assert pbi["createdBy"] == dev_server.DEV_OID

    got = client.get(f"/api/products/{SANDBOX_PRODUCT_ID}/pbis/{pbi['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == pbi["id"]


def test_me_returns_dev_user_with_memberships(client: TestClient) -> None:
    res = client.get("/api/me")
    assert res.status_code == 200
    body = res.json()
    assert body["oid"] == dev_server.DEV_OID
    product_ids = {p["productId"] for p in body["products"]}
    assert {SANDBOX_PRODUCT_ID, SCRUM_BOARD_PRODUCT_ID} <= product_ids
