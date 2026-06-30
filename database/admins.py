"""Работа с администраторами."""

from config.settings import get_admin_telegram_ids
from database.db import get_session
from database.models import Admin


def is_user_admin(telegram_id: int) -> bool:
    """Проверить, является ли пользователь админом."""
    session = get_session()
    try:
        admin = (
            session.query(Admin)
            .filter_by(telegram_id=telegram_id, is_active=True)
            .first()
        )
        return admin is not None
    finally:
        session.close()


def get_admin_telegram_ids_from_db() -> list[int]:
    """Все активные админы из базы."""
    session = get_session()
    try:
        return [
            a.telegram_id
            for a in session.query(Admin).filter_by(is_active=True).all()
        ]
    finally:
        session.close()


def sync_admins_from_env():
    """Добавить админов из .env в базу (не удаляет существующих)."""
    session = get_session()
    try:
        for telegram_id in get_admin_telegram_ids():
            exists = session.query(Admin).filter_by(telegram_id=telegram_id).first()
            if not exists:
                session.add(Admin(telegram_id=telegram_id, name="Админ"))
        session.commit()
    finally:
        session.close()
