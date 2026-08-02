"""env ゲートの E2E 認証バイパス（D-22）。

**既定 OFF・fail-closed** を固定する。E2E は実サーバで回り ``dependency_overrides``
を使えないため、``E2E_AUTH_BYPASS=1`` かつ ``E2E_AUTH_OID`` のときだけ固定ユーザーの
resolver に差し替わる。旗の付け忘れ・oid 欠落では本番挙動（Entra）に落ちること。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.auth import e2e_bypass_from_env
from app.auth.dependencies import get_current_user_resolver
from app.auth.resolver import EntraCurrentUserResolver, FixedUserResolver
from app.data.fake import InMemoryRepository
from app.data.members import Role, create_member
from app.data.products import SANDBOX_PRODUCT_ID, create_product
from app.main import app


@pytest.fixture(autouse=True)
def _clear_bypass_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """各テストを既知の未設定状態から始める。"""
    for name in ("E2E_AUTH_BYPASS", "E2E_AUTH_OID", "E2E_AUTH_NAME"):
        monkeypatch.delenv(name, raising=False)


def test_default_is_entra_resolver() -> None:
    # env 未設定なら本番挙動（Entra 実装）。バイパスは fail-closed で効かない。
    assert isinstance(get_current_user_resolver(), EntraCurrentUserResolver)
    assert e2e_bypass_from_env().is_active is False


def test_flag_without_oid_stays_entra(monkeypatch: pytest.MonkeyPatch) -> None:
    # 旗だけ立てて oid が無ければ有効化しない（誤設定で全員同一ユーザーになる事故を防ぐ）。
    monkeypatch.setenv("E2E_AUTH_BYPASS", "1")
    assert e2e_bypass_from_env().is_active is False
    assert isinstance(get_current_user_resolver(), EntraCurrentUserResolver)


def test_oid_without_flag_stays_entra(monkeypatch: pytest.MonkeyPatch) -> None:
    # oid だけあって旗が無ければ有効化しない。
    monkeypatch.setenv("E2E_AUTH_OID", "oid-e2e")
    assert e2e_bypass_from_env().is_active is False
    assert isinstance(get_current_user_resolver(), EntraCurrentUserResolver)


def test_active_bypass_returns_fixed_user(monkeypatch: pytest.MonkeyPatch) -> None:
    # 旗 + oid が揃って初めて固定ユーザーの resolver に差し替わる。
    monkeypatch.setenv("E2E_AUTH_BYPASS", "1")
    monkeypatch.setenv("E2E_AUTH_OID", "oid-e2e")
    monkeypatch.setenv("E2E_AUTH_NAME", "E2E User")

    resolver = get_current_user_resolver()
    assert isinstance(resolver, FixedUserResolver)

    # トークンなしのリクエストでも固定ユーザーを返す（検証を通さない）。
    user = asyncio.run(resolver.resolve(request=None))  # type: ignore[arg-type]
    assert user.oid == "oid-e2e"
    assert user.display_name == "E2E User"


# --- /api/me の E2E モード統合（resolver → skip_sandbox → 単一プロダクト） -----------


@pytest.fixture
def client() -> Iterator[TestClient]:
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()
    if hasattr(app.state, "repository"):
        del app.state.repository


def test_me_in_e2e_mode_returns_only_the_seeded_test_product(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # seeding 相当: prd_test_<runId> にプロダクトと E2E ユーザーの member を作る。
    oid = "oid-e2e"
    product_id = "prd_test_abc123"
    repo = InMemoryRepository()
    create_product(repo, product_id=product_id, name="E2E テスト", actor="system:e2e-seed")
    create_member(repo, product_id=product_id, oid=oid, role=Role.ADMIN, actor="system:e2e-seed")
    app.state.repository = repo

    monkeypatch.setenv("E2E_AUTH_BYPASS", "1")
    monkeypatch.setenv("E2E_AUTH_OID", oid)

    # トークンなしでも env ゲートの resolver が固定ユーザーに解決する。
    res = client.get("/api/me")

    assert res.status_code == 200
    body = res.json()
    assert body["oid"] == oid
    # E2E モードではサンドボックス自動参加をスキップするので、products は seeding した
    # prd_test の 1 件だけ（バックログが確実にこれを選ぶ）。
    product_ids = [p["productId"] for p in body["products"]]
    assert product_ids == [product_id]
    assert SANDBOX_PRODUCT_ID not in product_ids
