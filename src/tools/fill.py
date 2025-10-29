"""
Fill a form field identified by a CSS selector.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from pydantic import Field
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from ..browser import BrowserManager
from ..errors import ErrorCode, ToolError
from .base import SessionInput, ToolDefinition, with_session


class FillInput(SessionInput):
    selector: str = Field(description="CSS selector targeting the field to fill.")
    value: str = Field(description="Value to type into the element.")


def build_fill(manager: BrowserManager) -> ToolDefinition:
    def runner(raw: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        # Validate inputs then locate the desired element on the session page.
        session_id, data, page = with_session(raw, manager, FillInput)

        element = page.locator(data.selector)
        if element.count() == 0:
            raise ToolError(ErrorCode.ELEMENT_NOT_FOUND, f"No element matches selector '{data.selector}'.")

        target = element.first
        try:
            target.wait_for(state="visible", timeout=5_000)
        except PlaywrightTimeoutError as exc:
            raise ToolError(ErrorCode.ELEMENT_NOT_VISIBLE, f"Element '{data.selector}' never became visible.") from exc

        if not target.is_editable():
            raise ToolError(ErrorCode.ELEMENT_NOT_EDITABLE, f"Element '{data.selector}' is not editable.")

        try:
            target.fill(data.value)
        except PlaywrightError as exc:
            raise ToolError(ErrorCode.INTERNAL_ERROR, f"Filling '{data.selector}' failed: {exc}") from exc

        # Signal success to the caller.
        return session_id, {"filled": True}

    return ToolDefinition(
        name="fill",
        description="Fill a text input or textarea using a CSS selector.",
        schema=FillInput.model_json_schema(),
        run=runner,
    )


__all__ = ["build_fill"]
