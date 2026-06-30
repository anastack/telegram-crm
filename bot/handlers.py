"""Обработчики команд и кнопок бота."""

from datetime import date, datetime, time, timedelta
from pathlib import Path

from sqlalchemy.orm import joinedload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes, ConversationHandler

from bot.config import BOOKING_DAYS_AHEAD, WEBAPP_URL, WORK_HOURS
from database.admins import get_admin_telegram_ids_from_db, is_user_admin
from bot.keyboards import (
    appointments_keyboard,
    cancel_confirm_keyboard,
    confirm_keyboard,
    dates_keyboard,
    get_main_menu_keyboard,
    main_menu_inline,
    performers_keyboard,
    service_card_keyboard,
    services_keyboard,
    times_keyboard,
)
from database.db import get_session
from database.models import Appointment, Performer, Service, User

# Состояния диалога записи
CHOOSING_SERVICE, CHOOSING_PERFORMER, CHOOSING_DATE, CHOOSING_TIME, CONFIRMING = range(5)

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

# Локальные фото услуг
IMAGES_DIR = Path(__file__).parent / "images"


# ---------- Вспомогательные функции ----------


def get_or_create_user(telegram_user) -> User:
    """Найти пользователя в БД или зарегистрировать нового."""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_user.id).first()
        if user:
            return user

        user = User(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name or "Клиент",
            last_name=telegram_user.last_name,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


def get_available_dates() -> list[tuple[str, str]]:
    """Список дат для записи на ближайшие N дней."""
    result = []
    today = date.today()
    for i in range(1, BOOKING_DAYS_AHEAD + 1):
        d = today + timedelta(days=i)
        weekday = WEEKDAYS_RU[d.weekday()]
        label = f"{d.strftime('%d.%m')} ({weekday})"
        result.append((d.isoformat(), label))
    return result


def get_busy_times(performer_id: int, appointment_date: date) -> set[str]:
    """Занятые слоты исполнителя на выбранную дату."""
    session = get_session()
    try:
        appointments = (
            session.query(Appointment)
            .filter(
                Appointment.performer_id == performer_id,
                Appointment.appointment_date == appointment_date,
                Appointment.status == "confirmed",
            )
            .all()
        )
        return {a.appointment_time.strftime("%H:%M") for a in appointments}
    finally:
        session.close()


def get_free_times(performer_id: int, appointment_date: date) -> list[str]:
    """Свободные слоты."""
    busy = get_busy_times(performer_id, appointment_date)
    return [t for t in WORK_HOURS if t not in busy]


async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str):
    """Отправить уведомление всем администраторам."""
    for admin_id in get_admin_telegram_ids_from_db():
        try:
            await context.bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            pass


def build_service_caption(service, performers: list) -> str:
    """Текст под фото услуги."""
    master_names = ", ".join(p.name for p in performers)
    return (
        f"💇 *{service.name}*\n\n"
        f"👨‍💼 Мастера: {master_names}\n"
        f"💰 Цена: *{service.price} ₽*\n"
        f"⏱ Длительность: {service.duration_minutes} мин"
    )


async def send_service_catalog(
    chat_id: int, context: ContextTypes.DEFAULT_TYPE, services: list
):
    """Отправить карточки услуг с фото, мастерами и ценой."""
    session = get_session()
    try:
        for service in services:
            performers = (
                session.query(Performer).filter_by(service_id=service.id).all()
            )
            caption = build_service_caption(service, performers)
            keyboard = service_card_keyboard(service)

            image_path = IMAGES_DIR / service.image_url if service.image_url else None

            try:
                if image_path and image_path.exists():
                    with open(image_path, "rb") as photo_file:
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=photo_file,
                            caption=caption,
                            reply_markup=keyboard,
                            parse_mode="Markdown",
                        )
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=caption,
                        reply_markup=keyboard,
                        parse_mode="Markdown",
                    )
            except Exception:
                # Если фото не отправилось — показываем текстом
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=caption,
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
    finally:
        session.close()

    await context.bot.send_message(
        chat_id=chat_id,
        text="👆 Выберите услугу и нажмите «Записаться»",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_booking")]]
        ),
    )


