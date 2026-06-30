"""Проверка доступа администратора через Telegram Mini App."""

import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

from config.settings import BOT_TOKEN
from database.admins import is_user_admin


def verify_telegram_init_data(init_data: str) -> dict | None:
    """Проверить подпись Telegram WebApp initData."""
    if not BOT_TOKEN or not init_data:
        return None

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", "")
        if not received_hash:
            return None

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(
            b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
        ).digest()
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        if calculated_hash != received_hash:
            return None

        return json.loads(parsed.get("user", "{}"))
    except Exception:
        return None


def require_admin(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    """Доступ только для админов через Telegram Mini App."""
    if not x_telegram_init_data:
        raise HTTPException(
            status_code=401,
            detail="Откройте панель через кнопку «Админ-панель» в Telegram-боте",
        )

    user = verify_telegram_init_data(x_telegram_init_data)
    if not user or not user.get("id"):
        raise HTTPException(status_code=401, detail="Ошибка авторизации Telegram")

    telegram_id = int(user["id"])
    if not is_user_admin(telegram_id):
        raise HTTPException(status_code=403, detail="У вас нет прав администратора")

    return user
