"""
Tool registry that assembles all individual tool definitions.
"""
from __future__ import annotations

from typing import Dict

from ..browser import BrowserManager
from .base import ToolDefinition
from .click import build_click
from .extract_links import build_extract_links
from .fill import build_fill
from .get_html import build_get_html
from .navigate import build_navigate
from .screenshot import build_screenshot


def build_tools() -> Dict[str, ToolDefinition]:
    """
    Instantiate every tool once and return a name -> definition mapping.
    """

    manager = BrowserManager.get()
    builders = [
        build_navigate,
        build_screenshot,
        build_extract_links,
        build_fill,
        build_click,
        build_get_html,
    ]

    tools = []  # Keep a predictable order for deterministic `tools/list` responses.
    for builder in builders:
        # Each builder wires the shared BrowserManager into its tool.
        tools.append(builder(manager))

    # Expose the registry as a simple dict keyed by tool name.
    return {tool.name: tool for tool in tools}


__all__ = ["build_tools"]

