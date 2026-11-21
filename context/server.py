"""The context layer's MCP server: seven read-only tools over the files.

The files are read once, when the process starts, never for a request. On Lambda
it runs behind a Function URL with IAM auth, and a fresh server answers each request:
FastMCP's session manager can only run once, and Mangum starts and stops the app
around every request.
"""

from typing import Any, Literal

from mangum import Mangum
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from context import documents, lookups
from context.answers import Sourced, answer
from context.files import read_data, read_document

Record = Literal["claim", "policy", "previous_claim"]
Plan = Literal["economy", "premium", "first"]
DocumentName = Literal["policy_wording", "claims_manual"]

GLOSSARY = read_data("glossary.yaml")
DICTIONARY = read_data("data_dictionary.yaml")
PLANS = read_data("plans.yaml")
RULES = read_data("claim_rules.yaml")
REFERENCE = read_data("reference_data.yaml")
DOCUMENTS = [read_document("policy_wording"), read_document("claims_manual")]
SECTIONS = [section for doc in DOCUMENTS for section in documents.split(doc)]
SOURCES = {doc.name: Sourced(doc.file, doc.source) for doc in DOCUMENTS}


def lookup_term(term: str) -> dict[str, Any]:
    """Look up a term the policy wording defines, with the sections it comes from."""
    return lookups.lookup_term(GLOSSARY, term)


def describe_fields(record: Record) -> dict[str, Any]:
    """Say what each field of a claim, a policy or a previous claim means."""
    return lookups.describe_fields(DICTIONARY, record)


def get_plan(plan: Plan) -> dict[str, Any]:
    """Get one plan's limits, waiting periods and deductible, and the add-ons."""
    return lookups.get_plan(PLANS, plan)


def get_claim_rules() -> dict[str, Any]:
    """Get the rules claims operations applies to every claim."""
    return lookups.get_claim_rules(RULES)


def search_reference_data(query: str) -> dict[str, Any]:
    """Search outside facts, such as storms, strikes and prices, for every word."""
    return lookups.search_reference_data(REFERENCE, query)


def search_documents(query: str) -> dict[str, Any]:
    """Search the policy wording and the claims manual for sections with every word."""
    found = documents.search(SECTIONS, query)
    hits = [
        {"document": s.document, "number": s.number, "title": s.title, "file": s.file}
        for s in found
    ]
    files = {s.document: SOURCES[s.document] for s in found}
    return answer(hits, *files.values())


def read_section(document: DocumentName, number: int) -> dict[str, Any]:
    """Read one numbered section of the policy wording or the claims manual."""
    section = documents.find(SECTIONS, document, number)
    return answer(section._asdict(), SOURCES[document])


TOOLS = [
    lookup_term,
    describe_fields,
    get_plan,
    get_claim_rules,
    search_reference_data,
    search_documents,
    read_section,
]


def build_server(behind_function_url: bool = False) -> FastMCP:
    """Build the server. A Function URL's host is refused by DNS rebinding protection,
    which IAM auth makes unnecessary there.
    """
    security = (
        TransportSecuritySettings(enable_dns_rebinding_protection=False)
        if behind_function_url
        else None
    )
    server = FastMCP(
        "undercover-context",
        stateless_http=True,
        json_response=True,
        transport_security=security,
    )
    for tool in TOOLS:
        server.add_tool(tool, annotations=ToolAnnotations(readOnlyHint=True))
    return server


def handler(event: dict[str, Any], lambda_context: Any) -> dict[str, Any]:
    """Answer a Function URL event with a server of its own."""
    app = build_server(behind_function_url=True).streamable_http_app()
    return Mangum(app, lifespan="auto")(event, lambda_context)
