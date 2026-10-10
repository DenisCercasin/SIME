"""Public data contracts. Original event URLs and HTML never enter these models."""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Lesson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    subject: str = Field(min_length=1)
    lesson_number: int | None = Field(default=None, ge=1)
    start_time: time
    end_time: time
    teacher: str | None = None
    room: str | None = None
    homework: str | None = None

    @model_validator(mode="after")
    def valid_times(self) -> "Lesson":
        if self.end_time <= self.start_time:
            raise ValueError("lesson end must be after start")
        return self


class HomeworkAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesson_date: date
    subject: str
    description: str
    teacher: str | None = None
    source: str = "calendar"
    due_date: date | None = None


class CalendarMonth(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)
    lessons: list[Lesson]
    retrieved_at: datetime | None = None


class Subject(BaseModel):
    name: str
    teacher: str | None = None
