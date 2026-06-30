"""Подключение к SQLite и создание сессий."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import DATABASE_PATH

DB_PATH = Path(DATABASE_PATH)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_session():
    """Открыть сессию БД. Не забывайте закрывать: session.close()"""
    return SessionLocal()


def init_database():
    """Создать таблицы, если их ещё нет."""
    from database import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
