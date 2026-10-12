from datetime import date, datetime, time
from typing import Annotated

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies.auth import AuthDep
from app.dependencies.session import SessionDep
from app.repositories.appointment import AppointmentRepository
from app.services.appointment_service import (
    AdvisorNotFoundError,
    AppointmentNotDecidableError,
    AppointmentNotDeletableError,
    AppointmentService,
    BookingProfileNotFoundError,
)
from app.utilities.flash import flash

from . import router, templates


@router.post("/appointments/book", name="book_appointment")
def book_appointment(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    advisor_id: Annotated[int, Form()],
    appointment_date: Annotated[date, Form()],
    appointment_time: Annotated[time, Form()],
    reason: Annotated[str, Form()],
):
    try:
        service = AppointmentService(AppointmentRepository(db))
        appointment = service.book_for_student_email(
            student_email=user.email,
            advisor_id=advisor_id,
            date_time=datetime.combine(appointment_date, appointment_time),
            reason=reason,
        )
        flash(
            request,
            "Your advising session request was submitted and is pending advisor approval.",
            "success",
        )
        return RedirectResponse(
            url=request.url_for("student_pending_appointments").include_query_params(
                latest_appointment_id=appointment.appointment_id
            ),
            status_code=303,
        )
    except (AdvisorNotFoundError, BookingProfileNotFoundError) as e:
        flash(request, str(e), "danger")

    return RedirectResponse(
        url=request.url_for("user_home_view"),
        status_code=303,
    )


@router.get(
    "/appointments/history",
    name="appointment_history",
    response_class=HTMLResponse,
)
def appointment_history(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    service = AppointmentService(AppointmentRepository(db))
    try:
        student, appointments = service.get_history_for_student_email(user.email)
    except BookingProfileNotFoundError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(
            url=request.url_for("user_home_view"),
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="appointments/history.html",
        context={
            "appointments": appointments,
            "student": student,
            "user": user,
        },
    )


@router.get(
    "/appointments/pending",
    name="student_pending_appointments",
    response_class=HTMLResponse,
)
def student_pending_appointments(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    latest_appointment_id: int | None = None,
):
    service = AppointmentService(AppointmentRepository(db))
    try:
        student, appointments = service.get_pending_for_student_email(user.email)
    except BookingProfileNotFoundError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(
            url=request.url_for("user_home_view"),
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="appointments/pending.html",
        context={
            "appointments": appointments,
            "latest_appointment_id": latest_appointment_id,
            "student": student,
            "user": user,
        },
    )


@router.post("/appointments/{appointment_id}/delete", name="delete_appointment")
def delete_appointment(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    appointment_id: int,
    return_to: Annotated[str, Form()] = "history",
):
    service = AppointmentService(AppointmentRepository(db))
    try:
        service.delete_for_student_email(
            student_email=user.email,
            appointment_id=appointment_id,
        )
        flash(request, "The advising appointment was moved to the recycle bin.", "success")
    except (AppointmentNotDeletableError, BookingProfileNotFoundError) as exc:
        flash(request, str(exc), "danger")

    destination = (
        "student_pending_appointments"
        if return_to == "pending"
        else "appointment_history"
    )
    return RedirectResponse(
        url=request.url_for(destination),
        status_code=303,
    )


@router.get(
    "/appointments/trash",
    name="appointment_trash",
    response_class=HTMLResponse,
)
def appointment_trash(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    service = AppointmentService(AppointmentRepository(db))
    try:
        student, appointments = service.get_deleted_history_for_student_email(user.email)
    except BookingProfileNotFoundError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(
            url=request.url_for("user_home_view"),
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="appointments/trash.html",
        context={
            "appointments": appointments,
            "student": student,
            "user": user,
        },
    )


@router.post(
    "/appointments/trash/{appointment_id}/restore",
    name="restore_appointment",
)
def restore_appointment(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    appointment_id: int,
):
    service = AppointmentService(AppointmentRepository(db))
    try:
        service.restore_for_student_email(
            student_email=user.email,
            appointment_id=appointment_id,
        )
        flash(request, "The advising appointment was restored.", "success")
    except (AppointmentNotDeletableError, BookingProfileNotFoundError) as exc:
        flash(request, str(exc), "danger")

    return RedirectResponse(
        url=request.url_for("appointment_trash"),
        status_code=303,
    )


@router.get(
    "/advisor/appointments",
    name="advisor_dashboard",
    response_class=HTMLResponse,
)
def advisor_dashboard(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    service = AppointmentService(AppointmentRepository(db))
    try:
        advisor, appointments = service.get_pending_for_advisor_email(user.email)
    except AppointmentNotDecidableError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(
            url=request.url_for("user_home_view"),
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="appointments/advisor_requests.html",
        context={
            "advisor": advisor,
            "appointments": appointments,
            "user": user,
        },
    )


@router.get(
    "/advisor/appointments/history",
    name="advisor_appointment_history",
    response_class=HTMLResponse,
)
def advisor_appointment_history(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    service = AppointmentService(AppointmentRepository(db))
    try:
        advisor, appointments = service.get_history_for_advisor_email(user.email)
    except AppointmentNotDecidableError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(
            url=request.url_for("user_home_view"),
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="appointments/advisor_history.html",
        context={
            "advisor": advisor,
            "appointments": appointments,
            "user": user,
        },
    )


@router.post(
    "/advisor/appointments/{appointment_id}/decision",
    name="decide_appointment",
)
def decide_appointment(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    appointment_id: int,
    decision: Annotated[str, Form()],
    denial_note: Annotated[str, Form()] = "",
):
    service = AppointmentService(AppointmentRepository(db))
    try:
        service.decide_for_advisor_email(
            advisor_email=user.email,
            appointment_id=appointment_id,
            decision=decision,
            denial_note=denial_note,
        )
        flash(request, "Appointment decision saved.", "success")
    except (AppointmentNotDecidableError, BookingProfileNotFoundError) as exc:
        flash(request, str(exc), "danger")

    return RedirectResponse(
        url=request.url_for("advisor_dashboard"),
        status_code=303,
    )