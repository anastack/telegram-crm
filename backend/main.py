"""FastAPI — API для админ-панели."""

import os
import sys
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime, time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import joinedload

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from backend.auth import require_admin
from config.settings import RUN_BOT, WEBAPP_URL
from database.db import get_session, init_database
from database.models import Appointment, Performer, Service, User
from database.seed import seed_data


def _start_bot():
    """Запустить Telegram-бота в фоновом потоке."""
    from bot.main import run_bot

    run_bot()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_data()
    if RUN_BOT and os.getenv("BOT_TOKEN"):
        thread = threading.Thread(target=_start_bot, daemon=True)
        thread.start()
        print("Telegram-бот запущен в фоне")
    if not WEBAPP_URL:
        print("ВНИМАНИЕ: WEBAPP_URL не задан — админ-панель в Telegram недоступна")
    yield


app = FastAPI(title="CRM API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Схемы запросов ----------


class AppointmentUpdate(BaseModel):
    service_id: int | None = None
    performer_id: int | None = None
    appointment_date: date | None = None
    appointment_time: str | None = None  # "HH:MM"
    status: str | None = None


class StatusUpdate(BaseModel):
    status: str


# ---------- Вспомогательные функции ----------


def appointment_to_dict(appt: Appointment) -> dict:
    return {
        "id": appt.id,
        "user_id": appt.user_id,
        "client_name": appt.user.first_name,
        "client_username": appt.user.username,
        "client_phone": appt.user.phone,
        "service_id": appt.service_id,
        "service_name": appt.service.name,
        "service_price": appt.service.price,
        "performer_id": appt.performer_id,
        "performer_name": appt.performer.name,
        "appointment_date": appt.appointment_date.isoformat(),
        "appointment_time": appt.appointment_time.strftime("%H:%M"),
        "status": appt.status,
        "created_at": appt.created_at.isoformat() if appt.created_at else None,
    }


def get_appointment_or_404(session, appointment_id: int) -> Appointment:
    appt = (
        session.query(Appointment)
        .options(
            joinedload(Appointment.user),
            joinedload(Appointment.service),
            joinedload(Appointment.performer),
        )
        .filter_by(id=appointment_id)
        .first()
    )
    if not appt:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return appt


@app.get("/api/health")
def health():
    return {"status": "ok", "webapp_url": WEBAPP_URL}


@app.get("/api/me")
def me(admin=Depends(require_admin)):
    return {
        "id": admin.get("id"),
        "first_name": admin.get("first_name"),
        "username": admin.get("username"),
    }


@app.get("/")
def root():
    return RedirectResponse(url="/miniapp/")


@app.get("/api/dashboard")
def dashboard(admin=Depends(require_admin)):
    session = get_session()
    try:
        today = date.today()
        total_clients = session.query(User).count()
        total_appointments = session.query(Appointment).count()
        today_appointments = (
            session.query(Appointment)
            .filter(
                Appointment.appointment_date == today,
                Appointment.status == "confirmed",
            )
            .count()
        )
        upcoming = (
            session.query(Appointment)
            .options(
                joinedload(Appointment.user),
                joinedload(Appointment.service),
                joinedload(Appointment.performer),
            )
            .filter(
                Appointment.appointment_date >= today,
                Appointment.status == "confirmed",
            )
            .order_by(Appointment.appointment_date, Appointment.appointment_time)
            .limit(5)
            .all()
        )

        revenue = (
            session.query(func.sum(Service.price))
            .join(Appointment, Appointment.service_id == Service.id)
            .filter(Appointment.status == "confirmed")
            .scalar()
            or 0
        )

        return {
            "total_clients": total_clients,
            "total_appointments": total_appointments,
            "today_appointments": today_appointments,
            "revenue": revenue,
            "upcoming": [appointment_to_dict(a) for a in upcoming],
        }
    finally:
        session.close()


@app.get("/api/appointments")
def list_appointments(
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    admin=Depends(require_admin),
):
    session = get_session()
    try:
        query = (
            session.query(Appointment)
            .options(
                joinedload(Appointment.user),
                joinedload(Appointment.service),
                joinedload(Appointment.performer),
            )
            .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time)
        )
        if status:
            query = query.filter(Appointment.status == status)
        if date_from:
            query = query.filter(Appointment.appointment_date >= date_from)
        if date_to:
            query = query.filter(Appointment.appointment_date <= date_to)

        return [appointment_to_dict(a) for a in query.all()]
    finally:
        session.close()


@app.get("/api/appointments/{appointment_id}")
def get_appointment(appointment_id: int, admin=Depends(require_admin)):
    session = get_session()
    try:
        return appointment_to_dict(get_appointment_or_404(session, appointment_id))
    finally:
        session.close()


@app.put("/api/appointments/{appointment_id}")
def update_appointment(
    appointment_id: int, data: AppointmentUpdate, admin=Depends(require_admin)
):
    session = get_session()
    try:
        appt = get_appointment_or_404(session, appointment_id)

        if data.service_id is not None:
            appt.service_id = data.service_id
        if data.performer_id is not None:
            appt.performer_id = data.performer_id
        if data.appointment_date is not None:
            appt.appointment_date = data.appointment_date
        if data.appointment_time is not None:
            appt.appointment_time = datetime.strptime(
                data.appointment_time, "%H:%M"
            ).time()
        if data.status is not None:
            appt.status = data.status

        session.commit()
        session.refresh(appt)
        appt = get_appointment_or_404(session, appointment_id)
        return appointment_to_dict(appt)
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


