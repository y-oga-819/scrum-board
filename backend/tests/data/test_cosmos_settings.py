"""``cosmos_settings_from_env`` の env 解釈（B-07・EX-1）。

特に TLS 検証の切り替え（``COSMOS_TLS_VERIFY``）が **fail-safe**（未設定・不明な値では
検証する）であることを固定する。エミュレータ相手の E2E だけ "0" で無効化する。
"""

from __future__ import annotations

import pytest

from app.data.settings import cosmos_settings_from_env


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("COSMOS_ENDPOINT", "COSMOS_KEY", "COSMOS_DATABASE", "COSMOS_TLS_VERIFY"):
        monkeypatch.delenv(name, raising=False)


def test_tls_verify_defaults_to_true_when_unset() -> None:
    assert cosmos_settings_from_env().tls_verify is True


def test_tls_verify_off_only_for_explicit_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COSMOS_TLS_VERIFY", "0")
    assert cosmos_settings_from_env().tls_verify is False


@pytest.mark.parametrize("value", ["1", "true", "", "yes", "no"])
def test_tls_verify_stays_true_for_other_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    # "0" 以外は検証する（誤った値でうっかり検証を切らない fail-safe）。
    monkeypatch.setenv("COSMOS_TLS_VERIFY", value)
    assert cosmos_settings_from_env().tls_verify is True
