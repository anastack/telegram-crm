"""Начальные данные: услуги и исполнители."""

from pathlib import Path

from sqlalchemy import inspect, text

from database.admins import sync_admins_from_env
from database.db import engine, get_session, init_database
from database.models import Performer, Service

# Папка с локальными фото (Telegram не всегда загружает фото по URL из интернета)
IMAGES_DIR = Path(__file__).parent.parent / "bot" / "images"

# Имя файла в bot/images/ для каждой услуги
SERVICE_IMAGES = {
    "Стрижка": "strizhka.jpg",
    "Маникюр": "manicure.jpg",
    "Массаж": "massage.jpg",
    "Консультация": "consult.jpg",
}

# Услуга: (название, длительность, цена, [имена мастеров])
SERVICES_DATA = [
    ("Стрижка", 60, 1500, ["Анна", "Дмитрий"]),
    ("Маникюр", 90, 2000, ["Елена", "София"]),
    ("Массаж", 60, 2500, ["Игорь", "Мария"]),
    ("Консультация", 30, 1000, ["Ольга", "Алексей"]),
]


def create_placeholder_image(file_path: Path, title: str, color: tuple[int, int, int]):
    """Создать простое цветное фото-заглушку."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        # Минимальный валидный JPEG 1x1, если Pillow не установлен
        file_path.write_bytes(
            bytes.fromhex(
                "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707"
                "070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c"
                "231c1c2837292c30313434341f27393d38323c2e333432ffdb0043010909090c0b"
                "0c180d0d1832211c213232323232323232323232323232323232323232323232"
                "323232323232323232323232323232323232323232ffc000110800010001030111"
                "00021100031101ffc4001500010100000000000000000000000000000000ffc400"
                "14100100000000000000000000000000000000ffda0008010100003f00d2cf20"
                "ffd9"
            )
        )
        return

    img = Image.new("RGB", (800, 500), color=color)
    draw = ImageDraw.Draw(img)
    draw.rectangle((40, 40, 760, 460), outline=(255, 255, 255), width=4)
    draw.text((80, 220), title, fill=(255, 255, 255))
    img.save(file_path, "JPEG", quality=85)


def ensure_local_images():
    """Создать фото услуг в bot/images/."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    placeholders = {
        "strizhka.jpg": ("Стрижка", (70, 130, 180)),
        "manicure.jpg": ("Маникюр", (199, 21, 133)),
        "massage.jpg": ("Массаж", (46, 139, 87)),
        "consult.jpg": ("Консультация", (255, 140, 0)),
    }

    for filename, (title, color) in placeholders.items():
        file_path = IMAGES_DIR / filename
        if file_path.exists() and file_path.stat().st_size > 100:
            continue
        create_placeholder_image(file_path, title, color)


def migrate_database():
    """Добавить новые колонки в существующую базу."""
    init_database()
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("services")]

    if "image_url" not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE services ADD COLUMN image_url VARCHAR(500)"))
            conn.commit()


def update_service_images():
    """Обновить пути к фото у уже существующих услуг."""
    session = get_session()
    try:
        for service in session.query(Service).all():
            if service.name in SERVICE_IMAGES:
                service.image_url = SERVICE_IMAGES[service.name]
        session.commit()
    finally:
        session.close()


def seed_data():
    """Создать таблицы и заполнить тестовыми данными."""
    try:
        migrate_database()
        sync_admins_from_env()
        ensure_local_images()
        session = get_session()

        try:
            if session.query(Service).count() == 0:
                for name, duration, price, masters in SERVICES_DATA:
                    service = Service(
                        name=name,
                        duration_minutes=duration,
                        price=price,
                        image_url=SERVICE_IMAGES.get(name),
                    )
                    session.add(service)
                    session.flush()

                    for master_name in masters:
                        session.add(Performer(name=master_name, service_id=service.id))

                session.commit()
            else:
                update_service_images()
        finally:
            session.close()
    except Exception as e:
        print(f"Ошибка при инициализации БД: {e}")
        import traceback
        traceback.print_exc()

