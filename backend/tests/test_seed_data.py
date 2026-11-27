import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

from backend import db, tables

DATA = Path(__file__).resolve().parents[2] / "data"


def count(conn, table):
    return conn.execute(select(func.count()).select_from(table)).scalar_one()


def test_a_new_database_holds_every_record(client):
    with db.connection() as conn:
        counts = {
            table.name: count(conn, table)
            for table in (
                tables.claims,
                tables.policies,
                tables.customers,
                tables.plans,
                tables.add_ons,
                tables.handlers,
            )
        }
        documents = {
            row.document: row.version
            for row in conn.execute(
                select(tables.documents.c.document, tables.documents.c.version)
            )
        }
    assert counts == {
        "claims": 34,
        "policies": 59,
        "customers": 58,
        "plans": 3,
        "add_ons": 3,
        "handlers": 3,
    }
    assert documents == {"policy_wording": "2026.2", "claims_manual": "2026.3"}


def test_amounts_come_back_exact(client):
    with db.connection() as conn:
        trip = conn.execute(
            select(tables.policies.c.trip).where(
                tables.policies.c.policy_id == "POL-2001"
            )
        ).scalar_one()
        item = conn.execute(
            select(tables.claims.c["items"]).where(
                tables.claims.c.claim_id == "CLM-1001"
            )
        ).scalar_one()[0]
        limit = conn.execute(
            select(tables.settings.c.value).where(
                tables.settings.c.key == "payout_approval_limit"
            )
        ).scalar_one()
    assert trip["trip_cost"] == Decimal("3100.00")
    assert item["amount"] == Decimal("245.00")
    assert limit == "1000.00"


def test_starting_again_adds_nothing(client):
    db.forget_engines()
    with db.connection() as conn:
        assert count(conn, tables.policies) == 59


def test_requests_racing_for_a_new_database_share_one_engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'race.db'}"
    with ThreadPoolExecutor(8) as pool:
        engines = list(pool.map(lambda _: db.engine(url), range(8)))

    assert len({id(e) for e in engines}) == 1


def test_the_security_claim_is_in_the_queue_but_in_no_evaluation_set(client):
    claim = client.get("/api/claims/CLM-1901").json()
    assert claim["policy"]["policy_id"] == "POL-2901"
    assert claim["customer_id"] == "CUS-3901"
    assert claim["status"] == "waiting"
    with db.connection() as conn:
        answers = conn.execute(select(tables.answer_key.c.claim_id)).scalars().all()
        held_out = conn.execute(select(tables.held_out_claims.c.claim_id)).scalars()
    assert "CLM-1901" not in answers
    assert "CLM-1901" not in held_out.all()


def test_the_files_of_the_queue_are_unchanged_by_the_security_claim():
    queue = json.loads((DATA / "claims.json").read_text())
    assert len(queue) == 25
    assert "CLM-1901" not in [claim["claim_id"] for claim in queue]
