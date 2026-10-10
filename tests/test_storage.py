from datetime import date, time

from sime_mcp.models import Lesson
from sime_mcp.storage.database import CalendarStore


def test_cache_detects_homework_update_and_clears(tmp_path):
    store = CalendarStore(tmp_path / "cache.sqlite3")
    base = dict(
        date=date(2026, 10, 8),
        subject="Biologie",
        lesson_number=1,
        start_time=time(8, 15),
        end_time=time(9),
    )
    store.save(2026, 10, [Lesson(**base)])
    store.save(2026, 10, [Lesson(**base, homework="Read chapter 2")])
    assert store.changes()[0]["kind"] == "updated"
    assert store.read(2026, 10)[0].homework == "Read chapter 2"
    store.clear()
    assert store.read(2026, 10) is None
    assert store.changes() == []
