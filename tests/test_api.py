from fastapi.testclient import TestClient

from ingest_orquestator_server.main import app


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"service": "ingest-orquestator-server", "status": "ok"}
