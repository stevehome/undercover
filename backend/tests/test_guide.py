"""The user guide's page keeps its promises: pictures, words and nothing private."""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

GUIDE = Path(__file__).parents[2] / "guide"
FORBIDDEN = ["localhost", "127.0.0.1", "token", "bearer", "eyj", "arn:aws", "api_key"]


class Page(HTMLParser):
    """Collect a page's images and, for each section, its heading and paragraphs."""

    def __init__(self) -> None:
        super().__init__()
        self.images: list[dict[str, str | None]] = []
        self.sections: dict[str, dict[str, int]] = {}
        self._section = ""
        self._tag = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        self._tag = tag
        if tag == "section":
            self._section = values.get("id") or ""
            self.sections[self._section] = {"h2": 0, "p": 0}
        if tag == "img":
            self.images.append(values)
        if tag in ("h1", "h2", "p") and self._section in self.sections:
            counts = self.sections[self._section]
            counts[tag] = counts.get(tag, 0) + 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "section":
            self._section = ""


def read(text: str | None = None) -> Page:
    page = Page()
    page.feed(text if text is not None else (GUIDE / "index.html").read_text())
    return page


def problems(page: Page, folder: Path = GUIDE) -> list[str]:
    """Say what is wrong with the page's pictures, one line each."""
    found = []
    sources = {image.get("src") or "" for image in page.images}
    for image in page.images:
        src = image.get("src") or ""
        if not (image.get("alt") or "").strip():
            found.append(f"{src} has no alt text")
        if not (folder / src).is_file():
            found.append(f"{src} is missing")
        pair = re.sub(
            r"-(light|dark)\.png$",
            lambda m: "-dark.png" if m[1] == "light" else "-light.png",
            src,
        )
        if pair not in sources:
            found.append(f"{src} has no light and dark pair")
    return found


def test_the_page_has_pictures_and_each_is_whole() -> None:
    page = read()
    assert len(page.images) >= 20
    assert problems(page) == []


def test_every_section_has_a_heading_and_a_description() -> None:
    page = read()
    assert len(page.sections) >= 13
    for name, counts in page.sections.items():
        assert counts["h2"] + counts.get("h1", 0) == 1, name
        assert counts["p"] >= 1, name


def test_the_page_names_nothing_private() -> None:
    text = "\n".join(
        (GUIDE / name).read_text().lower() for name in ("index.html", "guide.css")
    )
    assert [word for word in FORBIDDEN if word.lower() in text] == []


@pytest.mark.parametrize(
    ("snippet", "expected"),
    [
        ('<img src="images/a-light.png" alt="">', "has no alt text"),
        ('<img src="images/none-light.png" alt="x">', "is missing"),
        ('<img src="images/queue-light.png" alt="x">', "no light and dark pair"),
    ],
)
def test_a_broken_picture_is_found(snippet: str, expected: str) -> None:
    found = problems(read(snippet))
    assert any(expected in line for line in found)
