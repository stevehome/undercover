import pytest

MARCUS = "marcus.oyelaran@undercover.example"


def setting(client, key):
    listed = client.get("/api/settings").json()
    return next(s for s in listed if s["key"] == key)


def decide(client, claim_id, payout):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": "approve",
            "payout": payout,
            "reason": "Covered.",
            "policy_reference": "Section 7",
        },
    ).json()


def test_the_settings_start_with_the_labs_values(client):
    assert setting(client, "payout_approval_limit")["value"] == "1000.00"
    assert setting(client, "objective_accuracy")["value"] == "0.60"
    assert setting(client, "tolerance_cost_per_claim")["value"] == "1.00"
    assert setting(client, "round_spending_limit")["value"] == "0.50"
    assert setting(client, "improver_agents_at_once")["value"] == 25


def test_a_change_is_recorded_with_the_handler_and_the_time(client):
    changed = client.post("/api/settings/round_spending_limit", json={"value": "0.75"})

    assert changed.status_code == 200
    assert changed.json()["value"] == "0.75"
    assert changed.json()["changed_by"] == "Dana Whitfield"
    assert changed.json()["changed_on"] is not None
    assert setting(client, "round_spending_limit")["changed_by"] == "Dana Whitfield"


def test_a_new_approval_limit_applies_to_the_next_decision(client):
    assert decide(client, "CLM-1001", "1200.00")["status"] == "waiting for sign-off"

    client.post("/api/settings/payout_approval_limit", json={"value": "2000"})

    after = decide(client, "CLM-1002", "1200.00")
    assert after["status"] == "decided"
    assert after["over_approval_limit"] == 0
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting for sign-off"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("objective_accuracy", "1.5"),
        ("objective_accuracy", "-0.1"),
        ("objective_accuracy", "0.123"),
        ("improver_agents_at_once", "26"),
        ("improver_agents_at_once", "0"),
        ("improver_agents_at_once", "2.5"),
        ("round_spending_limit", "100.01"),
        ("nothing_at_all", "1"),
    ],
)
def test_a_value_out_of_range_is_refused(client, key, value):
    refused = client.post(f"/api/settings/{key}", json={"value": value})

    assert refused.status_code == 422
    assert refused.json()["detail"]


def test_a_refused_change_changes_nothing(client):
    client.post("/api/settings/objective_accuracy", json={"value": "7"})

    assert setting(client, "objective_accuracy")["value"] == "0.60"
    assert setting(client, "objective_accuracy")["changed_by"] is None


def test_marcus_cannot_change_a_setting_and_dana_can(client, as_handler):
    refused = client.post(
        "/api/settings/round_spending_limit",
        json={"value": "1"},
        headers=as_handler(MARCUS),
    )
    assert refused.status_code == 403
    assert setting(client, "round_spending_limit")["value"] == "0.50"

    assert (
        client.post(
            "/api/settings/round_spending_limit", json={"value": "1"}
        ).status_code
        == 200
    )


def test_a_change_needs_a_sign_in(client):
    client.headers.pop("Authorization")
    refused = client.post("/api/settings/round_spending_limit", json={"value": "1"})
    assert refused.status_code == 401


def test_the_models_allowed_are_the_file_and_cannot_be_changed(client):
    models = client.get("/api/models").json()

    assert [m["model"] for m in models] == [
        "openai/gpt-6-luna",
        "google/gemini-3.5-flash-lite",
        "deepseek/deepseek-v4.1-flash",
    ]
    assert models[0]["reasoning_efforts"] == ["none", "low", "medium"]
    assert models[0]["input_price_per_million"] == 0.1
    assert client.post("/api/models", json={}).status_code == 405
    assert client.put("/api/models", json={}).status_code == 405


def test_with_model_name_set_the_one_model_is_free_at_default(client, monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")

    assert client.get("/api/models").json() == [
        {
            "model": "openrouter/free",
            "reasoning_efforts": ["default"],
            "input_price_per_million": 0.0,
            "output_price_per_million": 0.0,
        }
    ]
