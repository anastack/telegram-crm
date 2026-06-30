"""Клавиатуры бота."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from bot.config import WEBAPP_URL
from database.admins import is_user_admin

# --- Главное меню (кнопки внизу экрана) ---


def get_main_menu_keyboard(telegram_id: int | None = None) -> ReplyKeyboardMarkup:
    """Меню клиента. Админам — кнопка Mini App."""
    rows = [
        ["📅 Записаться"],
        ["📋 Мои записи"],
        ["ℹ️ Помощь"],
    ]

    if (
        telegram_id
        and is_user_admin(telegram_id)
        and WEBAPP_URL.startswith("https://")
    ):
        rows.append(
            [KeyboardButton("🔧 Админ-панель", web_app=WebAppInfo(url=WEBAPP_URL))]
        )

    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def main_menu_inline() -> InlineKeyboardMarkup:
    """То же меню, но inline-кнопками (после действий)."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📅 Записаться", callback_data="book_start")],
            [InlineKeyboardButton("📋 Мои записи", callback_data="my_appointments")],
        ]
    )


# --- Запись на услугу ---

def service_card_keyboard(service) -> InlineKeyboardMarkup:
    """Кнопка под карточкой услуги."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"📅 Записаться — {service.price} ₽",
                    callback_data=f"service_{service.id}",
                )
            ]
        ]
    )


def services_keyboard(services: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(s.name, callback_data=f"service_{s.id}")]
        for s in services
    ]
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_booking")])
    return InlineKeyboardMarkup(buttons)


def performers_keyboard(performers: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(p.name, callback_data=f"performer_{p.id}")]
        for p in performers
    ]
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="book_start")])
    return InlineKeyboardMarkup(buttons)


def dates_keyboard(dates: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """dates — список пар (дата ISO, подпись для кнопки)."""
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"date_{iso_date}")]
        for iso_date, label in dates
    ]
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_performer")])
    return InlineKeyboardMarkup(buttons)


def times_keyboard(times: list[str]) -> InlineKeyboardMarkup:
    row: list[InlineKeyboardButton] = []
    buttons: list[list[InlineKeyboardButton]] = []

    for t in times:
        row.append(InlineKeyboardButton(t, callback_data=f"time_{t}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_date")])
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_yes"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_booking"),
            ]
        ]
    )


# --- Мои записи ---

def appointments_keyboard(appointments: list) -> InlineKeyboardMarkup:
    buttons = []
    for appt in appointments:
        label = (
            f"❌ {appt.appointment_date.strftime('%d.%m')} "
            f"{appt.appointment_time.strftime('%H:%M')} — {appt.service.name}"
        )
        buttons.append(
            [InlineKeyboardButton(label, callback_data=f"cancel_appt_{appt.id}")]
        )
    buttons.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def cancel_confirm_keyboard(appointment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Да, отменить",
                    callback_data=f"confirm_cancel_{appointment_id}",
                ),
                InlineKeyboardButton("◀️ Назад", callback_data="my_appointments"),
            ]
        ]
    )