# ---------- /start и регистрация ----------


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Регистрация и приветствие."""
    user = get_or_create_user(update.effective_user)

    text = (
        f"Здравствуйте, {user.first_name}! 👋\n\n"
        "Добро пожаловать в CRM для записи на услуги.\n\n"
        "Выберите действие в меню ниже:"
    )
    await update.message.reply_text(
        text, reply_markup=get_main_menu_keyboard(update.effective_user.id)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка."""
    text = (
        "ℹ️ *Как пользоваться ботом:*\n\n"
        "📅 *Записаться* — выбрать услугу, мастера, дату и время\n"
        "📋 *Мои записи* — посмотреть или отменить запись\n\n"
        "По вопросам пишите администратору."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открыть админ-панель (только для администраторов)."""
    user_id = update.effective_user.id

    if not is_user_admin(user_id):
        await update.message.reply_text("Эта команда только для администратора.")
        return

    if not WEBAPP_URL:
        await update.message.reply_text(
            "Админ-панель не настроена. Укажите WEBAPP_URL в переменных окружения."
        )
        return

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔧 Открыть админ-панель", web_app=WebAppInfo(url=WEBAPP_URL))]]
    )

    await update.message.reply_text(
        "Нажмите кнопку ниже, чтобы открыть админ-панель:",
        reply_markup=keyboard,
    )


# ---------- Главное меню (текстовые кнопки) ----------


async def menu_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок главного меню."""
    text = update.message.text

    if text == "📅 Записаться":
        return await book_start(update, context)
    if text == "📋 Мои записи":
        return await show_my_appointments(update, context)
    if text == "ℹ️ Помощь":
        return await help_command(update, context)
    if text == "🔧 Админ-панель":
        return await admin_panel_command(update, context)

    await update.message.reply_text(
        "Используйте кнопки меню 👇",
        reply_markup=get_main_menu_keyboard(update.effective_user.id),
    )


# ---------- Запись: начало ----------


async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать процесс записи — показать карточки услуг с фото."""
    session = get_session()
    try:
        services = session.query(Service).all()
    finally:
        session.close()

    if not services:
        msg = "К сожалению, услуги пока не добавлены."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(msg)
        else:
            await update.message.reply_text(
                msg, reply_markup=get_main_menu_keyboard(update.effective_user.id)
            )
        return ConversationHandler.END

    chat_id = update.effective_chat.id

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.message.delete()
        except Exception:
            pass

    await context.bot.send_message(chat_id=chat_id, text="📋 *Наши услуги:*", parse_mode="Markdown")
    await send_service_catalog(chat_id, context, services)

    return CHOOSING_SERVICE


# ---------- Выбор услуги ----------


async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_booking":
        await query.message.reply_text(
            "Запись отменена.", reply_markup=main_menu_inline()
        )
        context.user_data.clear()
        return ConversationHandler.END

    service_id = int(query.data.split("_")[1])
    context.user_data["service_id"] = service_id

    session = get_session()
    try:
        performers = session.query(Performer).filter_by(service_id=service_id).all()
        service = session.get(Service, service_id)
    finally:
        session.close()

    await query.message.reply_text(
        f"✅ Вы выбрали: *{service.name}* — {service.price} ₽\n\n"
        f"👨‍💼 Выберите мастера:",
        reply_markup=performers_keyboard(performers),
        parse_mode="Markdown",
    )
    return CHOOSING_PERFORMER


# ---------- Выбор исполнителя ----------


async def choose_performer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "book_start":
        return await book_start(update, context)

    performer_id = int(query.data.split("_")[1])
    context.user_data["performer_id"] = performer_id

    session = get_session()
    try:
        performer = session.query(Performer).get(performer_id)
    finally:
        session.close()

    dates = get_available_dates()
    await query.edit_message_text(
        f"Исполнитель: *{performer.name}*\n\nВыберите дату:",
        reply_markup=dates_keyboard(dates),
        parse_mode="Markdown",
    )
    return CHOOSING_DATE


# ---------- Выбор даты ----------


async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_performer":
        service_id = context.user_data.get("service_id")
        session = get_session()
        try:
            performers = session.query(Performer).filter_by(service_id=service_id).all()
            service = session.query(Service).get(service_id)
        finally:
            session.close()
        await query.edit_message_text(
            f"Услуга: *{service.name}*\n\nВыберите исполнителя:",
            reply_markup=performers_keyboard(performers),
            parse_mode="Markdown",
        )
        return CHOOSING_PERFORMER

    iso_date = query.data.replace("date_", "")
    context.user_data["appointment_date"] = iso_date
    appointment_date = date.fromisoformat(iso_date)
    performer_id = context.user_data["performer_id"]

    free_times = get_free_times(performer_id, appointment_date)

    if not free_times:
        await query.edit_message_text(
            "На эту дату нет свободного времени. Выберите другую дату:",
            reply_markup=dates_keyboard(get_available_dates()),
        )
        return CHOOSING_DATE

    await query.edit_message_text(
        f"Дата: *{appointment_date.strftime('%d.%m.%Y')}*\n\nВыберите время:",
        reply_markup=times_keyboard(free_times),
        parse_mode="Markdown",
    )
    return CHOOSING_TIME


# ---------- Выбор времени ----------


async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_date":
        dates = get_available_dates()
        await query.edit_message_text(
            "Выберите дату:", reply_markup=dates_keyboard(dates)
        )
        return CHOOSING_DATE

    time_str = query.data.replace("time_", "")
    context.user_data["appointment_time"] = time_str

    # Собираем сводку для подтверждения
    session = get_session()
    try:
        service = session.query(Service).get(context.user_data["service_id"])
        performer = session.query(Performer).get(context.user_data["performer_id"])
    finally:
        session.close()

    appt_date = date.fromisoformat(context.user_data["appointment_date"])

    summary = (
        "📋 *Подтвердите запись:*\n\n"
        f"🔹 Услуга: {service.name}\n"
        f"🔹 Исполнитель: {performer.name}\n"
        f"🔹 Дата: {appt_date.strftime('%d.%m.%Y')}\n"
        f"🔹 Время: {time_str}\n"
        f"🔹 Стоимость: {service.price} ₽"
    )

    await query.edit_message_text(
        summary, reply_markup=confirm_keyboard(), parse_mode="Markdown"
    )
    return CONFIRMING


# ---------- Подтверждение записи ----------


async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_booking":
        await query.edit_message_text(
            "Запись отменена.", reply_markup=main_menu_inline()
        )
        context.user_data.clear()
        return ConversationHandler.END

    user = get_or_create_user(update.effective_user)
    data = context.user_data

    session = get_session()
    try:
        appointment = Appointment(
            user_id=user.id,
            service_id=data["service_id"],
            performer_id=data["performer_id"],
            appointment_date=date.fromisoformat(data["appointment_date"]),
            appointment_time=datetime.strptime(data["appointment_time"], "%H:%M").time(),
            status="confirmed",
        )
        session.add(appointment)
        session.commit()

        service = session.query(Service).get(data["service_id"])
        performer = session.query(Performer).get(data["performer_id"])
    finally:
        session.close()

    appt_date = date.fromisoformat(data["appointment_date"])
    time_str = data["appointment_time"]

    await query.edit_message_text(
        "✅ Запись успешно создана!\n\n"
        f"📅 {appt_date.strftime('%d.%m.%Y')} в {time_str}\n"
        f"💇 {service.name} — {performer.name}\n\n"
        "Мы напомним вам о визите.",
        reply_markup=main_menu_inline(),
    )

    # Уведомление клиенту (подтверждение)
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=(
            "🔔 Напоминание: у вас запись\n"
            f"📅 {appt_date.strftime('%d.%m.%Y')} в {time_str}\n"
            f"💇 {service.name}"
        ),
    )

    # Уведомление администратору
    admin_text = (
        "🆕 *Новая запись!*\n\n"
        f"👤 {user.first_name} (@{user.username or 'нет'})\n"
        f"💇 {service.name}\n"
        f"👨‍💼 {performer.name}\n"
        f"📅 {appt_date.strftime('%d.%m.%Y')} в {time_str}"
    )
    await notify_admins(context, admin_text)

    context.user_data.clear()
    return ConversationHandler.END


# ---------- Мои записи ----------


async def show_my_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные записи пользователя."""
    user = get_or_create_user(update.effective_user)

    session = get_session()
    try:
        appointments = (
            session.query(Appointment)
            .options(
                joinedload(Appointment.service),
                joinedload(Appointment.performer),
            )
            .filter(
                Appointment.user_id == user.id,
                Appointment.status == "confirmed",
                Appointment.appointment_date >= date.today(),
            )
            .order_by(Appointment.appointment_date, Appointment.appointment_time)
            .all()
        )
    finally:
        session.close()

    if not appointments:
        text = "У вас нет активных записей."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                text, reply_markup=main_menu_inline()
            )
        else:
            await update.message.reply_text(
        text, reply_markup=get_main_menu_keyboard(update.effective_user.id)
    )
        return

    lines = ["📋 *Ваши записи:*\n"]
    for i, appt in enumerate(appointments, 1):
        lines.append(
            f"{i}. {appt.appointment_date.strftime('%d.%m.%Y')} "
            f"в {appt.appointment_time.strftime('%H:%M')}\n"
            f"   {appt.service.name} — {appt.performer.name}"
        )
    lines.append("\nНажмите на запись, чтобы отменить:")

    text = "\n".join(lines)
    keyboard = appointments_keyboard(appointments)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, reply_markup=keyboard, parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=keyboard, parse_mode="Markdown"
        )


