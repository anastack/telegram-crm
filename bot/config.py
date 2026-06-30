"""Настройки бота из переменных окружения."""

from config.settings import BOT_TOKEN, WEBAPP_URL, get_admin_telegram_ids

# Рабочие часы: с 9:00 до 18:00, обед с 13:00 до 14:00
WORK_HOURS = ["09:00", "10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00", "18:00"]

# Сколько дней вперёд можно записаться
BOOKING_DAYS_AHEAD = 14

# Для обратной совместимости
ADMIN_TELEGRAM_ID = str(get_admin_telegram_ids()[0]) if get_admin_telegram_ids() else ""
