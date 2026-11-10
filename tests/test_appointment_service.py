from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.advising_note import AdvisingNote
from app.models.advisor import Advisor
from app.models.appointment import Appointment
from app.models.student import Student
from app.repositories.appointment import AppointmentRepository
from app.services.appointment_service import (
    AdvisorNotFoundError,
    AppointmentNotDecidableError,
    AppointmentService,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


@pytest.fixture
def service(session):
    return AppointmentService(AppointmentRepository(session))


def make_student(session: Session, *, name: str = "Bob", email: str = "bob@example.com") -> Student:
    student = Student(name=name, email=email, major="Computer Science", year=2)
    session.add(student)
    session.commit()
    session.refresh(student)
    return student


def make_advisor(session: Session, *, name: str = "Dr. Lee", email: str = "advisor@example.com") -> Advisor:
    advisor = Advisor(name=name, email=email, department="Computer Science")
    session.add(advisor)
    session.commit()
    session.refresh(advisor)
    return advisor


def make_appointment(
    session: Session,
    *,
    student: Student,
    advisor: Advisor,
    status: str = "pending",
    reason: str = "Academic planning",
    created_at: datetime | None = None,
    deleted_at: datetime | None = None,
) -> Appointment:
    appointment = Appointment(
        student_id=student.student_id,
        advisor_id=advisor.advisor_id,
        date_time=datetime(2027, 1, 15, 10, 0),
        reason=reason,
        status=status,
        created_at=created_at,
        deleted_at=deleted_at,
    )
    session.add(appointment)
    session.commit()
    session.refresh(appointment)
    return appointment


def test_book_for_student_email_creates_pending_appointment(session, service):
    student = make_student(session, email="bob@example.com")
    advisor = make_advisor(session, email="advisor@example.com")

    appointment = service.book_for_student_email(
        student_email=student.email,
        advisor_id=advisor.advisor_id,
        date_time=datetime(2027, 2, 1, 9, 30),
        reason="Need help choosing electives.",
    )

    assert appointment.appointment_id is not None
    assert appointment.status == "pending"
    assert appointment.student_id == student.student_id
    assert appointment.advisor_id == advisor.advisor_id
    assert appointment.reason == "Need help choosing electives."


def test_book_for_student_email_raises_for_missing_advisor(session, service):
    student = make_student(session, email="bob@example.com")

    with pytest.raises(AdvisorNotFoundError):
        service.book_for_student_email(
            student_email=student.email,
            advisor_id=999,
            date_time=datetime(2027, 2, 1, 9, 30),
            reason="Need help choosing electives.",
        )


def test_decide_for_advisor_email_updates_status_and_creates_note(session, service):
    student = make_student(session, email="student@example.com")
    advisor = make_advisor(session, email="advisor@example.com")
    appointment = make_appointment(session, student=student, advisor=advisor)

    service.decide_for_advisor_email(
        advisor_email=advisor.email,
        appointment_id=appointment.appointment_id,
        decision="deny",
        denial_note="You do not meet the prerequisite.",
    )

    updated = session.get(Appointment, appointment.appointment_id)
    assert updated is not None
    assert updated.status == "denied"

    note = session.exec(
        select(AdvisingNote).where(AdvisingNote.appointment_id == appointment.appointment_id)
    ).one()
    assert note.content == "You do not meet the prerequisite."


def test_decide_for_advisor_email_requires_note_for_denial(session, service):
    student = make_student(session, email="student@example.com")
    advisor = make_advisor(session, email="advisor@example.com")
    appointment = make_appointment(session, student=student, advisor=advisor)

    with pytest.raises(AppointmentNotDecidableError):
        service.decide_for_advisor_email(
            advisor_email=advisor.email,
            appointment_id=appointment.appointment_id,
            decision="deny",
            denial_note="   ",
        )


def test_get_history_for_student_email_returns_resolved_appointments_only(session, service):
    student = make_student(session, email="bob@example.com")
    advisor = make_advisor(session, email="advisor@example.com")
    make_appointment(session, student=student, advisor=advisor, status="approved")
    make_appointment(session, student=student, advisor=advisor, status="denied")
    make_appointment(session, student=student, advisor=advisor, status="pending")

    found_student, appointments = service.get_history_for_student_email(student.email)

    assert found_student.student_id == student.student_id
    assert len(appointments) == 2
    assert {appointment.status for appointment, _ in appointments} == {"approved", "denied"}


def test_delete_for_student_email_soft_deletes_owned_appointment(session, service):
    student = make_student(session, email="bob@example.com")
    advisor = make_advisor(session, email="advisor@example.com")
    appointment = make_appointment(session, student=student, advisor=advisor)

    service.delete_for_student_email(student_email=student.email, appointment_id=appointment.appointment_id)

    assert session.get(Appointment, appointment.appointment_id).deleted_at is not None
    assert service.appointment_repo.get_pending_for_student(student.student_id) == []
    deleted = service.appointment_repo.get_deleted_for_student(student.student_id)
    assert deleted[0][0].appointment_id == appointment.appointment_id


def test_restore_for_student_email_restores_recent_deleted_appointment(session, service):
    student = make_student(session, email="bob@example.com")
    advisor = make_advisor(session, email="advisor@example.com")
    appointment = make_appointment(
        session,
        student=student,
        advisor=advisor,
        deleted_at=datetime.now() - timedelta(days=1),
    )

    service.restore_for_student_email(
        student_email=student.email,
        appointment_id=appointment.appointment_id,
    )

    restored = session.get(Appointment, appointment.appointment_id)
    assert restored is not None
    assert restored.deleted_at is None


def test_get_deleted_history_for_student_email_purges_expired_deleted_records(session, service):
    student = make_student(session, email="bob@example.com")
    advisor = make_advisor(session, email="advisor@example.com")
    expired = make_appointment(
        session,
        student=student,
        advisor=advisor,
        deleted_at=datetime.now() - timedelta(days=8),
    )
    expired_id = expired.appointment_id
    recent = make_appointment(
        session,
        student=student,
        advisor=advisor,
        deleted_at=datetime.now() - timedelta(days=1),
    )

    _, appointments = service.get_deleted_history_for_student_email(student.email)

    remaining = session.exec(
        select(Appointment).where(Appointment.appointment_id == expired_id)
    ).one_or_none()
    assert remaining is None
    assert len(appointments) == 1
    assert appointments[0][0].appointment_id == recent.appointment_id


def test_get_pending_for_advisor_email_only_returns_pending_requests_for_that_advisor(session, service):
    student_1 = make_student(session, name="Alice", email="alice@example.com")
    student_2 = make_student(session, name="Carol", email="carol@example.com")
    advisor = make_advisor(session, email="advisor@example.com")
    other_advisor = make_advisor(session, email="other@example.com")

    make_appointment(session, student=student_1, advisor=advisor)
    make_appointment(session, student=student_2, advisor=advisor, status="approved")
    make_appointment(session, student=student_2, advisor=other_advisor)

    found_advisor, appointments = service.get_pending_for_advisor_email(advisor.email)

    assert found_advisor.advisor_id == advisor.advisor_id
    assert len(appointments) == 1
    assert appointments[0][1].student_id == student_1.student_id