async def cancel_appointment_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Спросить подтверждение отмены."""
    query = update.callback_query
    await query.answer()

    if query.data == "main_menu":
        await query.edit_message_text(
            "Главное меню 👇", reply_markup=main_menu_inline()
        )
        return

    if query.data == "my_appointments":
        return await show_my_appointments(update, context)

    appointment_id = int(query.data.replace("cancel_appt_", ""))

    session = get_session()
    try:
        appt = (
            session.query(Appointment)
            .options(joinedload(Appointment.service))
            .get(appointment_id)
        )
    finally:
        session.close()

    if not appt:
        await query.edit_message_text("Запись не найдена.")
        return

    await query.edit_message_text(
        f"Отменить запись?\n\n"
        f"📅 {appt.appointment_date.strftime('%d.%m.%Y')} "
        f"в {appt.appointment_time.strftime('%H:%M')}\n"
        f"💇 {appt.service.name}",
        reply_markup=cancel_confirm_keyboard(appointment_id),
    )


async def confirm_cancel_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить запись."""
    query = update.callback_query
    await query.answer()

    appointment_id = int(query.data.replace("confirm_cancel_", ""))
    user = get_or_create_user(update.effective_user)

    session = get_session()
    try:
        appt = (
            session.query(Appointment)
            .options(
                joinedload(Appointment.service),
                joinedload(Appointment.performer),
            )
            .filter_by(id=appointment_id, user_id=user.id, status="confirmed")
            .first()
        )
        if not appt:
            await query.edit_message_text("Запись не найдена или уже отменена.")
            return

        appt.status = "cancelled"
        session.commit()

        service_name = appt.service.name
        performer_name = appt.performer.name
        appt_date = appt.appointment_date.strftime("%d.%m.%Y")
        appt_time = appt.appointment_time.strftime("%H:%M")
    finally:
        session.close()

    await query.edit_message_text(
        f"❌ Запись отменена.\n\n📅 {appt_date} в {appt_time}",
        reply_markup=main_menu_inline(),
    )

    # Уведомление об отмене
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=f"🔔 Ваша запись на {appt_date} в {appt_time} ({service_name}) отменена.",
    )

    admin_text = (
        f"❌ *Отмена записи*\n\n"
        f"👤 {user.first_name}\n"
        f"💇 {service_name} — {performer_name}\n"
        f"📅 {appt_date} в {appt_time}"
    )
    await notify_admins(context, admin_text)


async def cancel_booking_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход из диалога записи."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "Действие отменено.", reply_markup=main_menu_inline()
        )
    context.user_data.clear()
    return ConversationHandler.END
