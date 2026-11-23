from sqlalchemy import insert

from agent import agents
from agent.tests.conftest import STUB_MODEL, StubModel, create_dispatch
from agent.tests.test_claim_graph import CLAIM, decision
from backend import db, tables


class Capturing(StubModel):
    """A stub model that keeps the messages it was asked to answer."""

    seen: list = []

    def _generate(self, messages, *args, **kwargs):
        self.seen.append(messages)
        return super()._generate(messages, *args, **kwargs)


def add_kept_version(instructions, model="google/gemini-3.5-flash-lite"):
    with db.connection() as conn:
        conn.execute(
            insert(tables.configurations).values(
                version=2,
                instructions=instructions,
                model=model,
                reasoning_effort="low",
                reason="A test version",
                proposed_by="improver",
                created_on=db.now(),
                verdict="kept",
            )
        )


def worked_with(script, saver, run_id=None):
    llm = Capturing(messages=script(decision(), "Done.").messages, seen=[])
    agents.decide_claim(CLAIM, llm, saver, run_id)
    return llm.seen[0][0].content


def test_a_claim_with_no_run_uses_the_current_version(backend, script, saver):
    add_kept_version("Version two says hello.")

    assert worked_with(script, saver) == "Version two says hello."


def test_a_claim_in_a_run_uses_the_runs_version(backend, script, saver):
    run_id = create_dispatch(1, STUB_MODEL)
    add_kept_version("Version two says hello.")

    sent = worked_with(script, saver, run_id)

    assert "Version two says hello." not in sent
    assert "You are the UnderCover Agent" in sent
