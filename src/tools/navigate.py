"""
Navigate the current page to a new URL.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple
from urllib.parse import urlparse

from pydantic import Field
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from ..browser import BrowserManager
from ..errors import ErrorCode, ToolError
from .base import SessionInput, ToolDefinition, with_session


class NavigateInput(SessionInput):
    url: str = Field(description="Destination URL (http or https).")


def build_navigate(manager: BrowserManager) -> ToolDefinition:
    def runner(raw: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        # Validate inputs and fetch a Playwright page tied to the session id (or a new one).
        session_id, data, page = with_session(raw, manager, NavigateInput)

        parsed = urlparse(data.url)
        if parsed.scheme not in {"http", "https"}:
            raise ToolError(ErrorCode.INVALID_URL, f"Only http(s) URLs are supported (got {parsed.scheme}).")

        try:
            response = page.goto(data.url, wait_until="networkidle", timeout=30_000)
        except PlaywrightTimeoutError as exc:
            raise ToolError(ErrorCode.NAVIGATION_TIMEOUT, f"Navigation to {data.url} timed out.") from exc
        except PlaywrightError as exc:
            raise ToolError(ErrorCode.NETWORK_ERROR, f"Navigation failed for {data.url}: {exc}") from exc

        status = response.status if response else None
        # Return the information that the MCP success envelope will forward to the client.
        return session_id, {
            "current_url": page.url,
            "status": status,
            "title": page.title(),
        }

    return ToolDefinition(
        name="navigate",
        description="Navigate the page to the provided URL.",
        schema=NavigateInput.model_json_schema(),
        run=runner,
    )


__all__ = ["build_navigate"]
