from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_admin_keyboard():
    """Клавиатура для админки"""
    keyboard = [
        [KeyboardButton(text="📊 Загрузить прайс"), KeyboardButton(text="📦 Прайс предзаказа")],
        [KeyboardButton(text="⚙️ Настройка наценки"), KeyboardButton(text="📈 Текущая наценка")],
        [KeyboardButton(text="⚙️ Наценка предзаказа"), KeyboardButton(text="📋 Статистика")],
        [KeyboardButton(text="👤 Персональные проценты"), KeyboardButton(text="📦 Заказы")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

