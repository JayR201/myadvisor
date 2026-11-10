from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.database import get_session
from app.dependencies import auth as auth_module
from app.main import app
from app.models.advisor import Advisor
from app.models.appointment import Appointment
from app.models.student import Student
from app.models.user import User


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine):
    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_student(session: Session, *, name: str, email: str) -> Student:
    student = Student(name=name, email=email, major="Computer Science", year=2)
    session.add(student)
    session.commit()
    session.refresh(student)
    return student


def make_advisor(session: Session, *, name: str, email: str) -> Advisor:
    advisor = Advisor(name=name, email=email, department="Computer Science")
    session.add(advisor)
    session.commit()
    session.refresh(advisor)
    return advisor


def make_user(*, username: str, email: str, role: str = "regular_user") -> User:
    return User(username=username, email=email, password="secret", role=role)


def test_book_appointment_route_creates_pending_request(client, db_session):
    student = make_student(db_session, name="Bob", email="bob@example.com")
    advisor = make_advisor(db_session, name="Dr. Lee", email="advisor@example.com")
    user = make_user(username="bob", email=student.email, role="regular_user")

    async def override_get_current_user():
        return user

    app.dependency_overrides[auth_module.get_current_user] = override_get_current_user

    response = client.post(
        "/appointments/book",
        data={
            "advisor_id": str(advisor.advisor_id),
            "appointment_date": "2027-02-01",
            "appointment_time": "09:30",
            "reason": "Need help choosing electives.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    with Session(db_session.get_bind()) as verify_session:
        created = verify_session.exec(
            select(Appointment).where(Appointment.student_id == student.student_id)
        ).all()
    assert len(created) == 1
    assert created[0].status == "pending"
    assert created[0].advisor_id == advisor.advisor_id


def test_student_history_route_returns_resolved_appointments(client, db_session):
    student = make_student(db_session, name="Bob", email="bob@example.com")
    advisor = make_advisor(db_session, name="Dr. Lee", email="advisor@example.com")
    user = make_user(username="bob", email=student.email, role="regular_user")

    ap_approved = Appointment(
        student_id=student.student_id,
        advisor_id=advisor.advisor_id,
        date_time=datetime(2027, 2, 3, 10, 0),
        reason="Approved request",
        status="approved",
    )
    ap_pending = Appointment(
        student_id=student.student_id,
        advisor_id=advisor.advisor_id,
        date_time=datetime(2027, 2, 4, 11, 0),
        reason="Pending request",
        status="pending",
    )
    db_session.add_all([ap_approved, ap_pending])
    db_session.commit()

    async def override_get_current_user():
        return user

    app.dependency_overrides[auth_module.get_current_user] = override_get_current_user

    response = client.get("/appointments/history")
    assert response.status_code == 200
    assert "Approved request" in response.text
    assert "Pending request" not in response.text


def test_advisor_dashboard_route_shows_pending_requests_for_that_advisor(client, db_session):
    student = make_student(db_session, name="Alice", email="alice@example.com")
    advisor = make_advisor(db_session, name="Dr. Lee", email="advisor@example.com")
    other_advisor = make_advisor(db_session, name="Dr. Smith", email="other@example.com")
    user = make_user(username="advisor", email=advisor.email, role="advisor")

    ap_own = Appointment(
        student_id=student.student_id,
        advisor_id=advisor.advisor_id,
        date_time=datetime(2027, 2, 5, 12, 0),
        reason="Needs advice",
        status="pending",
    )
    ap_other = Appointment(
        student_id=student.student_id,
        advisor_id=other_advisor.advisor_id,
        date_time=datetime(2027, 2, 6, 12, 0),
        reason="Other advisor request",
        status="pending",
    )
    db_session.add_all([ap_own, ap_other])
    db_session.commit()

    async def override_get_current_user():
        return user

    app.dependency_overrides[auth_module.get_current_user] = override_get_current_user

    response = client.get("/advisor/appointments")
    assert response.status_code == 200
    assert "Needs advice" in response.text
    assert "Other advisor request" not in response.text


def test_decide_appointment_route_updates_status_and_redirects(client, db_session):
    student = make_student(db_session, name="Alice", email="alice@example.com")
    advisor = make_advisor(db_session, name="Dr. Lee", email="advisor@example.com")
    user = make_user(username="advisor", email=advisor.email, role="advisor")
    appointment = Appointment(
        student_id=student.student_id,
        advisor_id=advisor.advisor_id,
        date_time=datetime(2027, 2, 7, 15, 0),
        reason="Please approve",
        status="pending",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    async def override_get_current_user():
        return user

    app.dependency_overrides[auth_module.get_current_user] = override_get_current_user

    response = client.post(
        f"/advisor/appointments/{appointment.appointment_id}/decision",
        data={
            "decision": "approve",
            "denial_note": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    with Session(db_session.get_bind()) as verify_session:
        refreshed = verify_session.get(Appointment, appointment.appointment_id)
    assert refreshed is not None
    assert refreshed.status == "approved"
