"""
Return the rendered HTML of the current page.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from ..browser import BrowserManager
from .base import SessionInput, ToolDefinition, with_session


class GetHtmlInput(SessionInput):
    pass


def build_get_html(manager: BrowserManager) -> ToolDefinition:
    def runner(raw: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        # No extra validation needed beyond the optional session id.
        session_id, data, page = with_session(raw, manager, GetHtmlInput)
        return session_id, {"html": page.content()}

    return ToolDefinition(
        name="get_html",
        description="Return the HTML content after scripts have executed.",
        schema=GetHtmlInput.model_json_schema(),
        run=runner,
    )


__all__ = ["build_get_html"]
