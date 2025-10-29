MCP Web Automation Server
=========================

The repository contains a compact, heavily commented implementation of the
MCP stdio server required by the exercise. The focus is on clarity: a small
`BrowserManager`, one module per tool inside `src/tools/`, and a trimmed
`mcp_server.py` that translates between MCP requests and those tools.

What you get
------------
- Six Playwright-backed tools (`navigate`, `screenshot`, `extract_links`, `fill`,
  `click`, `get_html`) each defined in its own file for easy explanation.
- A lightweight stdio server that supports `initialize`, `tools/list`, and
  `tools/call` with uniform success/error payloads.
- JSON logging sent to stderr so stdout stays dedicated to MCP traffic.
- A short demo script (`demo/scenario_part1.py`) showing the required workflow
  end to end, including friendly error reporting for invalid URLs.

Quick start
-----------
1. Install dependencies and the Chromium browser Playwright relies on:
   ```bash
   pip install -e .
   playwright install chromium
   ```
2. Run the server:
   ```bash
   python -m src.mcp_server
   ```
3. Try the demo scenario (saves two screenshots in `demo/`):
   ```bash
   python -m demo.scenario_part1
   ```

Project layout
--------------
```
src/
  browser.py        # tiny Playwright session helper with inline comments
  errors.py         # central error codes surfaced to MCP clients
  logging_conf.py   # JSON logger wired to stderr
  mcp_server.py     # stdio loop that glues MCP to the tools
  tools/
    base.py         # shared validation helpers + ToolDefinition
    navigate.py     # tool 1 - navigate to URL
    screenshot.py   # tool 2 - capture screenshot
    extract_links.py# tool 3 - extract anchors
    fill.py         # tool 4 - fill form fields
    click.py        # tool 5 - click elements
    get_html.py     # tool 6 - return rendered HTML

demo/
  scenario_part1.py  # reference workflow using the tools service

README.md        # you are here
DECISIONS.md     # brief rationale for the main technical choices
pyproject.toml   # dependency list (playwright + pydantic)
```

Usage notes
-----------
- Each tool accepts an optional `session_id`. When omitted the server creates a
  new Playwright context, returns the ID, and the client can reuse it later.
- `ToolError` instances map cleanly to the JSON error envelope. Anything else is
  reported as `INTERNAL_ERROR`.
- Logs are short JSON lines (level/tool/session/duration) for easy ingestion.
