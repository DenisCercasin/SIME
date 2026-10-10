from datetime import datetime

from sime_mcp.config import MOLDOVA_TZ
from sime_mcp.models import Subject
from sime_mcp.services.calendar import CalendarService


class SubjectService:
    def __init__(self, calendar: CalendarService):
        self.calendar = calendar

    async def get_subjects(
        self, year: int | None = None, month: int | None = None
    ) -> list[Subject]:
        today = datetime.now(MOLDOVA_TZ).date()
        result = await self.calendar.get_calendar_month(year or today.year, month or today.month)
        subjects = {(item.subject, item.teacher) for item in result.lessons}
        return [
            Subject(name=name, teacher=teacher)
            for name, teacher in sorted(
                subjects, key=lambda item: (item[0].casefold(), item[1] or "")
            )
        ]