@app.patch("/api/appointments/{appointment_id}/status")
def update_status(
    appointment_id: int, data: StatusUpdate, admin=Depends(require_admin)
):
    allowed = {"confirmed", "completed", "cancelled", "pending"}
    if data.status not in allowed:
        raise HTTPException(status_code=400, detail="Недопустимый статус")

    session = get_session()
    try:
        appt = get_appointment_or_404(session, appointment_id)
        appt.status = data.status
        session.commit()
        return appointment_to_dict(get_appointment_or_404(session, appointment_id))
    finally:
        session.close()


@app.delete("/api/appointments/{appointment_id}")
def cancel_appointment(appointment_id: int, admin=Depends(require_admin)):
    session = get_session()
    try:
        appt = get_appointment_or_404(session, appointment_id)
        appt.status = "cancelled"
        session.commit()
        return {"ok": True, "message": "Запись отменена"}
    finally:
        session.close()


@app.get("/api/clients")
def list_clients(q: str = Query(default=""), admin=Depends(require_admin)):
    session = get_session()
    try:
        query = session.query(User).order_by(User.created_at.desc())
        if q:
            like = f"%{q}%"
            query = query.filter(
                (User.first_name.ilike(like))
                | (User.last_name.ilike(like))
                | (User.username.ilike(like))
                | (User.phone.ilike(like))
            )

        clients = []
        for user in query.all():
            appt_count = (
                session.query(Appointment).filter_by(user_id=user.id).count()
            )
            clients.append(
                {
                    "id": user.id,
                    "telegram_id": user.telegram_id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "phone": user.phone,
                    "created_at": user.created_at.isoformat()
                    if user.created_at
                    else None,
                    "appointments_count": appt_count,
                }
            )
        return clients
    finally:
        session.close()


@app.get("/api/clients/{client_id}")
def get_client(client_id: int, admin=Depends(require_admin)):
    session = get_session()
    try:
        user = session.query(User).filter_by(id=client_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Клиент не найден")

        appointments = (
            session.query(Appointment)
            .options(
                joinedload(Appointment.service),
                joinedload(Appointment.performer),
            )
            .filter_by(user_id=client_id)
            .order_by(Appointment.appointment_date.desc())
            .all()
        )

        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "phone": user.phone,
            "appointments": [appointment_to_dict(a) for a in appointments],
        }
    finally:
        session.close()


@app.get("/api/statistics")
def statistics(admin=Depends(require_admin)):
    session = get_session()
    try:
        by_status = (
            session.query(Appointment.status, func.count(Appointment.id))
            .group_by(Appointment.status)
            .all()
        )
        by_service = (
            session.query(Service.name, func.count(Appointment.id))
            .join(Appointment, Appointment.service_id == Service.id)
            .group_by(Service.name)
            .all()
        )
        by_performer = (
            session.query(Performer.name, func.count(Appointment.id))
            .join(Appointment, Appointment.performer_id == Performer.id)
            .group_by(Performer.name)
            .all()
        )

        total_revenue = (
            session.query(func.sum(Service.price))
            .join(Appointment, Appointment.service_id == Service.id)
            .filter(Appointment.status == "confirmed")
            .scalar()
            or 0
        )

        return {
            "by_status": {s: c for s, c in by_status},
            "by_service": {s: c for s, c in by_service},
            "by_performer": {p: c for p, c in by_performer},
            "total_revenue": total_revenue,
            "total_clients": session.query(User).count(),
            "total_appointments": session.query(Appointment).count(),
        }
    finally:
        session.close()


@app.get("/api/calendar")
def calendar(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    admin=Depends(require_admin),
):
    session = get_session()
    try:
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)

        appointments = (
            session.query(Appointment)
            .options(
                joinedload(Appointment.user),
                joinedload(Appointment.service),
                joinedload(Appointment.performer),
            )
            .filter(
                Appointment.appointment_date >= start,
                Appointment.appointment_date < end,
            )
            .order_by(Appointment.appointment_date, Appointment.appointment_time)
            .all()
        )

        return [appointment_to_dict(a) for a in appointments]
    finally:
        session.close()


@app.get("/api/services")
def list_services(admin=Depends(require_admin)):
    session = get_session()
    try:
        services = session.query(Service).all()
        return [
            {
                "id": s.id,
                "name": s.name,
                "price": s.price,
                "duration_minutes": s.duration_minutes,
            }
            for s in services
        ]
    finally:
        session.close()


@app.get("/api/performers")
def list_performers(service_id: int | None = None, admin=Depends(require_admin)):
    session = get_session()
    try:
        query = session.query(Performer)
        if service_id:
            query = query.filter_by(service_id=service_id)
        return [{"id": p.id, "name": p.name, "service_id": p.service_id} for p in query.all()]
    finally:
        session.close()


# Раздаём Mini App
MINIAPP_DIR = ROOT / "miniapp"
if MINIAPP_DIR.exists():
    app.mount("/miniapp", StaticFiles(directory=str(MINIAPP_DIR), html=True), name="miniapp")
