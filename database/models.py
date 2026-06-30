"""Модели данных CRM."""

from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db import Base


class User(Base):
  """Клиент Telegram."""

  __tablename__ = "users"

  id: Mapped[int] = mapped_column(primary_key=True)
  telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
  username: Mapped[str | None] = mapped_column(String(100), nullable=True)
  first_name: Mapped[str] = mapped_column(String(100))
  last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
  phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  appointments: Mapped[list["Appointment"]] = relationship(back_populates="user")


class Admin(Base):
  """Администратор CRM."""

  __tablename__ = "admins"

  id: Mapped[int] = mapped_column(primary_key=True)
  telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
  name: Mapped[str | None] = mapped_column(String(100), nullable=True)
  is_active: Mapped[bool] = mapped_column(default=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Service(Base):
  """Услуга."""

  __tablename__ = "services"

  id: Mapped[int] = mapped_column(primary_key=True)
  name: Mapped[str] = mapped_column(String(200))
  duration_minutes: Mapped[int] = mapped_column(default=60)
  price: Mapped[int] = mapped_column(default=0)
  image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

  performers: Mapped[list["Performer"]] = relationship(back_populates="service")
  appointments: Mapped[list["Appointment"]] = relationship(back_populates="service")


class Performer(Base):
  """Исполнитель (мастер)."""

  __tablename__ = "performers"

  id: Mapped[int] = mapped_column(primary_key=True)
  name: Mapped[str] = mapped_column(String(100))
  service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))

  service: Mapped["Service"] = relationship(back_populates="performers")
  appointments: Mapped[list["Appointment"]] = relationship(back_populates="performer")


class Appointment(Base):
  """Запись клиента."""

  __tablename__ = "appointments"
  __table_args__ = (
      UniqueConstraint(
          "performer_id",
          "appointment_date",
          "appointment_time",
          name="uq_performer_datetime",
      ),
  )

  id: Mapped[int] = mapped_column(primary_key=True)
  user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
  service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
  performer_id: Mapped[int] = mapped_column(ForeignKey("performers.id"))
  appointment_date: Mapped[date] = mapped_column(Date)
  appointment_time: Mapped[time] = mapped_column(Time)
  status: Mapped[str] = mapped_column(String(20), default="confirmed")
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

  user: Mapped["User"] = relationship(back_populates="appointments")
  service: Mapped["Service"] = relationship(back_populates="appointments")
  performer: Mapped["Performer"] = relationship(back_populates="appointments")
