"""
Extract anchor tags from the current page.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple
from urllib.parse import urljoin, urlparse

from pydantic import Field

from ..browser import BrowserManager
from .base import SessionInput, ToolDefinition, with_session


class ExtractLinksInput(SessionInput):
    filter_contains: str | None = Field(
        default=None,
        description="Only keep links containing this text (case-insensitive).",
    )


def build_extract_links(manager: BrowserManager) -> ToolDefinition:
    def runner(raw: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        # Validate inputs and work with the session page.
        session_id, data, page = with_session(raw, manager, ExtractLinksInput)

        links = []
        current_url = page.url
        current_host = urlparse(current_url).netloc
        locator = page.locator("a")

        for idx in range(locator.count()):
            anchor = locator.nth(idx)
            href = (anchor.get_attribute("href") or "").strip()
            if not href:
                continue

            absolute = urljoin(current_url, href)
            label = (anchor.inner_text() or "").strip()
            parsed = urlparse(absolute)
            is_external = parsed.netloc and parsed.netloc != current_host

            candidate = {"text": label, "url": absolute, "is_external": bool(is_external)}

            if data.filter_contains:
                if data.filter_contains.lower() not in f"{label} {absolute}".lower():
                    continue

            links.append(candidate)

        # Return every matching link (optionally filtered) to the caller.
        return session_id, {"links": links}

    return ToolDefinition(
        name="extract_links",
        description="Return anchors on the page with text, URL, and external flag.",
        schema=ExtractLinksInput.model_json_schema(),
        run=runner,
    )


__all__ = ["build_extract_links"]
