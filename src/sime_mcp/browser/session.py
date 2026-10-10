"""Isolated persistent browser context; credentials remain in the browser profile."""

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import BrowserContext, Error, async_playwright

from sime_mcp.config import SIME_ORIGIN, SIME_START_URL, Settings, make_private_dir
from sime_mcp.errors import (
    AuthenticationRequiredError,
    BrowserUnavailableError,
    CalendarResponseError,
)

RESUME_FILENAME = ".sime-resume.json"


def _read_resume(settings: Settings) -> dict | None:
    path = settings.browser_profile / RESUME_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        parsed = urlparse(data["diary_url"])
        if (
            parsed.scheme != "https"
            or parsed.netloc != urlparse(SIME_ORIGIN).netloc
            or not (parsed.path.startswith("/ords/r/agenda/") or parsed.path == "/ords/f")
            or not isinstance(data["cookies"], list)
        ):
            raise ValueError("invalid resume state")
        return data
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise BrowserUnavailableError(
            "Saved browser state is invalid. Run `sime logout`, then log in again."
        ) from exc


def resume_diary_url(settings: Settings) -> str:
    state = _read_resume(settings)
    return state["diary_url"] if state else SIME_START_URL


async def save_authenticated_session(context: BrowserContext, page, settings: Settings) -> None:
    """Keep session state only in the private Chromium profile, never in logs or MCP output."""
    parsed = urlparse(page.url)
    if parsed.scheme != "https" or parsed.netloc != urlparse(SIME_ORIGIN).netloc:
        raise CalendarResponseError("Authenticated diary page was not found on SIME.")
    state = await context.storage_state()
    data = {
        "diary_url": page.url,
        "cookies": [
            cookie
            for cookie in state["cookies"]
            if urlparse(SIME_ORIGIN).netloc == cookie.get("domain", "").lstrip(".")
            or urlparse(SIME_ORIGIN).netloc.endswith("." + cookie.get("domain", "").lstrip("."))
        ],
    }
    path = settings.browser_profile / RESUME_FILENAME
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(data, stream)
    os.replace(temporary, path)
    path.chmod(0o600)


@asynccontextmanager
async def browser_context(
    settings: Settings, *, headless: bool | None = None
) -> AsyncIterator[BrowserContext]:
    profile: Path = settings.browser_profile
    make_private_dir(profile)
    marker = profile / ".sime-mcp-profile"
    if not marker.exists():
        if any(profile.iterdir()):
            raise BrowserUnavailableError(
                "Configured browser profile already contains other data; choose an empty directory."
            )
        marker.write_text("Isolated SIME MCP Chromium profile.\n", encoding="utf-8")
        marker.chmod(0o600)
    async with async_playwright() as playwright:
        try:
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                headless=settings.browser_headless if headless is None else headless,
                accept_downloads=False,
                service_workers="allow",
            )
        except Error as exc:
            raise BrowserUnavailableError(
                "Chromium could not start. Install Chromium and close other SIME sessions."
            ) from exc
        state = _read_resume(settings)
        if state and state["cookies"]:
            try:
                await context.add_cookies(state["cookies"])
            except Error as exc:
                await context.close()
                raise BrowserUnavailableError(
                    "Saved browser state could not be restored. Run `sime logout`."
                ) from exc
        context.set_default_timeout(settings.browser_timeout_ms)
        try:
            yield context
        finally:
            await context.close()


async def open_diary(context: BrowserContext, settings: Settings | None = None):
    page = context.pages[0] if context.pages else await context.new_page()
    try:
        await page.goto(
            resume_diary_url(settings) if settings else SIME_START_URL,
            wait_until="domcontentloaded",
        )
    except Error as exc:
        if "ERR_ABORTED" in str(exc):
            raise AuthenticationRequiredError("SIME login is required. Run `sime login`.") from exc
        raise CalendarResponseError("SIME page could not be loaded.") from exc
    if page.url == "about:blank":
        raise CalendarResponseError("SIME page did not load.")
    return page


async def open_login(context: BrowserContext):
    """Follow the site's public entry route so login dialogs have a parent page."""
    page = context.pages[0] if context.pages else await context.new_page()
    try:
        await page.goto(SIME_ORIGIN, wait_until="domcontentloaded")
        await page.wait_for_url(
            "**/ords/r/agenda/main/public*", wait_until="domcontentloaded", timeout=15_000
        )
    except Error as exc:
        raise CalendarResponseError("SIME public login page could not be loaded.") from exc
    if page.url == "about:blank":
        raise CalendarResponseError("SIME public login page did not load.")
    return page
