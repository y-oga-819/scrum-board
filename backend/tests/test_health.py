from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "scrum-board"}


def test_unknown_api_route_is_404_not_spa_fallback():
    # /api is owned by the backend; unknown API paths must not fall through to
    # the SPA index.html, otherwise a typo'd endpoint would silently 200.
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404
