from datetime import date

from sime_mcp.models import HomeworkAssignment
from sime_mcp.services.calendar import CalendarService


class HomeworkService:
    def __init__(self, calendar: CalendarService):
        self.calendar = calendar

    async def get_homework(self, start: date, end: date) -> list[HomeworkAssignment]:
        lessons = await self.calendar.get_calendar_range(start, end)
        return [
            HomeworkAssignment(
                lesson_date=item.date,
                subject=item.subject,
                description=item.homework,
                teacher=item.teacher,
            )
            for item in lessons
            if item.homework is not None
        ]
