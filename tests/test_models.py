from datetime import date, time

import pytest
from pydantic import ValidationError

from sime_mcp.errors import UnsupportedDateRangeError
from sime_mcp.models import HomeworkAssignment, Lesson
from sime_mcp.services.calendar import _months


def test_homework_has_no_invented_due_date():
    item = HomeworkAssignment(lesson_date=date(2026, 10, 8), subject="Biologie", description="Read")
    assert item.due_date is None
    assert item.model_dump(mode="json")["lesson_date"] == "2026-10-08"


def test_lesson_rejects_extra_sensitive_fields():
    with pytest.raises(ValidationError):
        Lesson(
            date=date(2026, 10, 8),
            subject="Math",
            start_time=time(8),
            end_time=time(9),
            cookie="secret",
        )


def test_date_range_month_rollover():
    assert _months(date(2026, 12, 31), date(2027, 1, 1)) == [(2026, 12), (2027, 1)]


def test_date_range_rejects_reverse():
    with pytest.raises(UnsupportedDateRangeError):
        _months(date(2026, 10, 11), date(2026, 10, 10))
