from fastapi import Request
from fastapi.responses import HTMLResponse

from app.dependencies.auth import AuthDep
from app.dependencies.session import SessionDep
from app.repositories.appointment import AppointmentRepository
from app.services.appointment_service import AppointmentService

from . import router, templates


@router.get("/app", response_class=HTMLResponse)
async def user_home_view(request: Request, user: AuthDep, db: SessionDep):
    advisors = AppointmentService(AppointmentRepository(db)).get_advisors()
    return templates.TemplateResponse(
        request=request,
        name="app.html",
        context={
            "user": user,
            "advisors": advisors,
        },
    )