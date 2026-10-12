from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel

from app.models.advising_note import AdvisingNote
from app.models.advisor import Advisor
from app.models.student import Student


class Appointment(SQLModel, table=True):
    appointment_id: int | None = Field(default=None, primary_key=True)
    date_time: datetime
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    status: str = Field(default="pending", max_length=10)
    reason: str
    deleted_at: datetime | None = Field(default=None)
    student_id: int = Field(foreign_key="student.student_id")
    advisor_id: int = Field(foreign_key="advisor.advisor_id")
    student: Student = Relationship()
    advisor: Advisor = Relationship()
    advising_notes: list[AdvisingNote] = Relationship()