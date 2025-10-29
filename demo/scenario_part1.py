"""
Demonstration script for the MCP web automation tools.

It runs the "Part 1" scenario required by the spec:
  1. Navigate to example.com
  2. Capture a viewport screenshot
  3. Extract links and follow the first external one
  4. Capture a second screenshot on the new page
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict

from src.mcp_server import ToolService


class DemoToolError(RuntimeError):
    def __init__(self, tool: str, code: str, message: str) -> None:
        self.tool = tool
        self.code = code
        self.message = message
        super().__init__(f"{tool} failed ({code}): {message}")

OUTPUT_DIR = Path(__file__).resolve().parent


def save_png(image_b64: str, path: Path) -> None:
    """Persist a base64 encoded screenshot to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(image_b64))


def call_tool(service: ToolService, name: str, session_id: str | None, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper so the scenario reads like a script.

    We call the MCP tool, bubble up clean errors, and always return the response
    payload when the call succeeds.
    """
    if session_id:
        params = {**params, "session_id": session_id}
    response = service.call(name, params)
    if not response["ok"]:
        error = response.get("error", {})
        raise DemoToolError(
            tool=name,
            code=str(error.get("code", "UNKNOWN_ERROR")),
            message=str(error.get("message", "No error message provided")),
        )
    return response


def main() -> None:
    service = ToolService()
    session_id: str | None = None

    # Step 1: open the landing page.
    navigate = call_tool(service, "navigate", session_id, {"url": "https://example.com/"})
    session_id = navigate["session_id"]
    print(f"Session {session_id} at {navigate['data']['current_url']}")

    # Step 2: grab a viewport screenshot.
    screenshot = call_tool(service, "screenshot", session_id, {"mode": "viewport"})
    save_png(screenshot["data"]["image_b64"], OUTPUT_DIR / "1_viewport.png")
    print("Saved demo/1_viewport.png")

    # Step 3: collect links and follow the first external one.
    links = call_tool(service, "extract_links", session_id, {})
    external = next((link for link in links["data"]["links"] if link["is_external"]), None)
    if not external:
        raise RuntimeError("No external link found on example.com")

    # Step 4: follow the first external link.
    navigate = call_tool(service, "navigate", session_id, {"url": external["url"]})
    session_id = navigate["session_id"]
    print(f"Followed external link to {navigate['data']['current_url']}")

    # Step 5: document the external page.
    screenshot = call_tool(service, "screenshot", session_id, {"mode": "viewport"})
    save_png(screenshot["data"]["image_b64"], OUTPUT_DIR / "2_external.png")
    print("Saved demo/2_external.png")


if __name__ == "__main__":
    try:
        main()
    except DemoToolError as exc:
        print(f"[demo] {exc}")
        print("Aborting scenario. Please fix the input or retry with a reachable URL.")
        raise SystemExit(1)
