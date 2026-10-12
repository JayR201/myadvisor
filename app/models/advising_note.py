from datetime import datetime

from sqlmodel import Field, SQLModel


class AdvisingNote(SQLModel, table=True):
    note_id: int | None = Field(default=None, primary_key=True)
    content: str
    date_created: datetime = Field(default_factory=datetime.utcnow)
    appointment_id: int = Field(foreign_key="appointment.appointment_id")
