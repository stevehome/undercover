from pathlib import Path

import pytest

from agent import agents, routes
from agent.direct import DirectRoute
from agent.tests.test_claim_graph import CLAIM, decision
from agent.tests.test_routes import PAYOUT

PLANS_SOURCE = {
    "system": "Policy administration",
    "owner": "Product",
    "reviewed": "2026-09-01",
}


def recorded(backend, kind=None):
    steps = backend.get(f"/api/claims/{CLAIM}/steps").json()
    return [s for s in steps if kind is None or s["kind"] == kind]


@pytest.fixture(params=["direct", "gateway"])
def named(request, monkeypatch, signed_gateway_route):
    """Work on a route, with the prefix that route gives its tools' names."""
    gateway = request.param == "gateway"
    route = signed_gateway_route if gateway else DirectRoute()
    monkeypatch.setattr(routes, "choose", lambda: route)
    return lambda target, tool: f"{target}___{tool}" if gateway else tool


def test_each_tool_call_is_a_step_named_as_its_route_names_the_tool(
    backend, script, saver, named
):
    steps = (("get_claim", {}), ("get_plan", {"plan": "premium"}), PAYOUT)

    agents.decide_claim(CLAIM, script(*steps, decision(), "Done."), saver)

    calls = recorded(backend, "tool_call")
    assert [c["text"] for c in calls] == [
        f"Called {named('undercover-app', 'get_claim')}",
        f"Called {named('undercover-context', 'get_plan')}",
        f"Called {named('undercover-app', 'calculate_payout')}",
        f"Called {named('undercover-app', 'decide_claim')}",
    ]
    assert calls[1]["details"] == {"tool": named("undercover-context", "get_plan")}


def test_a_lookup_says_what_was_looked_up_and_where_it_came_from(
    backend, script, saver, named
):
    plan = ("get_plan", {"plan": "premium"})

    agents.decide_claim(CLAIM, script(plan, decision(), "Done."), saver)

    (lookup,) = recorded(backend, "lookup")
    assert lookup["text"] == "Looked up the premium plan"
    assert lookup["details"] == {"files": {"plans.yaml": PLANS_SOURCE}}


def test_reading_a_section_is_a_lookup_with_its_title_and_file(
    backend, script, saver, named
):
    read = ("read_section", {"document": "claims_manual", "number": 14})

    agents.decide_claim(CLAIM, script(read, decision(), "Done."), saver)

    (lookup,) = recorded(backend, "lookup")
    assert lookup["text"] == "Read claims manual section 14: Records"
    assert list(lookup["details"]["files"]) == ["claims_manual.md"]


def test_a_call_is_recorded_before_what_it_looked_up(backend, script, saver, named):
    rules = ("get_claim_rules", {})

    agents.decide_claim(CLAIM, script(rules, decision(), "Done."), saver)

    kinds = [s["kind"] for s in recorded(backend)]

    assert kinds.index("tool_call") < kinds.index("lookup")


def test_a_refusal_is_a_step_of_its_own_with_who_refused_and_why(
    backend, script, saver, named
):
    missing = ("read_section", {"document": "claims_manual", "number": 99})

    agents.decide_claim(CLAIM, script(missing, decision(), "Done."), saver)

    (refusal,) = recorded(backend, "refusal")
    assert refusal["details"]["source"] == "the context layer"
    assert "no section 99" in refusal["details"]["detail"]
    assert refusal["text"].startswith("Refused by the context layer: ")


def test_a_refusal_by_the_app_is_one_too(backend, script, saver, named):
    early = (
        "decide_claim",
        {
            "decision": "approve",
            "payout": "420.00",
            "reason": "Too soon.",
            "policy_reference": "Section 3",
        },
    )
    decline = decision("decline", "0.00")

    agents.decide_claim(CLAIM, script(early, decline, "Done."), saver)

    (refusal,) = recorded(backend, "refusal")
    assert refusal["details"]["source"] == "the app"
    assert "Claims manual section 14" in refusal["details"]["detail"]


def test_the_tools_record_nothing_themselves():
    source = (Path(__file__).parents[1] / "tools.py").read_text()

    assert "record_step" not in source
