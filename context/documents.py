"""A document split into sections, each tagged with its document, number and title."""

import re
from typing import NamedTuple

from context.files import Document

HEADING = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)


class Section(NamedTuple):
    """One numbered section of a document."""

    document: str
    file: str
    number: int
    title: str
    text: str


def split(document: Document) -> list[Section]:
    """Split a document at its numbered headings; earlier text is no section."""
    headings = list(HEADING.finditer(document.body))
    ends = [h.start() for h in headings[1:]] + [len(document.body)]
    return [
        Section(
            document.name,
            document.file,
            int(heading.group(1)),
            heading.group(2),
            document.body[heading.end() : end].strip(),
        )
        for heading, end in zip(headings, ends, strict=True)
    ]


def search(sections: list[Section], query: str) -> list[Section]:
    """Return the sections that contain every word of the query, in any case."""
    words = query.lower().split()
    return [
        s for s in sections if all(w in f"{s.title} {s.text}".lower() for w in words)
    ]


def find(sections: list[Section], document: str, number: int) -> Section:
    """Return one section, or raise `ValueError` saying it isn't there."""
    for section in sections:
        if (section.document, section.number) == (document, number):
            return section
    name = document.replace("_", " ")
    raise ValueError(f"The {name} has no section {number}")
