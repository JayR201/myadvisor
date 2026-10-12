import logging
from datetime import datetime

from sqlmodel import Session, delete, select

from app.models.advising_note import AdvisingNote
from app.models.advisor import Advisor
from app.models.appointment import Appointment
from app.models.student import Student

logger = logging.getLogger(__name__)


class AppointmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_student_by_email(self, email: str) -> Student | None:
        statement = select(Student).where(Student.email == email)
        return self.db.exec(statement).one_or_none()

    def get_advisor_by_id(self, advisor_id: int) -> Advisor | None:
        return self.db.get(Advisor, advisor_id)

    def get_advisor_by_email(self, email: str) -> Advisor | None:
        statement = select(Advisor).where(Advisor.email == email)
        return self.db.exec(statement).one_or_none()

    def get_advisors(self) -> list[Advisor]:
        statement = select(Advisor).order_by(Advisor.name)
        return self.db.exec(statement).all()

    def get_for_student(
        self, student_id: int
    ) -> list[tuple[Appointment, Advisor]]:
        statement = (
            select(Appointment, Advisor)
            .join(Advisor, Appointment.advisor_id == Advisor.advisor_id)
            .where(Appointment.student_id == student_id)
            .where(Appointment.status.in_(["approved", "denied"]))
            .where(Appointment.deleted_at.is_(None))
            .order_by(
                Appointment.created_at.desc().nullslast(),
                Appointment.appointment_id.desc(),
            )
        )
        return self.db.exec(statement).all()

    def get_pending_for_student(
        self, student_id: int
    ) -> list[tuple[Appointment, Advisor]]:
        statement = (
            select(Appointment, Advisor)
            .join(Advisor, Appointment.advisor_id == Advisor.advisor_id)
            .where(Appointment.student_id == student_id)
            .where(Appointment.status == "pending")
            .where(Appointment.deleted_at.is_(None))
            .order_by(
                Appointment.created_at.desc().nullslast(),
                Appointment.appointment_id.desc(),
            )
        )
        return self.db.exec(statement).all()

    def get_deleted_for_student(
        self, student_id: int
    ) -> list[tuple[Appointment, Advisor]]:
        statement = (
            select(Appointment, Advisor)
            .join(Advisor, Appointment.advisor_id == Advisor.advisor_id)
            .where(Appointment.student_id == student_id)
            .where(Appointment.deleted_at.is_not(None))
            .order_by(Appointment.deleted_at.desc())
        )
        return self.db.exec(statement).all()

    def get_pending_for_advisor(
        self, advisor_id: int
    ) -> list[tuple[Appointment, Student]]:
        statement = (
            select(Appointment, Student)
            .join(Student, Appointment.student_id == Student.student_id)
            .where(Appointment.advisor_id == advisor_id)
            .where(Appointment.status == "pending")
            .where(Appointment.deleted_at.is_(None))
            .order_by(Appointment.date_time)
        )
        return self.db.exec(statement).all()

    def get_resolved_for_advisor(
        self, advisor_id: int
    ) -> list[tuple[Appointment, Student]]:
        statement = (
            select(Appointment, Student)
            .join(Student, Appointment.student_id == Student.student_id)
            .where(Appointment.advisor_id == advisor_id)
            .where(Appointment.status.in_(["approved", "denied"]))
            .where(Appointment.deleted_at.is_(None))
            .order_by(
                Appointment.created_at.desc().nullslast(),
                Appointment.appointment_id.desc(),
            )
        )
        return self.db.exec(statement).all()

    def soft_delete_for_student(
        self, appointment_id: int, student_id: int, deleted_at: datetime
    ) -> bool:
        statement = select(Appointment).where(
            Appointment.appointment_id == appointment_id,
            Appointment.student_id == student_id,
            Appointment.status.in_(["pending", "approved", "denied"]),
            Appointment.deleted_at.is_(None),
        )
        appointment = self.db.exec(statement).one_or_none()
        if appointment is None:
            return False

        try:
            appointment.deleted_at = deleted_at
            self.db.commit()
            return True
        except Exception:
            logger.exception("Failed to delete an advising appointment")
            self.db.rollback()
            raise

    def restore_for_student(
        self, appointment_id: int, student_id: int, cutoff: datetime
    ) -> bool:
        statement = select(Appointment).where(
            Appointment.appointment_id == appointment_id,
            Appointment.student_id == student_id,
            Appointment.deleted_at > cutoff,
        )
        appointment = self.db.exec(statement).one_or_none()
        if appointment is None:
            return False

        try:
            appointment.deleted_at = None
            self.db.commit()
            return True
        except Exception:
            logger.exception("Failed to restore an advising appointment")
            self.db.rollback()
            raise

    def purge_expired_deleted_for_student(
        self, student_id: int, cutoff: datetime
    ) -> None:
        statement = delete(Appointment).where(
            Appointment.student_id == student_id,
            Appointment.deleted_at <= cutoff,
        )
        try:
            self.db.exec(statement)
            self.db.commit()
        except Exception:
            logger.exception("Failed to purge expired advising appointments")
            self.db.rollback()
            raise

    def set_pending_status_for_advisor(
        self,
        appointment_id: int,
        advisor_id: int,
        status: str,
        denial_note: str | None = None,
    ) -> bool:
        statement = select(Appointment).where(
            Appointment.appointment_id == appointment_id,
            Appointment.advisor_id == advisor_id,
            Appointment.status == "pending",
            Appointment.deleted_at.is_(None),
        )
        appointment = self.db.exec(statement).one_or_none()
        if appointment is None:
            return False

        try:
            appointment.status = status
            self.db.add(appointment)
            if status == "denied" and denial_note is not None:
                self.db.add(
                    AdvisingNote(
                        content=denial_note,
                        appointment_id=appointment_id,
                    )
                )
            self.db.commit()
            return True
        except Exception:
            logger.exception("Failed to update an advising appointment decision")
            self.db.rollback()
            raise

    def create(
        self,
        *,
        student_id: int,
        advisor_id: int,
        date_time: datetime,
        reason: str,
    ) -> Appointment:
        appointment = Appointment(
            student_id=student_id,
            advisor_id=advisor_id,
            date_time=date_time,
            reason=reason,
        )
        try:
            self.db.add(appointment)
            self.db.commit()
            self.db.refresh(appointment)
            return appointment
        except Exception:
            logger.exception("Failed to save an advising appointment")
            self.db.rollback()
            raise
