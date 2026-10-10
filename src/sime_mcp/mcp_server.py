"""Read-only local MCP server over STDIO."""

from datetime import date, datetime, timedelta

from mcp.server.fastmcp import FastMCP

from sime_mcp.config import MOLDOVA_TZ, Settings
from sime_mcp.logging_utils import configure_logging
from sime_mcp.services.calendar import CalendarService
from sime_mcp.services.grades import GradeService
from sime_mcp.services.homework import HomeworkService
from sime_mcp.services.subjects import SubjectService


def create_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings.from_env()
    calendar = CalendarService(settings)
    homework = HomeworkService(calendar)
    grades = GradeService(calendar)
    subjects = SubjectService(calendar)
    server = FastMCP(
        "SIME Diary", instructions="Read-only access to an authorized local SIME diary."
    )

    @server.tool()
    async def get_schedule(start_date: str, end_date: str) -> list[dict]:
        """Return lessons in an inclusive ISO date range (YYYY-MM-DD)."""
        lessons = await calendar.get_calendar_range(
            date.fromisoformat(start_date), date.fromisoformat(end_date)
        )
        return [item.model_dump(mode="json") for item in lessons]

    @server.tool()
    async def get_homework(start_date: str, end_date: str) -> list[dict]:
        """Return homework on lessons in an inclusive ISO date range; due dates are unknown."""
        entries = await homework.get_homework(
            date.fromisoformat(start_date), date.fromisoformat(end_date)
        )
        return [item.model_dump(mode="json") for item in entries]

    @server.tool()
    async def get_grades(start_date: str, end_date: str) -> list[dict]:
        """Return grades displayed on calendar lessons in an inclusive ISO date range."""
        entries = await grades.get_grades(
            date.fromisoformat(start_date), date.fromisoformat(end_date)
        )
        return [item.model_dump(mode="json") for item in entries]

    @server.tool()
    async def get_subjects() -> list[dict]:
        """Return unique subjects and teachers observed in the current month's calendar."""
        return [item.model_dump(mode="json") for item in await subjects.get_subjects()]

    @server.tool()
    async def get_today_schedule() -> list[dict]:
        """Return today's lessons in the Europe/Chisinau timezone."""
        today = datetime.now(MOLDOVA_TZ).date()
        return [
            item.model_dump(mode="json") for item in await calendar.get_calendar_range(today, today)
        ]

    @server.tool()
    async def get_week_schedule(week_start: str) -> list[dict]:
        """Return seven days of lessons starting on the supplied ISO date."""
        start = date.fromisoformat(week_start)
        return [
            item.model_dump(mode="json")
            for item in await calendar.get_calendar_range(start, start + timedelta(days=6))
        ]

    return server


def main() -> None:
    configure_logging()
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
