"""Общие настройки проекта (бот + API)."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent

# Загружаем .env если он существует
env_file = ROOT / ".env"
if env_file.exists():
    load_dotenv(env_file)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Публичный HTTPS-адрес Mini App, например: https://your-app.railway.app/miniapp/
_raw_webapp = os.getenv("WEBAPP_URL", "").rstrip("/")
WEBAPP_URL = f"{_raw_webapp}/" if _raw_webapp else ""

# Путь к базе (на Railway укажите постоянный том, например /data/crm.db)
DATABASE_PATH = os.getenv("DATABASE_PATH", str(ROOT / "database" / "crm.db"))

# Запускать бота вместе с API (true на Railway в одном сервисе)
RUN_BOT = os.getenv("RUN_BOT", "true").lower() == "true"


def get_admin_telegram_ids() -> list[int]:
    """Список Telegram ID админов из .env"""
    ids: set[int] = set()
    for source in (os.getenv("ADMIN_TELEGRAM_IDS", ""), os.getenv("ADMIN_TELEGRAM_ID", "")):
        for part in source.split(","):
            part = part.strip()
            if part.isdigit():
                ids.add(int(part))
    return sorted(ids)

