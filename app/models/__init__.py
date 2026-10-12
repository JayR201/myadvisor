"""Database table models.

Import every table model here so ``SQLModel.metadata.create_all`` sees them.
"""

from app.models.advising_note import AdvisingNote
from app.models.advisor import Advisor
from app.models.appointment import Appointment
from app.models.student import Student
from app.models.user import User

__all__ = ["AdvisingNote", "Advisor", "Appointment", "Student", "User"]
