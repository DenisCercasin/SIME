import json
from pathlib import Path

import pytest

from sime_mcp.errors import InvalidCalendarDataError
from sime_mcp.parsers.calendar import parse_calendar_events


@pytest.fixture
def events():
    return json.loads((Path(__file__).parent / "fixtures/sample_calendar.json").read_text())


def test_normal_lesson_and_homework(events):
    lesson = parse_calendar_events(events)[0]
    assert lesson.subject == "Biologie"
    assert lesson.lesson_number == 1
    assert lesson.start_time.isoformat() == "08:15:00"
    assert lesson.room == "A33"
    assert lesson.homework == "стр 12 № 3 в тетради, № 8 - по желанию"


def test_missing_homework_room_and_romanian(events):
    lesson = parse_calendar_events(events)[1]
    assert lesson.subject == "Limba română"
    assert lesson.homework is None
    assert lesson.room is None
    assert lesson.grades == ["9"]


def test_multiple_displayed_grades_are_kept_separate(events):
    events[1]["title"] = events[1]["title"].replace(
        "<span class='lesson-grade'>9</span>",
        "<span class='lesson-grade'>9</span><span class='lesson-grade'>10</span>",
    )
    assert parse_calendar_events(events)[1].grades == ["9", "10"]


def test_duplicate_and_unknown_event(events):
    events.append(events[0])
    events.append({"title": "<div>Holiday</div>", "start": "2026-10-08"})
    assert len(parse_calendar_events(events)) == 2


@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_lesson_combines_room_and_grade(events, reverse):
    graded = events[0].copy()
    graded["title"] = graded["title"].replace(
        "<span class='lesson-room'>A33</span>",
        "<span class='lesson-grade'>10</span>",
    )
    duplicates = [events[0], graded]
    lesson = parse_calendar_events(duplicates[::-1] if reverse else duplicates)[0]
    assert lesson.room == "A33"
    assert lesson.grades == ["10"]


def test_duplicate_lesson_keeps_repeated_marks(events):
    graded = events[1].copy()
    graded["title"] = graded["title"].replace(
        "<span class='lesson-grade'>9</span>",
        "<span class='lesson-grade'>9</span><span class='lesson-grade'>9</span>",
    )
    assert parse_calendar_events([events[1], graded])[0].grades == ["9", "9"]


@pytest.mark.parametrize("bad", [{}, [{"title": "x"}], [1], "not json"])
def test_malformed_response_rejected(bad):
    with pytest.raises(InvalidCalendarDataError):
        parse_calendar_events(bad)


def test_session_url_never_normalized(events):
    serialized = json.dumps(
        [item.model_dump(mode="json") for item in parse_calendar_events(events)]
    )
    assert "SECRET-CHECKSUM" not in serialized
    assert "javascript:" not in serialized
    assert "url" not in serialized
