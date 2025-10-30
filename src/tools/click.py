"""
Click a CSS-selected element.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from pydantic import Field
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from ..browser import BrowserManager
from ..errors import ErrorCode, ToolError
from .base import SessionInput, ToolDefinition, with_session


class ClickInput(SessionInput):
    selector: str = Field(description="CSS selector targeting the element to click.")


def build_click(manager: BrowserManager) -> ToolDefinition:
    def runner(raw: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        # Validate inputs then try to interact with the element on the session page.
        session_id, data, page = with_session(raw, manager, ClickInput)

        element = page.locator(data.selector)
        if element.count() == 0:
            raise ToolError(ErrorCode.ELEMENT_NOT_FOUND, f"No element matches selector '{data.selector}'.")

        target = element.first

        # Scroll element into view before checking visibility
        try:
            target.scroll_into_view_if_needed(timeout=2_000)
        except (PlaywrightTimeoutError, PlaywrightError):
            pass  # Continue even if scroll fails

        try:
            target.wait_for(state="visible", timeout=5_000)
        except PlaywrightTimeoutError as exc:
            raise ToolError(ErrorCode.ELEMENT_NOT_VISIBLE, f"Element '{data.selector}' never became visible.") from exc

        if not target.is_enabled():
            raise ToolError(ErrorCode.ELEMENT_NOT_CLICKABLE, f"Element '{data.selector}' is disabled.")

        try:
            target.click()
        except PlaywrightTimeoutError as exc:
            raise ToolError(ErrorCode.ELEMENT_NOT_CLICKABLE, f"Element '{data.selector}' was not clickable.") from exc
        except PlaywrightError as exc:
            raise ToolError(ErrorCode.INTERNAL_ERROR, f"Clicking '{data.selector}' failed: {exc}") from exc

        # Signal success to the caller.
        return session_id, {"clicked": True}

    return ToolDefinition(
        name="click",
        description="Click a visible, enabled element identified by CSS selector.",
        schema=ClickInput.model_json_schema(),
        run=runner,
    )


__all__ = ["build_click"]
