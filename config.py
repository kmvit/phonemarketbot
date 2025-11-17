# Конфигурация проекта
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Список ID администраторов (формат в .env: "123456789,987654321" или "123456789")
admin_ids_str = os.getenv("ADMIN_IDS", "")
if admin_ids_str:
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in admin_ids_str.split(",") if admin_id.strip()]
else:
    ADMIN_IDS = []

# Путь к базе данных
DATABASE_PATH = os.getenv("DATABASE_PATH", "phonemarketbot.db")

# Стандартная наценка (сумма в рублях)
DEFAULT_MARKUP_AMOUNT = int(os.getenv("DEFAULT_MARKUP_AMOUNT", "0"))

# Стандартная наценка для предзаказа (сумма в рублях)
DEFAULT_PREORDER_MARKUP_AMOUNT = int(os.getenv("DEFAULT_PREORDER_MARKUP_AMOUNT", "0"))

# Директория для загруженных прайс-листов
PRICE_UPLOAD_DIR = os.getenv("PRICE_UPLOAD_DIR", "data/samples")

# ID администратора для ответов пользователям (кнопка "Связаться с администратором")
ADMIN_HELP = int(os.getenv("ADMIN_HELP", "0")) if os.getenv("ADMIN_HELP") else None
