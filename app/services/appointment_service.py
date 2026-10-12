from datetime import datetime, timedelta, timezone

from app.models.advisor import Advisor
from app.models.appointment import Appointment
from app.models.student import Student
from app.repositories.appointment import AppointmentRepository


class BookingProfileNotFoundError(ValueError):
    """Raised when the signed-in account has no matching booking profile."""


class AdvisorNotFoundError(ValueError):
    """Raised when the requested advisor does not exist."""


class AppointmentNotDeletableError(ValueError):
    """Raised when the appointment cannot be deleted or restored."""


class AppointmentNotDecidableError(ValueError):
    """Raised when an advisor cannot apply the requested appointment decision."""


def _retention_cutoff() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)


class AppointmentService:
    def __init__(self, appointment_repo: AppointmentRepository):
        self.appointment_repo = appointment_repo

    def get_advisors(self) -> list[Advisor]:
        return self.appointment_repo.get_advisors()

    def get_pending_for_advisor_email(
        self, advisor_email: str
    ) -> tuple[Advisor, list[tuple[Appointment, Student]]]:
        advisor = self.appointment_repo.get_advisor_by_email(advisor_email)
        if advisor is None or advisor.advisor_id is None:
            raise AppointmentNotDecidableError(
                "No advisor profile is registered for your signed-in email."
            )

        appointments = self.appointment_repo.get_pending_for_advisor(
            advisor.advisor_id
        )
        return advisor, appointments

    def get_history_for_advisor_email(
        self, advisor_email: str
    ) -> tuple[Advisor, list[tuple[Appointment, Student]]]:
        advisor = self.appointment_repo.get_advisor_by_email(advisor_email)
        if advisor is None or advisor.advisor_id is None:
            raise AppointmentNotDecidableError(
                "No advisor profile is registered for your signed-in email."
            )

        appointments = self.appointment_repo.get_resolved_for_advisor(
            advisor.advisor_id
        )
        return advisor, appointments

    def get_history_for_student_email(
        self, student_email: str
    ) -> tuple[Student, list[tuple[Appointment, Advisor]]]:
        student = self.appointment_repo.get_student_by_email(student_email)
        if student is None or student.student_id is None:
            raise BookingProfileNotFoundError(
                "No student profile is registered for your signed-in email."
            )

        appointments = self.appointment_repo.get_for_student(student.student_id)
        return student, appointments

    def get_pending_for_student_email(
        self, student_email: str
    ) -> tuple[Student, list[tuple[Appointment, Advisor]]]:
        student = self.appointment_repo.get_student_by_email(student_email)
        if student is None or student.student_id is None:
            raise BookingProfileNotFoundError(
                "No student profile is registered for your signed-in email."
            )

        appointments = self.appointment_repo.get_pending_for_student(
            student.student_id
        )
        return student, appointments

    def get_deleted_history_for_student_email(
        self, student_email: str
    ) -> tuple[Student, list[tuple[Appointment, Advisor]]]:
        student = self.appointment_repo.get_student_by_email(student_email)
        if student is None or student.student_id is None:
            raise BookingProfileNotFoundError(
                "No student profile is registered for your signed-in email."
            )

        self.appointment_repo.purge_expired_deleted_for_student(
            student.student_id, _retention_cutoff()
        )
        appointments = self.appointment_repo.get_deleted_for_student(
            student.student_id
        )
        return student, appointments

    def delete_for_student_email(
        self, *, student_email: str, appointment_id: int
    ) -> None:
        student = self.appointment_repo.get_student_by_email(student_email)
        if student is None or student.student_id is None:
            raise BookingProfileNotFoundError(
                "No student profile is registered for your signed-in email."
            )

        deleted = self.appointment_repo.soft_delete_for_student(
            appointment_id=appointment_id,
            student_id=student.student_id,
            deleted_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        if not deleted:
            raise AppointmentNotDeletableError(
                "That appointment could not be deleted. Check that it belongs to you."
            )

    def restore_for_student_email(
        self, *, student_email: str, appointment_id: int
    ) -> None:
        student = self.appointment_repo.get_student_by_email(student_email)
        if student is None or student.student_id is None:
            raise BookingProfileNotFoundError(
                "No student profile is registered for your signed-in email."
            )

        cutoff = _retention_cutoff()
        self.appointment_repo.purge_expired_deleted_for_student(
            student.student_id, cutoff
        )
        restored = self.appointment_repo.restore_for_student(
            appointment_id=appointment_id,
            student_id=student.student_id,
            cutoff=cutoff,
        )
        if not restored:
            raise AppointmentNotDeletableError(
                "That appointment is no longer available to restore."
            )

    def decide_for_advisor_email(
        self,
        *,
        advisor_email: str,
        appointment_id: int,
        decision: str,
        denial_note: str = "",
    ) -> None:
        advisor = self.appointment_repo.get_advisor_by_email(advisor_email)
        if advisor is None or advisor.advisor_id is None:
            raise AppointmentNotDecidableError(
                "No advisor profile is registered for your signed-in email."
            )

        if decision not in ("approve", "deny"):
            raise AppointmentNotDecidableError("Invalid decision.")

        status = "approved" if decision == "approve" else "denied"
        normalized_note = denial_note.strip()
        if status == "denied" and not normalized_note:
            raise AppointmentNotDecidableError(
                "Add a note explaining why you are denying this request."
            )

        updated = self.appointment_repo.set_pending_status_for_advisor(
            appointment_id=appointment_id,
            advisor_id=advisor.advisor_id,
            status=status,
            denial_note=normalized_note if status == "denied" else None,
        )
        if not updated:
            raise AppointmentNotDecidableError(
                "That request is not available to you, or it is no longer pending."
            )

    def book_for_student_email(
        self,
        *,
        student_email: str,
        advisor_id: int,
        date_time: datetime,
        reason: str,
    ) -> Appointment:
        student = self.appointment_repo.get_student_by_email(student_email)
        if student is None or student.student_id is None:
            raise BookingProfileNotFoundError(
                "No student profile is registered for your signed-in email."
            )

        advisor = self.appointment_repo.get_advisor_by_id(advisor_id)
        if advisor is None or advisor.advisor_id is None:
            raise AdvisorNotFoundError("The selected advisor could not be found.")

        return self.appointment_repo.create(
            student_id=student.student_id,
            advisor_id=advisor.advisor_id,
            date_time=date_time,
            reason=reason,
        )
