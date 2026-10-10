"""Month snapshots and changes, storing only normalized educational records."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sime_mcp.config import make_private_dir
from sime_mcp.models import Lesson


def _identity(lesson: Lesson) -> str:
    # Slot identity catches subject/time changes as updates. Insertions or
    # renumbering may appear as remove/add pairs; see README.
    return f"{lesson.date.isoformat()}:{lesson.lesson_number or lesson.start_time.isoformat()}"


class CalendarStore:
    def __init__(self, path: Path):
        self.path = path
        make_private_dir(path.parent)
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    month TEXT PRIMARY KEY, retrieved_at TEXT NOT NULL, lessons_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS changes (
                    id INTEGER PRIMARY KEY, month TEXT NOT NULL, detected_at TEXT NOT NULL,
                    kind TEXT NOT NULL, old_json TEXT, new_json TEXT
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        if self.path.exists():
            self.path.chmod(0o600)
        return db

    def read(self, year: int, month: int, ttl_seconds: int | None = None) -> list[Lesson] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT retrieved_at, lessons_json FROM snapshots WHERE month = ?",
                (f"{year:04d}-{month:02d}",),
            ).fetchone()
        if not row:
            return None
        stamp = datetime.fromisoformat(row[0])
        if ttl_seconds is not None and datetime.now(UTC) - stamp > timedelta(seconds=ttl_seconds):
            return None
        return [Lesson.model_validate(item) for item in json.loads(row[1])]

    def save(self, year: int, month: int, lessons: list[Lesson]) -> None:
        key = f"{year:04d}-{month:02d}"
        now = datetime.now(UTC).isoformat()
        old = self.read(year, month)
        before = {_identity(item): item for item in old or []}
        after = {_identity(item): item for item in lessons}
        with self._connect() as db:
            if old is not None:
                for identity in sorted(before.keys() | after.keys()):
                    prior, new = before.get(identity), after.get(identity)
                    if prior == new:
                        continue
                    kind = "added" if prior is None else "removed" if new is None else "updated"
                    db.execute(
                        "INSERT INTO changes(month, detected_at, kind, old_json, new_json) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            key,
                            now,
                            kind,
                            prior.model_dump_json() if prior else None,
                            new.model_dump_json() if new else None,
                        ),
                    )
            db.execute(
                "INSERT INTO snapshots(month, retrieved_at, lessons_json) VALUES (?, ?, ?) "
                "ON CONFLICT(month) DO UPDATE SET retrieved_at=excluded.retrieved_at, "
                "lessons_json=excluded.lessons_json",
                (
                    key,
                    now,
                    json.dumps(
                        [item.model_dump(mode="json") for item in lessons], ensure_ascii=False
                    ),
                ),
            )

    def changes(self, limit: int = 100) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT month, detected_at, kind, old_json, new_json FROM changes "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "month": row[0],
                "detected_at": row[1],
                "kind": row[2],
                "before": json.loads(row[3]) if row[3] else None,
                "after": json.loads(row[4]) if row[4] else None,
            }
            for row in rows
        ]

    def clear(self) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM changes")
            db.execute("DELETE FROM snapshots")
