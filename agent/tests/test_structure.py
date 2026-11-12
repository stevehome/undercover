"""Checks on how the code is organized, so structure can't drift past a review."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_CLIENTS = {"api.py", "backend_http.py", "improver_api.py"}
AGENT_MODULES = [
    p for p in (ROOT / "agent").glob("*.py") if p.name not in BACKEND_CLIENTS
]


def test_only_the_clients_talk_http():
    """service.py is the agent's own web entry point: its routes are not calls."""
    for path in AGENT_MODULES:
        tree = ast.parse(path.read_text())
        assert "httpx" not in path.read_text(), path.name
        if path.name == "service.py":
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not node.value.startswith(("/api/", "http://")), path.name


def test_tools_are_module_level_not_built_inside_functions():
    for path in AGENT_MODULES:
        for function in ast.walk(ast.parse(path.read_text())):
            if not isinstance(function, ast.FunctionDef):
                continue
            for inner in ast.walk(function):
                if inner is not function and isinstance(inner, ast.FunctionDef):
                    decorators = {ast.unparse(d) for d in inner.decorator_list}
                    assert "tool" not in decorators, f"{path.name}: {inner.name}"


def test_backend_routes_hold_no_sql():
    source = (ROOT / "backend" / "main.py").read_text()
    assert "sqlite3" not in source
    assert "execute(" not in source


def test_no_float_annotations_for_money():
    for path in [*AGENT_MODULES, *(ROOT / "backend").glob("*.py")]:
        for node in ast.walk(ast.parse(path.read_text())):
            assert not (isinstance(node, ast.Name) and node.id == "float"), path.name


def test_backend_never_imports_the_agent():
    for path in (ROOT / "backend").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            assert not any(n.split(".")[0] == "agent" for n in names), path.name


def _imported_modules(path):
    modules = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_only_tracing_imports_langfuse():
    for path in AGENT_MODULES:
        if path.name != "tracing.py":
            assert "langfuse" not in {
                m.split(".")[0] for m in _imported_modules(path)
            }, path.name


def test_only_checkpoint_talks_to_postgres():
    for path in AGENT_MODULES:
        if path.name == "checkpoint.py":
            continue
        for module in _imported_modules(path):
            assert not module.startswith(("psycopg", "langgraph.checkpoint.postgres"))


def test_the_agent_applies_no_approval_limit():
    for path in AGENT_MODULES:
        text = path.read_text()
        assert "APPROVAL_LIMIT" not in text, path.name
        assert "1000" not in text, path.name


def test_only_seed_data_reads_the_data_folder():
    for path in (ROOT / "backend").glob("*.py"):
        if path.name != "seed_data.py":
            assert "DATA_DIR" not in path.read_text(), path.name
            assert '"data"' not in path.read_text(), path.name


ANSWER_KEY_READERS = {
    "tables.py",
    "seed_data.py",
    "evaluations.py",
    "scoring.py",
    "grading.py",
    "improver_view.py",
}


def test_only_seeding_opens_the_evals_folder():
    for path in [*(ROOT / "backend").glob("*.py"), *(ROOT / "agent").glob("*.py")]:
        if path.name != "seed_data.py":
            assert "evals" not in path.read_text(), path.name


def test_the_answer_key_is_read_only_where_an_evaluation_is_scored():
    for path in [*(ROOT / "backend").glob("*.py"), *(ROOT / "agent").glob("*.py")]:
        if path.name not in ANSWER_KEY_READERS:
            text = path.read_text()
            assert "answer_key" not in text, path.name
            assert "held_out_claims" not in text, path.name


def test_only_the_dispatcher_fans_out_with_send():
    for path in AGENT_MODULES:
        if path.name != "dispatcher.py":
            assert not any(
                isinstance(node, ast.ImportFrom)
                and any(alias.name == "Send" for alias in node.names)
                for node in ast.walk(ast.parse(path.read_text()))
            ), path.name


def test_only_agents_builds_the_claim_graph():
    for path in AGENT_MODULES:
        if path.name not in ("agents.py", "claim_graph.py"):
            assert "claim_graph" not in _imported_modules(path), path.name
            assert "build_graph" not in path.read_text(), path.name


def _paths(path):
    return [
        node.value
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith("/api/")
    ]


def test_the_claim_agents_client_cant_reach_the_scores_or_the_rounds():
    """The scores, the handlers' reasons and the rounds are the improver's client's."""
    forbidden = ("/api/improver", "/api/rounds", "/api/proposals", "/api/settings")
    for path in _paths(ROOT / "agent" / "api.py"):
        assert not path.startswith(forbidden), path
        assert not path.startswith("/api/evaluations"), path
    names = ast.parse((ROOT / "agent" / "api.py").read_text())
    functions = {n.name for n in ast.walk(names) if isinstance(n, ast.FunctionDef)}
    assert not {f for f in functions if "score" in f or "view" in f or "round" in f}


def test_only_the_improvers_client_calls_the_improvers_operations():
    for client in BACKEND_CLIENTS - {"improver_api.py"}:
        assert not any(
            p.startswith("/api/improver") for p in _paths(ROOT / "agent" / client)
        ), client
    assert _paths(ROOT / "agent" / "improver_api.py")
