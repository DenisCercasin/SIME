"""Calendar retrieval and inclusive date-range filtering."""

from calendar import monthrange
from datetime import date

from sime_mcp.browser.calendar_capture import capture_calendar_month
from sime_mcp.browser.session import browser_context, resume_diary_url
from sime_mcp.config import Settings
from sime_mcp.errors import UnsupportedDateRangeError
from sime_mcp.models import CalendarMonth, Lesson
from sime_mcp.parsers.calendar import parse_calendar_events
from sime_mcp.storage.database import CalendarStore


def _months(start: date, end: date) -> list[tuple[int, int]]:
    if end < start:
        raise UnsupportedDateRangeError("End date must be on or after start date.")
    count = (end.year - start.year) * 12 + end.month - start.month + 1
    if count > 12:
        raise UnsupportedDateRangeError("Date ranges are limited to 12 calendar months.")
    return [
        (start.year + (start.month - 1 + offset) // 12, (start.month - 1 + offset) % 12 + 1)
        for offset in range(count)
    ]


class CalendarService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = CalendarStore(settings.database_path) if settings.cache_enabled else None

    async def get_calendar_month(
        self, year: int, month: int, *, refresh: bool = False
    ) -> CalendarMonth:
        monthrange(year, month)  # Validate month early.
        if self.store and not refresh:
            cached = self.store.read(year, month, self.settings.cache_ttl_seconds)
            if cached is not None:
                return CalendarMonth(year=year, month=month, lessons=cached)
        async with browser_context(self.settings) as context:
            page = context.pages[0] if context.pages else await context.new_page()
            events = await capture_calendar_month(
                page,
                year,
                month,
                self.settings.browser_timeout_ms,
                source_url=resume_diary_url(self.settings),
            )
        lessons = parse_calendar_events(events)
        lessons = [item for item in lessons if item.date.year == year and item.date.month == month]
        if self.store:
            self.store.save(year, month, lessons)
        return CalendarMonth(year=year, month=month, lessons=lessons)

    async def get_calendar_range(self, start: date, end: date) -> list[Lesson]:
        months = _months(start, end)
        lessons: list[Lesson] = []
        for year, month in months:
            result = await self.get_calendar_month(year, month)
            lessons.extend(item for item in result.lessons if start <= item.date <= end)
        return sorted(lessons, key=lambda item: (item.date, item.start_time))
