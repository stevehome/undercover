import pytest

from context import documents
from context.files import read_document


@pytest.fixture(params=["policy_wording", "claims_manual"])
def document(request):
    return read_document(request.param)


def test_a_document_is_split_at_its_numbered_headings(document):
    sections = documents.split(document)

    numbers = [s.number for s in sections]
    assert numbers == list(range(1, len(sections) + 1))
    assert {s.document for s in sections} == {document.name}
    assert {s.file for s in sections} == {document.file}
    assert all(s.title and s.text for s in sections)


def test_the_front_matter_is_never_part_of_a_section(document):
    sections = documents.split(document)

    assert document.version in {"2026.1", "2026.2"}
    assert not any("source:" in s.text or s.text.startswith("---") for s in sections)
    assert not any("reviewed:" in s.text for s in sections)


def test_a_section_holds_its_text_and_not_its_heading_or_the_next_sections():
    sections = documents.split(read_document("claims_manual"))

    records = documents.find(sections, "claims_manual", 14)

    assert records.title == "Records"
    assert records.text.startswith("Every decision record holds")
    assert "## " not in records.text
    assert "Wording versions" not in records.text


def test_the_document_has_the_sections_the_brief_counts_on():
    wording = documents.split(read_document("policy_wording"))
    manual = documents.split(read_document("claims_manual"))

    assert (len(wording), len(manual)) == (12, 14)


def test_a_search_finds_the_sections_with_every_word_in_any_case():
    sections = documents.split(read_document("claims_manual"))

    found = documents.search(sections, "DECISION RECORD")

    assert [s.number for s in found if s.number == 14] == [14]
    assert documents.search(sections, "decision zzzunknown") == []


def test_a_section_that_does_not_exist_is_a_value_error():
    sections = documents.split(read_document("claims_manual"))

    with pytest.raises(ValueError, match="no section 99"):
        documents.find(sections, "claims_manual", 99)
