"""
Small helper around Playwright to open pages and keep sessions alive.
"""
from __future__ import annotations

import atexit
import uuid
from dataclasses import dataclass
from typing import Dict, Tuple

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright


@dataclass
class StoredPage:
    context: BrowserContext
    page: Page


class BrowserManager:
    """
    Tiny singleton wrapper.

    We launch Chromium once, create new contexts on demand, and reuse them when
    callers pass the same `session_id` back in.
    """

    _instance: "BrowserManager | None" = None

    def __init__(self) -> None:
        # Launch Playwright/Chromium once for the entire process.
        self._playwright = sync_playwright().start()
        self._browser: Browser = self._playwright.chromium.launch(headless=True)
        self._sessions: Dict[str, StoredPage] = {}
        atexit.register(self.shutdown)

    @classmethod
    def get(cls) -> "BrowserManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def session(self, session_id: str | None) -> Tuple[str, Page]:
        """
        Return an existing page when the session is known, otherwise create one.
        """

        if session_id and session_id in self._sessions:
            # Reuse the existing Playwright page for this session.
            stored = self._sessions[session_id]
            return session_id, stored.page

        # Otherwise start a fresh isolated context + page.
        context = self._browser.new_context()
        page = context.new_page()
        session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        self._sessions[session_id] = StoredPage(context=context, page=page)
        return session_id, page

    def shutdown(self) -> None:
        """
        Close every page/context and stop Playwright.
        """

        while self._sessions:
            # Pop items until the dictionary is empty so that a partial failure
            # cannot leave hanging pages/contexts.
            _, stored = self._sessions.popitem()
            stored.page.close()
            stored.context.close()

        self._browser.close()
        self._playwright.stop()
        BrowserManager._instance = None


__all__ = ["BrowserManager"]
