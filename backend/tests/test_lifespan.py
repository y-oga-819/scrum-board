"""アプリ lifespan（Cosmos クライアントのシングルトン管理）のテスト。

実 Cosmos には接続しない。``create_client`` / ``build_repository`` を差し替え、
「未構成なら何もしない」「構成済みなら1度だけ生成して shutdown で閉じる」ことを見る。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main


def test_lifespan_is_inert_without_cosmos_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
    monkeypatch.delenv("COSMOS_KEY", raising=False)
    monkeypatch.delenv("COSMOS_DATABASE", raising=False)

    # 構成済みなら呼ばれるはずの関数。未構成では呼ばれないことを保証する。
    def fail_create_client(_settings: object) -> object:
        raise AssertionError("未構成なのに CosmosClient を作ろうとした")

    monkeypatch.setattr(main, "create_client", fail_create_client)

    with TestClient(main.app) as client:
        assert main.app.state.repository is None
        assert client.get("/api/health").json()["status"] == "ok"


def test_lifespan_creates_singleton_and_closes_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://example.documents.azure.com:443/")
    monkeypatch.setenv("COSMOS_KEY", "test-key")
    monkeypatch.setenv("COSMOS_DATABASE", "scrumboard")

    created: list[object] = []
    closed: list[object] = []

    class FakeClient:
        def close(self) -> None:
            closed.append(self)

    def fake_create_client(_settings: object) -> FakeClient:
        instance = FakeClient()
        created.append(instance)
        return instance

    sentinel_repo = object()

    def fake_build_repository(_client: object, _settings: object) -> object:
        return sentinel_repo

    # マイグレーション適用（B-08）は構成済みの起動で走る。実適用は test_migrations が
    # 検証するので、ここでは「構築したリポジトリに対して1度呼ばれる」ことだけを見る。
    migrated: list[object] = []

    def fake_run_migrations(repository: object) -> list[str]:
        migrated.append(repository)
        return []

    monkeypatch.setattr(main, "create_client", fake_create_client)
    monkeypatch.setattr(main, "build_repository", fake_build_repository)
    monkeypatch.setattr(main, "run_migrations", fake_run_migrations)

    with TestClient(main.app) as client:
        # クライアントは1個だけ生成され、リポジトリが app.state に載る。
        assert len(created) == 1
        assert main.app.state.repository is sentinel_repo
        # 構築したリポジトリに対してマイグレーションが1度走る。
        assert migrated == [sentinel_repo]
        assert client.get("/api/health").json()["status"] == "ok"
        assert closed == []  # 稼働中は閉じない

    # shutdown で必ず close される（＝接続を放置しない）。
    assert closed == created
