import pytest

from context import server


def sources(answer):
    """Every file an answer names must carry its system, owner and review date."""
    assert answer["sources"]
    for file, source in answer["sources"].items():
        assert file.endswith((".yaml", ".md")), file
        assert set(source) == {"system", "owner", "reviewed"}, file


def test_a_term_is_found_in_any_case_with_its_sections():
    found = server.lookup_term("  cArRiEr ")

    assert found["answer"]["term"] == "Carrier"
    assert found["answer"]["definition"].startswith("An airline")
    assert found["answer"]["sections"] == [12]
    assert list(found["sources"]) == ["glossary.yaml"]
    sources(found)


def test_an_unknown_term_gets_the_terms_the_glossary_defines():
    found = server.lookup_term("Zebra")

    assert found["answer"]["unknown"] == "Zebra"
    assert "Carrier" in found["answer"]["terms"]
    sources(found)


@pytest.mark.parametrize("record", ["claim", "policy", "previous_claim"])
def test_each_records_fields_are_described(record):
    found = server.describe_fields(record)

    assert found["answer"]["record"] == record
    assert found["answer"]["fields"]
    assert list(found["sources"]) == ["data_dictionary.yaml"]
    sources(found)


@pytest.mark.parametrize(
    ("plan", "deductible"),
    [("economy", 100.0), ("premium", 50.0), ("first", 0.0)],
)
def test_a_plan_comes_with_its_deductible_and_the_add_ons(plan, deductible):
    found = server.get_plan(plan)

    assert found["answer"]["plan"]["plan"] == plan
    assert found["answer"]["plan"]["deductible"] == deductible
    assert found["answer"]["deductible_applies_to"] == ["baggage", "emergency_medical"]
    assert {a["add_on"] for a in found["answer"]["add_ons"]} >= {"adventure_sports"}
    sources(found)


def test_the_claim_rules_come_with_their_numbers():
    found = server.get_claim_rules()

    window = next(r for r in found["answer"] if r["rule"] == "filing_window")
    assert window["days"] == 90
    assert list(found["sources"]) == ["claim_rules.yaml"]
    sources(found)


def test_reference_data_is_searched_for_every_word_in_any_case():
    found = server.search_reference_data("TROPICAL storm MARISOL")

    assert found["answer"]
    assert {f["topic"] for f in found["answer"]} == {"events"}
    assert all("Marisol" in f["fact"] for f in found["answer"])
    assert server.search_reference_data("zzzunknown")["answer"] == []
    sources(found)


def test_a_search_of_the_documents_names_the_file_of_each_section_it_finds():
    found = server.search_documents("sign off")

    assert found["answer"]
    for hit in found["answer"]:
        assert hit["file"] in found["sources"]
        assert set(hit) == {"document", "number", "title", "file"}
    sources(found)


def test_a_search_with_no_hits_names_no_file():
    assert server.search_documents("zzzunknown") == {"sources": {}, "answer": []}


def test_a_section_is_read_by_its_document_and_number():
    found = server.read_section("claims_manual", 14)

    assert found["answer"]["title"] == "Records"
    assert found["answer"]["text"].startswith("Every decision record holds")
    assert list(found["sources"]) == ["claims_manual.md"]
    sources(found)


def test_a_section_that_does_not_exist_is_refused_in_words():
    with pytest.raises(ValueError, match="no section 99"):
        server.read_section("policy_wording", 99)
