"""env ゲートの E2E 認証バイパス（D-22）。

**既定 OFF・fail-closed** を固定する。E2E は実サーバで回り ``dependency_overrides``
を使えないため、``E2E_AUTH_BYPASS=1`` かつ ``E2E_AUTH_OID`` のときだけ固定ユーザーの
resolver に差し替わる。旗の付け忘れ・oid 欠落では本番挙動（Entra）に落ちること。
"""

from __future__ import annotations

import asyncio

import pytest

from app.auth import e2e_bypass_from_env
from app.auth.dependencies import get_current_user_resolver
from app.auth.resolver import EntraCurrentUserResolver, FixedUserResolver


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
