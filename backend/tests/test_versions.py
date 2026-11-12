import difflib

from sqlalchemy import insert

from backend import db, tables
from backend.main import AgentConfiguration

INSTRUCTIONS = (
    db.Path(__file__).resolve().parents[2] / "data/claim_instructions.md"
).read_text()
RECIPE = (
    db.Path(__file__).resolve().parents[2] / "data/improver_recipe.md"
).read_text()


def add_version(table, version, verdict, **content):
    with db.connection() as conn:
        conn.execute(
            insert(table).values(
                version=version,
                reason="A test version",
                proposed_by="improver",
                created_on=db.now(),
                verdict=verdict,
                **content,
            )
        )


def add_configuration(version, verdict, instructions="New instructions.\n", model="m"):
    add_version(
        tables.configurations,
        version,
        verdict,
        instructions=instructions,
        model=model,
        reasoning_effort="low",
    )


def test_version_1_of_the_configuration_is_the_instructions_file(client):
    [first] = client.get("/api/configurations").json()

    assert first["version"] == 1
    assert first["instructions"] == INSTRUCTIONS
    assert (first["model"], first["reasoning_effort"]) == ("openai/gpt-6-luna", "low")
    assert first["verdict"] == "kept"


def test_version_1_of_the_recipe_is_the_recipe_file(client):
    [first] = client.get("/api/recipes").json()

    assert first["version"] == 1
    assert first["text"] == RECIPE
    assert "read_results" in first["text"]
    assert first["verdict"] == "kept"


def test_the_current_version_is_the_highest_one_kept(client):
    add_configuration(2, "kept")
    add_configuration(3, "rolled back")
    add_configuration(4, None)

    current = client.get("/api/configuration/current").json()

    assert current["version"] == 2


def test_the_agents_configuration_holds_no_scores_or_reasons(client):
    assert set(AgentConfiguration.model_fields) == {
        "version",
        "instructions",
        "model",
        "reasoning_effort",
        "round_id",
    }
    current = client.get("/api/configuration/current").json()
    assert set(current) == set(AgentConfiguration.model_fields)


def test_a_run_gives_its_own_version_and_model(client):
    add_configuration(2, "kept")
    body = {
        "concurrency": 1,
        "model": "stub/model",
        "reasoning_effort": "default",
        "configuration_version": 1,
    }
    run_id = client.post("/api/runs/dispatch", json=body).json()["run_id"]

    run = client.get(f"/api/runs/{run_id}/configuration").json()

    assert run["version"] == 1
    assert run["instructions"] == INSTRUCTIONS
    assert (run["model"], run["reasoning_effort"]) == ("stub/model", "default")
    assert client.get(f"/api/runs/{run_id}").json()["configuration_version"] == 1


def test_a_run_on_an_unknown_version_is_refused(client):
    body = {
        "concurrency": 1,
        "model": "m",
        "reasoning_effort": "low",
        "configuration_version": 9,
    }

    assert client.post("/api/runs/dispatch", json=body).status_code == 404


def test_an_evaluation_records_the_version_it_tests(client):
    add_configuration(2, None)
    body = {
        "concurrency": 1,
        "eval_set": "evaluation",
        "tiny": True,
        "model": "m",
        "reasoning_effort": "low",
        "configuration_version": 2,
    }

    run_id = client.post("/api/runs/evaluation", json=body).json()["run_id"]

    assert client.get(f"/api/runs/{run_id}").json()["configuration_version"] == 2


def test_the_diff_matches_difflib_with_additions_and_removals_marked(client):
    add_configuration(2, "kept", instructions="one\ntwo\nthree\n")
    add_configuration(3, "kept", instructions="one\n2\nthree\nfour\n")

    diff = client.get("/api/configurations/3/diff").json()

    expected = list(
        difflib.unified_diff(
            ["one", "two", "three"], ["one", "2", "three", "four"], lineterm="", n=3
        )
    )[2:]
    assert [line["text"] for line in diff["lines"] if line["kind"] != "hunk"] == [
        line[1:] for line in expected if not line.startswith("@@")
    ]
    kinds = {line["text"]: line["kind"] for line in diff["lines"]}
    assert kinds["two"] == "removed"
    assert kinds["2"] == "added"
    assert kinds["four"] == "added"
    assert kinds["one"] == "context"
    assert diff["from_version"] == 2


def test_the_diff_shows_a_changed_model_and_effort(client):
    add_configuration(2, "kept", model="google/gemini-3.5-flash-lite")

    diff = client.get("/api/configurations/2/diff").json()

    assert diff["model_before"] == "openai/gpt-6-luna"
    assert diff["model_after"] == "google/gemini-3.5-flash-lite"


def test_version_1_is_all_additions(client):
    diff = client.get("/api/configurations/1/diff").json()

    assert diff["from_version"] is None
    assert {line["kind"] for line in diff["lines"] if line["kind"] != "hunk"} == {
        "added"
    }


def test_a_recipe_diff_and_a_missing_version(client):
    add_version(tables.recipes, 2, "kept", text="1. Read.\n")

    diff = client.get("/api/recipes/2/diff").json()

    assert diff["from_version"] == 1
    assert any(line["kind"] == "removed" for line in diff["lines"])
    assert client.get("/api/recipes/9/diff").status_code == 404
