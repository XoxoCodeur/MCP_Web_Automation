"""
Shared helpers for individual MCP tools.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Tuple, Type

from pydantic import BaseModel, Field, ValidationError
from playwright.sync_api import Page

from ..browser import BrowserManager
from ..errors import ErrorCode, ToolError


class SessionInput(BaseModel):
    """All tools accept an optional session identifier so callers can reuse pages."""

    session_id: str | None = Field(
        default=None,
        description="Existing session identifier. Leave empty to start a new session.",
    )


@dataclass
class ToolDefinition:
    """
    Small container describing a tool and providing the callable that executes it.
    """

    name: str
    description: str
    schema: Dict[str, Any]
    run: Callable[[Dict[str, Any]], Tuple[str, Dict[str, Any]]]


def validate(model: Type[BaseModel], raw: Dict[str, Any]) -> BaseModel:
    """
    Validate raw arguments against the given Pydantic model and wrap errors with ToolError.

    We raise `ToolError` so the MCP loop can surface a clean, uniform error to clients.
    """

    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise ToolError(
            ErrorCode.INTERNAL_ERROR,
            "Invalid arguments supplied to tool.",
            {"validation_errors": exc.errors()},
        ) from exc


def with_session(
    raw: Dict[str, Any],
    manager: BrowserManager,
    input_model: Type[SessionInput],
) -> Tuple[str, SessionInput, Page]:
    """
    Utility used by every tool: validate inputs and return the session/page pair.
    """

    data = validate(input_model, raw)
    # Ask the BrowserManager for a page; it reuses the session when possible or
    # spins up a new Playwright context transparently.
    session_id, page = manager.session(data.session_id)
    return session_id, data, page


__all__ = ["SessionInput", "ToolDefinition", "validate", "with_session"]
