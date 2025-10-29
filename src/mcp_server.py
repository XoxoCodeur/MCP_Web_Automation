"""
Minimal MCP stdio server that wires MCP requests to the Playwright-backed tools.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, MutableMapping, Optional

from pydantic import BaseModel, Field, ValidationError

from .errors import ErrorCode, ToolError, to_error_payload
from .logging_conf import configure_logging, get_logger
from .tools import build_tools
from .tools.base import ToolDefinition

def _dumps(payload: Mapping[str, Any]) -> str:
    """
    Serialize a small Python mapping to JSON. We keep an optional fast-path via
    orjson but gracefully fall back to the stdlib when the dependency is absent.
    """

    try:
        import orjson
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    else:
        return orjson.dumps(payload).decode("utf-8")

# ---------------------------------------------------------------------------
# Request / response payloads
# ---------------------------------------------------------------------------


class MCPRequest(BaseModel):
    """Incoming MCP message decoded from a single JSON line."""

    id: str | int | None = None
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)


class ToolCallParams(BaseModel):
    """Payload carried by a `tools/call` request."""

    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


SERVER_INFO = {
    "name": "mcp-web-automation",
    "version": "0.1.0",
    "mcp_protocol": "stdio",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


@dataclass
class MCPResponse:
    """Outgoing message: either a result or an error."""

    id: str | int | None
    result: Mapping[str, Any] | None = None
    error: Mapping[str, Any] | None = None

    def to_json(self) -> str:
        payload: MutableMapping[str, Any] = {"id": self.id}
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error
        return _dumps(payload)


# ---------------------------------------------------------------------------
# Tool execution service
# ---------------------------------------------------------------------------


class ToolService:
    """Thin wrapper around the tool registry."""

    def __init__(self) -> None:
        self.logger = get_logger("mcp.tools")
        self.tools: Dict[str, ToolDefinition] = build_tools()

    def descriptors(self) -> Dict[str, Any]:
        """Return the metadata surfaced via `tools/list`."""

        return {
            name: {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.schema,
            }
            for name, tool in self.tools.items()
        }

    def call(self, name: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """
        Execute a tool and return the uniform success/error payload.
        """

        if name not in self.tools:
            return {
                "ok": False,
                "tool": name,
                "error": {
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": f"Unknown tool: {name}",
                },
                "meta": {"ts": _timestamp(), "duration_ms": 0},
            }

        tool = self.tools[name]
        incoming_args = dict(arguments)  # copy to avoid accidental mutations
        start = time.perf_counter()

        try:
            session_id, data = tool.run(incoming_args)
        except ToolError as exc:
            duration = _duration_ms(start)
            error_payload = exc.to_payload()
            self.logger.info(
                "tool_failure",
                extra={
                    "tool": name,
                    "session_id": incoming_args.get("session_id"),
                    "ok": False,
                    "error_code": exc.code.value,
                    "duration_ms": duration,
                },
            )
            failure: MutableMapping[str, Any] = {
                "ok": False,
                "tool": name,
                "error": error_payload,
                "meta": {"ts": _timestamp(), "duration_ms": duration},
            }
            if incoming_args.get("session_id"):
                failure["session_id"] = incoming_args["session_id"]
            return failure
        except Exception as exc:  # pragma: no cover - unexpected tool failure
            duration = _duration_ms(start)
            self.logger.exception("tool_failure_unexpected", extra={"tool": name})
            return {
                "ok": False,
                "tool": name,
                "error": to_error_payload(exc),
                "meta": {"ts": _timestamp(), "duration_ms": duration},
            }

        duration = _duration_ms(start)
        self.logger.info(
            "tool_success",
            extra={
                "tool": name,
                "session_id": session_id,
                "ok": True,
                "duration_ms": duration,
                "url": data.get("current_url") if isinstance(data, dict) else None,
            },
        )
        return {
            "ok": True,
            "tool": name,
            "session_id": session_id,
            "data": data,
            "meta": {"ts": _timestamp(), "duration_ms": duration},
        }


# ---------------------------------------------------------------------------
# MCP stdio loop
# ---------------------------------------------------------------------------


class MCPServer:
    """Blocking stdio loop that consumes requests and emits responses."""

    def __init__(self) -> None:
        configure_logging()
        self.logger = get_logger("mcp.server")
        self.tool_service = ToolService()

    def handle(self, request: MCPRequest) -> MCPResponse:
        """Route a parsed request to the appropriate handler."""

        if request.method == "initialize":
            return MCPResponse(
                id=request.id,
                result={**SERVER_INFO, "tools": list(self.tool_service.descriptors().keys())},
            )

        if request.method == "tools/list":
            return MCPResponse(id=request.id, result={"tools": list(self.tool_service.descriptors().values())})

        if request.method == "tools/call":
            params = ToolCallParams.model_validate(request.params)
            result = self.tool_service.call(params.name, params.arguments)
            return MCPResponse(id=request.id, result=result)

        return MCPResponse(
            id=request.id,
            error={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": f"Unknown method: {request.method}",
            },
        )

    def serve_forever(self) -> None:
        """Read JSON lines from stdin and respond on stdout."""

        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            response_line = self._dispatch(line)
            sys.stdout.write(response_line + "\n")
            sys.stdout.flush()

    def _dispatch(self, payload: str) -> str:
        try:
            request = MCPRequest.model_validate_json(payload)
        except ValidationError as exc:
            self.logger.error("invalid_request", extra={"error": exc.errors()})
            return MCPResponse(
                id=None,
                error={
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": "Invalid request payload",
                    "details": exc.errors(),
                },
            ).to_json()

        try:
            response = self.handle(request)
        except ValidationError as exc:
            response = MCPResponse(
                id=request.id,
                error={
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": "Invalid parameters",
                    "details": exc.errors(),
                },
            )
        except Exception as exc:  # pragma: no cover - last safety net
            self.logger.exception("request_failure")
            response = MCPResponse(id=request.id, error=to_error_payload(exc))

        return response.to_json()


def main() -> None:
    MCPServer().serve_forever()


if __name__ == "__main__":
    main()
