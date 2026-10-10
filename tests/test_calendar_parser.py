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


def test_duplicate_and_unknown_event(events):
    events.append(events[0])
    events.append({"title": "<div>Holiday</div>", "start": "2026-10-08"})
    assert len(parse_calendar_events(events)) == 2


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
