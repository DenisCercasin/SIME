"""Observe the site's own calendar requests while navigating its UI."""

import asyncio
import re
from datetime import date, datetime
from urllib.parse import parse_qs, urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, Response
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from sime_mcp.config import MOLDOVA_TZ, SIME_ORIGIN, SIME_START_URL
from sime_mcp.errors import (
    AuthenticationRequiredError,
    CalendarNotFoundError,
    CalendarResponseError,
)
from sime_mcp.parsers.calendar import is_calendar_event_array

CALENDAR_SELECTOR = ".fc, .a-FC, [class*='fc-view']"
PREV_SELECTOR = ".fc-prev-button, .fc-prev"
NEXT_SELECTOR = ".fc-next-button, .fc-next"
RANGE_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})000000$")


def _request_range(response: Response) -> tuple[date, date] | None:
    request = response.request
    parsed = urlparse(response.url)
    if (
        request.method != "POST"
        or parsed.scheme != "https"
        or parsed.netloc != urlparse(SIME_ORIGIN).netloc
        or not parsed.path.endswith("/ords/wwv_flow.ajax")
    ):
        return None
    values = parse_qs(request.post_data or "", keep_blank_values=True)
    if values.get("x01") != ["GET"] or not values.get("p_request", [""])[0].startswith("PLUGIN="):
        return None
    try:
        start_raw, end_raw = values["x02"][0], values["x03"][0]
        if not (RANGE_RE.fullmatch(start_raw) and RANGE_RE.fullmatch(end_raw)):
            return None
        return date.fromisoformat(
            f"{start_raw[:4]}-{start_raw[4:6]}-{start_raw[6:8]}"
        ), date.fromisoformat(f"{end_raw[:4]}-{end_raw[4:6]}-{end_raw[6:8]}")
    except (KeyError, IndexError, ValueError):
        return None


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    return start, end


def _covers_month(request_range: tuple[date, date], month_bounds: tuple[date, date]) -> bool:
    start, end = request_range
    month_start, month_end = month_bounds
    return start <= month_start and end >= month_end and 0 < (end - start).days <= 50


def safe_calendar_structure(page: Page):
    """Sanitized selector discovery; no text, attributes, HTML or URLs."""
    return page.evaluate(
        """() => ({
            calendarCount: document.querySelectorAll('.fc, .a-FC').length,
            toolbarButtons: [...document.querySelectorAll('.fc-toolbar button')]
                .map(b => [...b.classList].filter(c => c.startsWith('fc-')))
                .slice(0, 20)
        })"""
    )


async def capture_calendar_month(
    page: Page,
    year: int,
    month: int,
    timeout_ms: int = 30_000,
    source_url: str = SIME_START_URL,
) -> list[dict]:
    """Capture a matching event response produced by normal browser navigation.

    The site controls its own session and AJAX payload. No request is replayed or forged.
    """
    target_bounds = _month_bounds(year, month)
    loop = asyncio.get_running_loop()
    result: asyncio.Future[list[dict]] = loop.create_future()
    ranges: asyncio.Queue[tuple[date, date]] = asyncio.Queue()
    bad_response = False

    async def inspect(response: Response) -> None:
        nonlocal bad_response
        request_range = _request_range(response)
        if request_range is None:
            return
        try:
            value = await response.json()
            if is_calendar_event_array(value):
                ranges.put_nowait(request_range)
                if _covers_month(request_range, target_bounds) and not result.done():
                    result.set_result(value)
            elif _covers_month(request_range, target_bounds):
                bad_response = True
        except (PlaywrightError, ValueError):
            if _covers_month(request_range, target_bounds):
                bad_response = True

    def listener(response: Response) -> None:
        asyncio.create_task(inspect(response))

    page.on("response", listener)
    try:
        try:
            await page.goto(source_url, wait_until="domcontentloaded", timeout=timeout_ms)
        except PlaywrightError as exc:
            if "ERR_ABORTED" in str(exc):
                raise AuthenticationRequiredError(
                    "SIME login is required. Run `sime login`."
                ) from exc
            raise CalendarResponseError("SIME could not be reached or loaded.") from exc
        calendar = page.locator(CALENDAR_SELECTOR).first
        if await calendar.count() and not await calendar.is_visible():
            agenda_card = page.locator(".badge-agenda").first
            if await agenda_card.count() and await agenda_card.is_visible():
                await agenda_card.click()
        try:
            await calendar.wait_for(state="visible", timeout=timeout_ms)
        except PlaywrightTimeoutError as exc:
            login_visible = await page.locator("input[type='password']").count() > 0
            if login_visible or "login" in page.url.lower() or "auth" in page.url.lower():
                raise AuthenticationRequiredError(
                    "SIME login is required. Run `sime login`."
                ) from exc
            raise CalendarNotFoundError(
                "Calendar was not found. Run `sime discover` to inspect controls."
            ) from exc

        # FullCalendar month grids can include days from adjacent months. The
        # midpoint of the observed 5- or 6-week request identifies the view month.
        try:
            initial_start, initial_end = await asyncio.wait_for(ranges.get(), 5)
            midpoint = initial_start + (initial_end - initial_start) / 2
            current = (midpoint.year, midpoint.month)
        except TimeoutError:
            current = None
        if current is None:
            today = datetime.now(MOLDOVA_TZ).date()
            current = (today.year, today.month)
        delta = (year - current[0]) * 12 + month - current[1]
        if abs(delta) > 24:
            raise CalendarNotFoundError("Requested month is more than 24 UI steps away.")
        if delta == 0 and not result.done():
            # Force a site-generated refresh with the month controls.
            previous = page.locator(PREV_SELECTOR).first
            following = page.locator(NEXT_SELECTOR).first
            if not await previous.count() or not await following.count():
                raise CalendarNotFoundError("Calendar month navigation controls were not found.")
            await previous.click()
            try:
                await asyncio.wait_for(ranges.get(), timeout_ms / 1000)
            except TimeoutError as exc:
                raise CalendarResponseError("Calendar navigation produced no response.") from exc
            await following.click()
        for _ in range(abs(delta)):
            button = page.locator(NEXT_SELECTOR if delta > 0 else PREV_SELECTOR).first
            if not await button.count():
                raise CalendarNotFoundError("Calendar month navigation controls were not found.")
            await button.click()
            try:
                await asyncio.wait_for(ranges.get(), timeout_ms / 1000)
            except TimeoutError as exc:
                raise CalendarResponseError("Calendar navigation produced no response.") from exc
        try:
            return await asyncio.wait_for(result, timeout_ms / 1000)
        except TimeoutError as exc:
            if bad_response:
                raise CalendarResponseError("SIME returned an invalid calendar response.") from exc
            raise CalendarResponseError(
                "No matching calendar response was observed. Check login and calendar view."
            ) from exc
    finally:
        page.remove_listener("response", listener)
