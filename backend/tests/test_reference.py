import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend import money, reference
from backend.errors import NotFound
from context import files

DATA = Path(__file__).resolve().parents[2] / "data"


def from_file(name):
    return money.convert(json.loads((DATA / name).read_text(), parse_float=Decimal))


@pytest.fixture(autouse=True)
def fresh_database(client):
    """Each test reads from a new database."""


def test_policies_and_customers_match_their_files():
    for record in from_file("policies.json"):
        assert reference.policy(record["policy_id"]) == record
    for record in from_file("customers.json"):
        assert reference.customer(record["customer_id"]) == record


def test_handlers_match_their_file():
    assert reference.handlers() == from_file("handlers.json")
    marcus = reference.handler_by_email("MARCUS.Oyelaran@undercover.example")
    assert marcus
    assert marcus["name"] == "Marcus Oyelaran"
    assert reference.handler_by_email("nobody@undercover.example") is None


def test_plans_and_add_ons_match_the_context_layers_file():
    file = money.convert(files.read_data("plans.yaml").content)
    for plan in file["plans"]:
        assert reference.plan(plan["plan"]) == plan
    for add_on in file["add_ons"]:
        assert reference.add_on(add_on["add_on"]) == add_on
    assert sorted(reference.deductible_benefits()) == sorted(
        file["deductible_applies_to"]
    )


@pytest.mark.parametrize(
    "lookup",
    [
        lambda: reference.policy("POL-9999"),
        lambda: reference.customer("CUS-9999"),
        lambda: reference.plan("gold"),
        lambda: reference.add_on("jetpack"),
    ],
)
def test_a_missing_record_raises_not_found(lookup):
    with pytest.raises(NotFound):
        lookup()
