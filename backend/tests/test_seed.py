from collections import Counter

from backend import db, seed


def test_reset_puts_every_claim_back_as_it_was_seeded(client):
    client.post(
        "/api/claims/CLM-1001/steps",
        json={"kind": "note", "text": "started", "details": {}},
    )
    assert client.get("/api/claims/CLM-1001").json()["status"] == "in progress"

    seed.reset()

    statuses = Counter(c["status"] for c in client.get("/api/claims").json())
    assert statuses == {"waiting": 26, "decided": 8}
    assert client.get("/api/claims/CLM-1001/steps").json() == []


def test_database_url_uses_the_postgres_driver(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/postgres")
    assert db.database_url() == "postgresql+psycopg://u:p@host:5432/postgres"
