"""
Error definitions and helper utilities for the MCP web automation server.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, MutableMapping, Optional


class ErrorCode(str, Enum):
    """Stable error codes surfaced to MCP clients."""

    INVALID_URL = "INVALID_URL"
    NAVIGATION_TIMEOUT = "NAVIGATION_TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    ELEMENT_NOT_FOUND = "ELEMENT_NOT_FOUND"
    ELEMENT_NOT_VISIBLE = "ELEMENT_NOT_VISIBLE"
    ELEMENT_NOT_EDITABLE = "ELEMENT_NOT_EDITABLE"
    ELEMENT_NOT_CLICKABLE = "ELEMENT_NOT_CLICKABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(slots=True)
class ToolError(Exception):
    """
    Domain specific exception raised by tool implementations.

    The MCP loop catches this exception and turns it into a uniform error payload.
    """

    code: ErrorCode
    message: str
    details: Optional[Mapping[str, Any]] = None

    def to_payload(self) -> MutableMapping[str, Any]:
        payload: MutableMapping[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.details:
            payload["details"] = dict(self.details)
        return payload

    def __str__(self) -> str:  # pragma: no cover - repr convenience
        return f"{self.code.value}: {self.message}"


def to_error_payload(exc: Exception) -> Mapping[str, Any]:
    """
    Convert any exception to a uniform error payload.
    """

    if isinstance(exc, ToolError):
        return exc.to_payload()
    return {
        "code": ErrorCode.INTERNAL_ERROR.value,
        "message": str(exc) or "Internal error",
    }


__all__ = [
    "ErrorCode",
    "ToolError",
    "to_error_payload",
]

