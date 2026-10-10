import json
from datetime import date, time

import pytest

from sime_mcp.config import Settings
from sime_mcp.mcp_server import create_server
from sime_mcp.models import Lesson
from sime_mcp.services.calendar import CalendarService


@pytest.mark.asyncio
async def test_mcp_tools_use_service_and_return_structured_data(monkeypatch, tmp_path):
    lesson = Lesson(
        date=date(2026, 10, 8),
        subject="Biologie",
        lesson_number=1,
        start_time=time(8, 15),
        end_time=time(9),
        homework="Citiți pagina 12",
    )

    async def fake_range(self, start, end):
        assert start <= lesson.date <= end
        return [lesson]

    monkeypatch.setattr(CalendarService, "get_calendar_range", fake_range)
    server = create_server(Settings(data_dir=tmp_path))
    tools = {tool.name for tool in await server.list_tools()}
    assert tools == {
        "get_schedule",
        "get_homework",
        "get_subjects",
        "get_today_schedule",
        "get_week_schedule",
    }

    schedule = await server.call_tool(
        "get_schedule", {"start_date": "2026-10-08", "end_date": "2026-10-08"}
    )
    schedule_text = json.dumps(schedule, default=str, ensure_ascii=False)
    assert "Biologie" in schedule_text
    assert "Citiți pagina 12" in schedule_text
    assert "cookie" not in schedule_text

    homework = await server.call_tool(
        "get_homework", {"start_date": "2026-10-08", "end_date": "2026-10-08"}
    )
    assert "due_date" in json.dumps(homework, default=str)
