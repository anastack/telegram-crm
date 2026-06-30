"""Точка входа Telegram-бота."""

import sys
from pathlib import Path

# Добавляем корень проекта в путь, чтобы работали импорты
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config import BOT_TOKEN
from bot.handlers import (
    CHOOSING_DATE,
    CHOOSING_PERFORMER,
    CHOOSING_SERVICE,
    CHOOSING_TIME,
    CONFIRMING,
    admin_panel_command,
    book_start,
    cancel_appointment_prompt,
    cancel_booking_conversation,
    choose_date,
    choose_performer,
    choose_service,
    choose_time,
    confirm_booking,
    confirm_cancel_appointment,
    help_command,
    menu_text_handler,
    show_my_appointments,
    start_command,
)
from database.seed import seed_data


def main():
    if not BOT_TOKEN:
        print("Ошибка: укажите BOT_TOKEN в файле .env")
        sys.exit(1)

    run_bot()


def run_bot():
    """Запуск polling-бота."""
    seed_data()

    app = Application.builder().token(BOT_TOKEN).build()

    # Диалог записи на услугу
    booking_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📅 Записаться$"), book_start),
            CallbackQueryHandler(book_start, pattern="^book_start$"),
        ],
        states={
            CHOOSING_SERVICE: [
                CallbackQueryHandler(choose_service, pattern="^(service_|cancel_booking)"),
            ],
            CHOOSING_PERFORMER: [
                CallbackQueryHandler(choose_performer, pattern="^(performer_|book_start)"),
            ],
            CHOOSING_DATE: [
                CallbackQueryHandler(choose_date, pattern="^(date_|back_to_performer)"),
            ],
            CHOOSING_TIME: [
                CallbackQueryHandler(choose_time, pattern="^(time_|back_to_date)"),
            ],
            CONFIRMING: [
                CallbackQueryHandler(confirm_booking, pattern="^(confirm_yes|cancel_booking)"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_booking_conversation, pattern="^cancel_booking$"),
            CommandHandler("start", start_command),
        ],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_panel_command))
    app.add_handler(booking_handler)

    # Мои записи и отмена
    app.add_handler(
        CallbackQueryHandler(show_my_appointments, pattern="^my_appointments$")
    )
    app.add_handler(
        CallbackQueryHandler(cancel_appointment_prompt, pattern="^(cancel_appt_|main_menu|my_appointments)")
    )
    app.add_handler(
        CallbackQueryHandler(confirm_cancel_appointment, pattern="^confirm_cancel_")
    )

    # Текстовые кнопки меню
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            menu_text_handler,
        )
    )

    print("Бот запущен. Нажмите Ctrl+C для остановки.")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
