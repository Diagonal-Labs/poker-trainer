"""API smoke test."""

from fastapi.testclient import TestClient

from pokersim import __version__
from pokersim.api.app import create_app


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
