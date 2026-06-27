"""HTML parsing for web_search / web_fetch.

Uses selectolax (CSS-selector-based) when available, with stdlib fallback.
"""

from __future__ import annotations

import html
import importlib
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


def _make_parser_classes():
    """Factory: return (SearchResultParser, HTMLTextParser) for the best
    available HTML parser backend."""
    try:
        _sp = importlib.import_module("selectolax.parser")
        _SelParser = _sp.HTMLParser
    except ImportError:
        _SelParser = None

    if _SelParser is not None:

        class _SelSearchParser:
            """Extract DuckDuckGo lite result links and titles using selectolax."""

            def __init__(self) -> None:
                self.results: list[dict[str, str]] = []

            def feed(self, data: str) -> None:
                tree = _SelParser(data)
                for link in tree.css("a"):
                    href = link.attributes.get("href", "")
                    if not href or "uddg=" not in href:
                        continue
                    parsed = urlparse(str(href))
                    query = parse_qs(str(parsed.query))
                    uddg = query.get("uddg", [""])[0]
                    if not uddg:
                        continue
                    url = unquote(uddg)
                    title = link.text(deep=True, separator=" ").strip()
                    title = " ".join(title.split())
                    if title and not any(r["url"] == url for r in self.results):
                        self.results.append({"title": html.unescape(title), "url": url})
                        self.results.append({"title": html.unescape(title), "url": url})

        class _SelTextParser:
            """Strip scripts/styles and collect visible text + title using selectolax."""

            def __init__(self) -> None:
                self.title = ""
                self.text_parts: list[str] = []

            def feed(self, data: str) -> None:
                tree = _SelParser(data)
                for tag in ("script", "style", "noscript"):
                    for node in tree.css(tag):
                        node.decompose()
                title_tag = tree.css_first("title")
                if title_tag is not None:
                    self.title = title_tag.text(deep=True, separator=" ").strip()
                body = tree.css_first("body")
                if body is not None:
                    raw = body.text(deep=True, separator=" ")
                    for line in raw.splitlines():
                        text = " ".join(line.split())
                        if text:
                            self.text_parts.append(text)

        return _SelSearchParser, _SelTextParser

    class _StdSearchParser(HTMLParser):
        """Extract DuckDuckGo lite result links and titles using stdlib."""

        def __init__(self) -> None:
            super().__init__()
            self.results: list[dict[str, str]] = []
            self._href: str | None = None
            self._title_parts: list[str] = []

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            if tag != "a":
                return
            href = dict(attrs).get("href")
            if not href or "uddg=" not in href:
                return
            parsed = urlparse(href)
            query = parse_qs(parsed.query)
            uddg = query.get("uddg", [""])[0]
            if not uddg:
                return
            self._href = unquote(uddg)
            self._title_parts = []

        def handle_data(self, data: str) -> None:
            if self._href is not None:
                self._title_parts.append(data)

        def handle_endtag(self, tag: str) -> None:
            if tag != "a" or self._href is None:
                return
            title = " ".join("".join(self._title_parts).split())
            if title and not any(
                result["url"] == self._href for result in self.results
            ):
                self.results.append(
                    {
                        "title": html.unescape(title),
                        "url": self._href,
                    }
                )
            self._href = None
            self._title_parts = []

    class _StdTextParser(HTMLParser):
        """Strip scripts/styles and collect visible text + title using stdlib."""

        def __init__(self) -> None:
            super().__init__()
            self.title = ""
            self.text_parts: list[str] = []
            self._in_title = False
            self._skip_depth = 0

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            if tag in {"script", "style", "noscript"}:
                self._skip_depth += 1
            elif tag == "title":
                self._in_title = True

        def handle_endtag(self, tag: str) -> None:
            if tag in {"script", "style", "noscript"} and self._skip_depth:
                self._skip_depth -= 1
            elif tag == "title":
                self._in_title = False

        def handle_data(self, data: str) -> None:
            text = " ".join(data.split())
            if not text:
                return
            if self._in_title:
                self.title = f"{self.title} {text}".strip()
            elif not self._skip_depth:
                self.text_parts.append(text)

    return _StdSearchParser, _StdTextParser


SearchResultParser, HTMLTextParser = _make_parser_classes()


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(getattr(item, "text", "")))
        return "\n".join(part for part in parts if part)
    return str(content)


QUERY_RE = re.compile(r"query:\s*(.+)", flags=re.IGNORECASE | re.DOTALL)
URL_RE = re.compile(r"https?://\S+")


def extract_query(text: str) -> str:
    match = QUERY_RE.search(text)
    if match:
        return match.group(1).strip().strip("\"'")
    return text.strip()


def extract_url(text: str) -> str:
    match = URL_RE.search(text)
    return match.group(0).rstrip(").,]") if match else text.strip()
