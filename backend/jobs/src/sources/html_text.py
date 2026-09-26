"""HTML to plain text with the standard library ``html.parser``."""

import html
import re
from html.parser import HTMLParser

MAX_DESCRIPTION_CHARS = 30_000

_SKIPPED_TAGS = frozenset({"script", "style", "noscript", "template", "svg", "head"})
_PAGE_CHROME_TAGS = frozenset({"nav", "header", "footer", "aside", "form"})
_BLOCK_TAGS = frozenset(
    {
        "p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article", "main",
        "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "dd", "dt",
    }
)  # fmt: skip
_SPACES = re.compile(r"[ \t\r\f\v]+")


class _TextExtractor(HTMLParser):
    def __init__(self, skip_page_chrome: bool) -> None:
        super().__init__(convert_charrefs=True)
        self._skipped = _SKIPPED_TAGS | (_PAGE_CHROME_TAGS if skip_page_chrome else frozenset())
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._skipped:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._skipped:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(markup: str | None, *, skip_page_chrome: bool = False) -> str:
    """Readable text from an HTML fragment or page; entity-escaped markup is decoded first.

    ``skip_page_chrome`` also drops navigation, headers, footers and forms, for whole pages.
    """
    if not markup:
        return ""
    # Some APIs (Greenhouse) return the posting body as entity-escaped HTML.
    if "<" not in markup and "&lt;" in markup:
        markup = html.unescape(markup)
    parser = _TextExtractor(skip_page_chrome)
    parser.feed(markup)
    parser.close()
    lines = (_SPACES.sub(" ", line).strip() for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)[:MAX_DESCRIPTION_CHARS]
