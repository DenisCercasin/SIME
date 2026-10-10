import asyncio
import json
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import pytest

from sime_mcp.browser.calendar_capture import (
    _covers_month,
    _request_range,
    capture_calendar_month,
)
from sime_mcp.config import Settings
from sime_mcp.mcp_server import create_server


class Request:
    method = "POST"

    def __init__(self, month):
        self.post_data = (
            "p_request=PLUGIN%3Dprivate-identifier&x01=GET&"
            f"x02=2026{month:02d}01000000&x03=2026{month + 1:02d}01000000"
        )


class Response:
    url = "https://agenda.sime.md/ords/wwv_flow.ajax?p_context=secret-session"

    def __init__(self, month, events):
        self.request = Request(month)
        self.events = events

    async def json(self):
        return self.events


class Locator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector
        self.first = self

    async def wait_for(self, **kwargs):
        pass

    async def count(self):
        return 1

    async def is_visible(self):
        return True

    async def click(self):
        self.page.month += 1 if "next" in self.selector else -1
        self.page.emit()


class Page:
    url = "https://agenda.sime.md/ords/r/agenda/main/main-page"

    def __init__(self, events):
        self.month = 10
        self.events = events
        self.listener = None

    def on(self, event, callback):
        self.listener = callback

    def remove_listener(self, event, callback):
        self.listener = None

    def locator(self, selector):
        return Locator(self, selector)

    async def goto(self, *args, **kwargs):
        self.emit()
        await asyncio.sleep(0)

    def emit(self):
        self.listener(Response(self.month, self.events))


@pytest.mark.asyncio
async def test_capture_matches_requested_month_and_sanitizes_logs(caplog):
    events = [
        {
            "title": "<div class='lesson-card'><span class='lesson-text-wrap'>Math</span></div>",
            "start": "2026-11-08T08:00:00",
            "end": "2026-11-08T09:00:00",
            "url": "javascript:secret-token",
        }
    ]
    page = Page(events)
    result = await capture_calendar_month(page, 2026, 11, timeout_ms=1000)
    assert result == events
    assert "secret" not in caplog.text
    assert page.listener is None


def test_request_needs_plugin_and_matching_origin():
    response = Response(10, [])
    assert _request_range(response)[0].isoformat() == "2026-10-01"
    response.request.post_data = "x01=GET&x02=20261001000000&x03=20261101000000"
    assert _request_range(response) is None
    response.request = Request(10)
    response.url = "https://example.net/ords/wwv_flow.ajax"
    assert _request_range(response) is None


def test_extended_fullcalendar_range_covers_month():
    assert _covers_month(
        (date(2026, 9, 28), date(2026, 11, 2)), (date(2026, 10, 1), date(2026, 11, 1))
    )
    assert not _covers_month(
        (date(2026, 9, 28), date(2026, 11, 2)), (date(2026, 11, 1), date(2026, 12, 1))
    )


@pytest.mark.asyncio
async def test_synthetic_browser_to_mcp_response(monkeypatch, tmp_path):
    events = json.loads((Path(__file__).parent / "fixtures/sample_calendar.json").read_text())
    page = Page(events)

    class Context:
        pages = [page]

    @asynccontextmanager
    async def fake_context(settings):
        yield Context()

    monkeypatch.setattr("sime_mcp.services.calendar.browser_context", fake_context)
    server = create_server(Settings(data_dir=tmp_path))
    response = await server.call_tool(
        "get_schedule", {"start_date": "2026-10-08", "end_date": "2026-10-08"}
    )
    result = json.dumps(response, default=str, ensure_ascii=False)
    assert "Biologie" in result
    assert "стр 12 № 3" in result
    assert "SECRET-CHECKSUM" not in result
