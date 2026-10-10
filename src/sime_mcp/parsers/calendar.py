"""Parse SIME FullCalendar event JSON without executing embedded JavaScript."""

from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup
from pydantic import ValidationError

from sime_mcp.errors import InvalidCalendarDataError
from sime_mcp.models import Lesson


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    result = " ".join(value.split())
    return result or None


def _text(soup: BeautifulSoup, selector: str) -> str | None:
    element = soup.select_one(selector)
    return _clean(element.get_text(" ", strip=True)) if element else None


def is_calendar_event_array(value: Any) -> bool:
    """Validate response shape; an empty array is valid only after request matching."""
    return isinstance(value, list) and all(
        isinstance(item, dict)
        and isinstance(item.get("title"), str)
        and isinstance(item.get("start"), str)
        for item in value
    )


def parse_calendar_events(events: Any) -> list[Lesson]:
    if not is_calendar_event_array(events):
        raise InvalidCalendarDataError("Calendar response is not an event array.")

    lessons: list[Lesson] = []
    seen: set[tuple] = set()
    for event in events:
        title = event["title"]
        soup = BeautifulSoup(title, "html.parser")
        if soup.select_one(".lesson-card") is None:
            continue  # Other FullCalendar event types are outside this parser's scope.

        subject = _text(soup, ".lesson-text-wrap")
        if not subject:
            continue  # A malformed lesson card cannot be represented meaningfully.
        try:
            start = datetime.fromisoformat(event["start"])
            end = datetime.fromisoformat(event["end"])
            order = _text(soup, ".lesson-order")
            number = int(order) if order and order.isdecimal() else None
            # Event timestamps are authoritative; HTML times are display text only.
            lesson = Lesson(
                date=start.date(),
                subject=subject,
                lesson_number=number,
                start_time=start.time().replace(tzinfo=None),
                end_time=end.time().replace(tzinfo=None),
                teacher=_text(soup, ".lesson-teacher"),
                room=_text(soup, ".lesson-room"),
                homework=_text(soup, ".lesson-homework"),
                grades=[
                    value
                    for element in soup.select(".lesson-grade")
                    if (value := _clean(element.get_text(" ", strip=True))) is not None
                ],
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise InvalidCalendarDataError("A lesson event has invalid date or time data.") from exc
        key = (lesson.date, lesson.lesson_number, lesson.subject, lesson.start_time)
        if key not in seen:
            seen.add(key)
            lessons.append(lesson)
    return sorted(lessons, key=lambda item: (item.date, item.start_time, item.lesson_number or 0))
