from datetime import date

from sime_mcp.models import LessonGrade
from sime_mcp.services.calendar import CalendarService


class GradeService:
    def __init__(self, calendar: CalendarService):
        self.calendar = calendar

    async def get_grades(self, start: date, end: date) -> list[LessonGrade]:
        lessons = await self.calendar.get_calendar_range(start, end)
        return [
            LessonGrade(
                lesson_date=item.date,
                subject=item.subject,
                grade=grade,
                lesson_number=item.lesson_number,
                teacher=item.teacher,
            )
            for item in lessons
            for grade in item.grades
        ]
