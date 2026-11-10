from fastapi.testclient import TestClient

from agent import agents, api, service
from agent.tests.test_claim_graph import CLAIM, decision, sign_off


def test_the_service_carries_on_with_a_signed_off_claim(backend, script, saver):
    agents.decide_claim(CLAIM, script(decision(payout="1200.00"), "Done."), saver)
    sign_off(backend)
    service.app.dependency_overrides[service.claim_worker] = lambda: (
        lambda claim_id: agents.decide_claim(claim_id, script(), saver)
    )
    try:
        response = TestClient(service.app).post(f"/api/claims/{CLAIM}/resume")
    finally:
        service.app.dependency_overrides.clear()

    assert response.status_code == 202
    assert api.get_claim(CLAIM)["paid_amount"] == "1200.00"
