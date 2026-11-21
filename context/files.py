"""The files data governance owns, read with the source each one names."""

from pathlib import Path
from typing import Any, NamedTuple

import yaml

FOLDER = Path(__file__).resolve().parent
FRONT_MATTER = "---"


class DataFile(NamedTuple):
    """A YAML file: what it holds, and the system, owner and review date it names."""

    file: str
    source: dict[str, str]
    content: dict[str, Any]


class Document(NamedTuple):
    """A Markdown document: its source, version and body, without its front matter."""

    name: str
    file: str
    source: dict[str, str]
    version: str
    body: str


def read_data(file: str) -> DataFile:
    """Read a YAML file in this folder."""
    content = yaml.safe_load((FOLDER / file).read_text(encoding="utf-8"))
    return DataFile(file, content.pop("source"), content)


def read_document(name: str) -> Document:
    """Read a document in this folder, such as `claims_manual`."""
    file = f"{name}.md"
    text = (FOLDER / file).read_text(encoding="utf-8")
    _, front, body = text.split(FRONT_MATTER, 2)
    header = yaml.safe_load(front)
    return Document(name, file, header["source"], header["version"], body.strip())
