import pytest

CLAIM = "CLM-1001"
SOURCE = {
    "system": "Policy administration",
    "owner": "Product",
    "reviewed": "2026-09-01",
}
STEPS = [
    ("note", "Security check: no instructions found", {}),
    ("tool_call", "Called undercover-context___get_plan", {"tool": "get_plan"}),
    (
        "lookup",
        "Looked up the premium plan",
        {"files": {"plans.yaml": SOURCE}},
    ),
    (
        "memory_search",
        "Searched the customer's memory for bags",
        {"found": ["Earlier: lost a bag."]},
    ),
    ("memory_save", "Saved the claim", {"saved": ["Claim CLM-1001: a delay."]}),
    (
        "refusal",
        "Refused by the Gateway: Tool Execution Denied",
        {"source": "the Gateway", "detail": "Tool Execution Denied"},
    ),
]


def post(client, kind, text, data):
    body = {"kind": kind, "text": text, "details": data}
    return client.post(f"/api/claims/{CLAIM}/steps", json=body)


def test_each_kind_of_step_is_listed_in_order_with_its_data(client):
    for kind, text, data in STEPS:
        assert post(client, kind, text, data).status_code == 200

    listed = client.get(f"/api/claims/{CLAIM}/steps").json()

    assert [(s["kind"], s["text"], s["details"]) for s in listed] == STEPS
    assert all(s["recorded_on"] for s in listed)


def test_a_step_of_an_unknown_kind_is_refused(client):
    assert post(client, "gossip", "Heard something", {}).status_code == 422


def test_a_step_with_no_details_is_refused(client):
    body = {"kind": "note", "text": "No details"}

    response = client.post(f"/api/claims/{CLAIM}/steps", json=body)

    assert response.status_code == 422


@pytest.mark.parametrize("kind", ["tool_call", "lookup", "refusal"])
def test_a_recorded_step_moves_a_waiting_claim_in_progress(client, kind):
    post(client, kind, "Something", {})

    assert client.get(f"/api/claims/{CLAIM}").json()["status"] == "in progress"
