import time
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend import grading, judge
from backend.judge import judge as ask_jev

DECISIONS = "/api/runs/evaluation"


class FakeDecisions:
    """A stand-in for the SDK's Decisions endpoint."""

    def __init__(self, probabilities, score):
        self.calls = []
        self.probabilities = probabilities
        self.score = score

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            answers={
                "grade": SimpleNamespace(
                    score=self.score, probabilities=self.probabilities
                ),
                "same_grounds": SimpleNamespace(noul=0.93),
                "same_section": SimpleNamespace(noul=0.12),
            },
            usage=SimpleNamespace(cost=0.00004),
        )


def fake_jev(monkeypatch, probabilities, score):
    decisions = FakeDecisions(probabilities, score)
    client = SimpleNamespace(alpha=SimpleNamespace(decisions=decisions))
    monkeypatch.setattr(judge, "_client", lambda: client)
    return decisions


HANDLER = {"decision": "approve", "reason": "Covered.", "reference": "Section 3"}
AGENT = {"decision": "approve", "rationale": "Covered.", "section": "Section 3"}


def test_the_letter_is_the_most_likely_level_not_the_rounded_score(monkeypatch):
    # The score 1.65 rounds to B, but A is the most likely level.
    fake_jev(monkeypatch, {"0": 0.4, "1": 0.05, "2": 0.05, "3": 0.5}, 1.65)

    judgement = ask_jev(HANDLER, AGENT)

    assert judgement.letter == "A"
    assert judgement.score == Decimal("1.65")


def test_the_two_checks_are_kept_as_probabilities_with_the_cost(monkeypatch):
    fake_jev(monkeypatch, {"0": 0.1, "1": 0.2, "2": 0.6, "3": 0.1}, 1.7)

    judgement = ask_jev(HANDLER, AGENT)

    assert (judgement.same_grounds, judgement.same_section) == (
        Decimal("0.93"),
        Decimal("0.12"),
    )
    assert judgement.cost == Decimal("0.00004")


def test_each_call_passes_the_address_a_timeout_and_no_retries(monkeypatch):
    decisions = fake_jev(monkeypatch, {"0": 1.0}, 0)

    ask_jev(HANDLER, AGENT)

    [call] = decisions.calls
    assert call["server_url"] == judge.ORIGIN
    assert call["timeout_ms"] == 10_000
    assert call["retries"] is None
    assert call["model"] == "typesafe/jev-1.13"
    assert call["state"] == {"handler": HANDLER, "agent": AGENT}


def evaluation(client, eval_set="held_out", tiny=True):
    body = {
        "concurrency": 5,
        "eval_set": eval_set,
        "tiny": tiny,
        "model": "stub/model",
        "reasoning_effort": "low",
        "configuration_version": 1,
    }
    return client.post(DECISIONS, json=body).json()


def decide(client, claims, count=None):
    for claim in claims[:count]:
        client.post(
            f"/api/claims/{claim['claim_id']}/decision",
            json={
                "decision": "decline",
                "payout": "0.00",
                "reason": "Not covered.",
                "policy_reference": "Section 1",
            },
        )


def finished(client, run):
    client.post(f"/api/runs/{run['run_id']}/finish")
    return client.get(f"/api/evaluations/{run['run_id']}").json()


def test_a_claim_the_agent_did_not_decide_gets_an_f_with_no_call(client, monkeypatch):
    asked = []

    def stub(handler, agent):
        asked.append(agent)
        return judge.Judgement(
            Decimal("3"), "A", Decimal("1"), Decimal("1"), Decimal("0.00001")
        )

    monkeypatch.setattr(judge, "judge", stub)
    run = evaluation(client)
    decide(client, run["claims"], count=3)

    result = finished(client, run)

    letters = [claim["grade"]["letter"] for claim in result["claims"]]
    assert sorted(letters) == ["A", "A", "A", "F", "F"]
    assert len(asked) == 3
    assert result["measures"]["grade"] == "1.800"


def test_a_claim_the_judge_fails_on_is_not_graded_and_left_out(client, monkeypatch):
    def stub(handler, agent):
        if handler["reference"] == calls[0]:
            raise TimeoutError
        return judge.Judgement(
            Decimal("2"), "B", Decimal("1"), Decimal("1"), Decimal("0")
        )

    calls = []
    monkeypatch.setattr(judge, "judge", stub)
    run = evaluation(client)
    decide(client, run["claims"])
    calls.append(None)

    result = finished(client, run)

    assert result["measures"]["grade"] == "2.000"


def test_a_run_with_no_graded_claim_has_no_grade(client, monkeypatch):
    def failing(handler, agent):
        raise TimeoutError

    monkeypatch.setattr(judge, "judge", failing)
    run = evaluation(client)
    decide(client, run["claims"])

    result = finished(client, run)

    assert result["measures"]["grade"] is None
    assert all(claim["grade"] is None for claim in result["claims"])


def test_the_claims_are_graded_in_parallel(client, monkeypatch):
    def slow(handler, agent):
        time.sleep(1)
        return judge.Judgement(
            Decimal("2"), "B", Decimal("1"), Decimal("1"), Decimal("0")
        )

    monkeypatch.setattr(judge, "judge", slow)
    run = evaluation(client, eval_set="evaluation", tiny=False)
    assert len(run["claims"]) == 25
    decide(client, run["claims"])

    started = time.monotonic()
    result = finished(client, run)

    assert time.monotonic() - started < 5
    assert result["measures"]["grade"] == "2.000"


def test_the_judges_cost_is_apart_from_the_agents(client):
    run = evaluation(client)
    decide(client, run["claims"])

    measures = finished(client, run)["measures"]

    assert measures["judge_cost"] == "0.000200000"
    assert Decimal(measures["model_cost_per_claim"]) == 0


def test_a_claim_shows_its_letter_score_and_the_two_checks(client):
    run = evaluation(client)
    decide(client, run["claims"])

    claim = finished(client, run)["claims"][0]

    assert claim["grade"]["letter"] == "B"
    assert claim["grade"]["score"] == "2.100"
    assert claim["grade"]["same_grounds_matched"] is True
    assert claim["grade"]["same_section_matched"] is True


def test_with_model_name_set_the_judge_is_not_called(client, monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    monkeypatch.setattr(grading.judge, "judge", pytest.fail)
    run = evaluation(client)
    decide(client, run["claims"])

    result = finished(client, run)

    assert result["measures"]["grade"] is None
    assert all(claim["grade"] is None for claim in result["claims"])


def test_a_dispatch_is_not_graded(client):
    client.post(
        "/api/runs/dispatch",
        json={
            "concurrency": 1,
            "model": "m",
            "reasoning_effort": "low",
            "configuration_version": 1,
        },
    )
    assert client.post("/api/runs/1/finish").status_code == 200
