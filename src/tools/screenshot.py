"""
Capture a PNG screenshot of the current page.
"""
from __future__ import annotations

import base64
from typing import Any, Dict, Tuple

from pydantic import Field
from playwright.sync_api import Error as PlaywrightError

from ..browser import BrowserManager
from ..errors import ErrorCode, ToolError
from .base import SessionInput, ToolDefinition, with_session


class ScreenshotInput(SessionInput):
    mode: str = Field(
        default="viewport",
        description="Screenshot mode: 'viewport' or 'fullpage'.",
        pattern="^(viewport|fullpage)$",
    )


def build_screenshot(manager: BrowserManager) -> ToolDefinition:
    def runner(raw: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        # Validate inputs and reuse/create the Playwright page backing the session.
        session_id, data, page = with_session(raw, manager, ScreenshotInput)

        try:
            image_bytes = page.screenshot(full_page=data.mode == "fullpage")
        except PlaywrightError as exc:
            raise ToolError(ErrorCode.INTERNAL_ERROR, f"Screenshot failed: {exc}") from exc

        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        # Return the screenshot meta alongside the base64 data.
        return session_id, {
            "current_url": page.url,
            "mode": data.mode,
            "image_b64": image_b64,
        }

    return ToolDefinition(
        name="screenshot",
        description="Capture a PNG screenshot of the current page.",
        schema=ScreenshotInput.model_json_schema(),
        run=runner,
    )


__all__ = ["build_screenshot"]
