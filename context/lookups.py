"""The five tools that read the YAML files: each takes the file it reads."""

from typing import Any

from context.answers import Sourced, answer
from context.files import DataFile


def lookup_term(glossary: DataFile, term: str) -> dict[str, Any]:
    """Return a term's definition and sections in any case, or the terms there are."""
    terms = glossary.content["terms"]
    found = next((t for t in terms if t["term"].lower() == term.strip().lower()), None)
    payload = found or {"unknown": term, "terms": [t["term"] for t in terms]}
    return answer(payload, Sourced(glossary.file, glossary.source))


def describe_fields(dictionary: DataFile, record: str) -> dict[str, Any]:
    """Return what the fields of a claim, a policy or a previous claim mean."""
    found = next(r for r in dictionary.content["records"] if r["record"] == record)
    return answer(found, Sourced(dictionary.file, dictionary.source))


def get_plan(plans: DataFile, plan: str) -> dict[str, Any]:
    """Return a plan's limits, waiting periods and deductible, and the add-ons."""
    found = next(p for p in plans.content["plans"] if p["plan"] == plan)
    payload = {
        "plan": found,
        "deductible_applies_to": plans.content["deductible_applies_to"],
        "add_ons": plans.content["add_ons"],
    }
    return answer(payload, Sourced(plans.file, plans.source))


def get_claim_rules(rules: DataFile) -> dict[str, Any]:
    """Return the rules claims operations applies to every claim."""
    return answer(rules.content["rules"], Sourced(rules.file, rules.source))


def search_reference_data(reference: DataFile, query: str) -> dict[str, Any]:
    """Return the facts that contain every word of the query, each with its topic."""
    words = query.lower().split()
    facts = [
        {"topic": topic["topic"], "fact": fact}
        for topic in reference.content["topics"]
        for fact in topic["facts"]
        if all(word in fact.lower() for word in words)
    ]
    return answer(facts, Sourced(reference.file, reference.source))
