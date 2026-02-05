from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Родительские категории
parent_categories = [
    "Apple",
    "Samsung",
    "Google Pixel",
    "Xiaomi",
    "Redmi",
    "POCO",
    "Honor",
    "Huawei",
    "Vivo",
    "Realme",
    "Yandex",
    "Meta Quest",
    "Nintendo",
    "Valve",
    "Sony",
    "GoPro",
    "Insta360",
    "Garmin",
    "Dyson",
    "Аксессуары"
]

# Маппинг родительских категорий к подкатегориям
parent_to_subcategories = {
    "Apple": [
        "iPhone SE", "iPhone 11", "iPhone 12", "iPhone 13", "iPhone 14",
        "iPhone 15", "iPhone 16", "iPhone 17", "iPhone 17 Air", "iPhone 17 Pro", "iPhone 17 Pro Max", "iPhone Air",
        "iPad", "iPad Air", "iPad Pro", "iPad mini",
        "MacBook Air", "MacBook Pro", "Mac mini",
        "Apple Watch", "Apple iMac", "AirPods", "Magic Keyboard", "Apple Pencil",
        "Apple Аксессуары"
    ],
    "Samsung": [
        "Samsung Galaxy S25 Ultra", "Samsung Galaxy S25+", "Samsung Galaxy S25",
        "Samsung Galaxy S24 Ultra", "Samsung Galaxy S24+", "Samsung Galaxy S24", 
        "Samsung Galaxy S23+", "Samsung Galaxy S23",
        "Samsung Galaxy S22", "Samsung Galaxy S21", "Samsung Galaxy S20",
        "Samsung Galaxy Z Fold", "Samsung Galaxy Z Flip", "Samsung Galaxy A",
        "Samsung Galaxy Tab", "Samsung Galaxy Watch", "Samsung Galaxy Buds",
        "Samsung Galaxy Ring", "Samsung Аксессуары", "Samsung"
    ],
    "Google Pixel": [
        "Google Pixel 6", "Google Pixel 7", "Google Pixel 7 Pro",
        "Google Pixel 9", "Google Pixel 9a", "Google Pixel 9 Pro XL",
        "Google Pixel 9 Pro Fold", "Google Pixel 10", "Google Pixel 10 Pro",
        "Google Pixel 10 Pro XL", "Google Pixel 10 Pro Fold", "Google Pixel"
    ],
    "Xiaomi": [
        "Xiaomi", "Xiaomi Pad 7 Pro", "Xiaomi Pad"
    ],
    "Redmi": [
        "Redmi 13", "Redmi 15", "Redmi Note 14", "Redmi Note 14 Pro",
        "Redmi Note 14 Pro+", "Redmi Note 14S", "Redmi Pad 7 Pro",
        "Redmi Pad Pro", "Redmi"
    ],
    "POCO": [
        "POCO C61", "POCO C85", "POCO F6", "POCO F6 Pro", "POCO F7",
        "POCO M6", "POCO M7", "POCO M7 Pro", "POCO Pad", "POCO X7",
        "POCO X7 Pro", "POCO"
    ],
    "Honor": [
        "Honor X8b", "Honor"
    ],
    "Huawei": [
        "Huawei"
    ],
    "Vivo": [
        "Vivo Y04", "Vivo Y29", "Vivo Buds", "Vivo"
    ],
    "Realme": [
        "Realme 14", "Realme C75", "Realme"
    ],
    "Yandex": [
        "Yandex Станция Лайт 2", "Yandex Станция Мини 3 Про",
        "Yandex Станция Стрит", "Yandex"
    ],
    "Meta Quest": [
        "Meta Quest 3", "Meta Quest 3S", "Meta Quest"
    ],
    "Nintendo": [
        "Nintendo Switch Lite", "Nintendo Switch", "Nintendo"
    ],
    "Valve": [
        "Valve Steam Deck OLED", "Valve Steam Deck", "Valve"
    ],
    "Sony": [
        "Sony PlayStation 5", "Sony WH-1000XM5", "Sony WH-1000XM6", "Sony"
    ],
    "GoPro": [
        "GoPro 13", "GoPro"
    ],
    "Insta360": [
        "Insta360 X4", "Insta360 X5", "Insta360"
    ],
    "Garmin": [
        "Garmin MARQ", "Garmin"
    ],
    "Dyson": [
        "Dyson V8", "Dyson V10", "Dyson V11", "Dyson V12", "Dyson V15",
        "Dyson Airwrap", "Dyson Supersonic", "Dyson Purifier", "Dyson"
    ],
    "Аксессуары": ["Аксессуары"]
}

def get_category_with_icon(category):
    """Возвращает название категории без иконки"""
    return category

def get_main_keyboard(user_id=None):
    """Создает главную клавиатуру. Кнопка 'Админка' показывается только администраторам."""
    keyboard = [
        [KeyboardButton(text="Прайс"), KeyboardButton(text="Предзаказ"), KeyboardButton(text="Корзина")],
        [KeyboardButton(text="📞 Связаться с администратором")]
    ]
    
    # Добавляем кнопку "Админка" только для администраторов
    if user_id is not None:
        from config import ADMIN_IDS
        if user_id in ADMIN_IDS:
            keyboard.append([KeyboardButton(text="Админка")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_categories_keyboard(source='standard', include_simple=True):
    """Клавиатура с родительскими категориями, в которых есть товары с указанным source"""
    from db.crud import get_available_parent_categories
    
    # Получаем только те категории, в которых есть товары
    available_categories = get_available_parent_categories(parent_categories, source)
    
    # Если нужно включить и simple формат
    if include_simple and source == 'standard':
        available_simple = get_available_parent_categories(parent_categories, 'simple')
        # Объединяем и убираем дубликаты
        available_categories = list(set(available_categories + available_simple))
    
    if not available_categories:
        # Если нет доступных категорий, возвращаем пустую клавиатуру с кнопкой "Назад"
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Назад")]], resize_keyboard=True)
    
    row = []
    keyboard = []
    for i, cat in enumerate(available_categories, 1):
        row.append(KeyboardButton(text=get_category_with_icon(cat)))
        if i % 3 == 0 or i == len(available_categories):
            keyboard.append(row)
            row = []
    # Добавляем кнопку 'Назад' отдельной строкой
    keyboard.append([KeyboardButton(text="Назад")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_subcategories_keyboard(parent_category, available_subcats=None):
    """Клавиатура с подкатегориями для родительской категории"""
    if available_subcats is None:
        subcategories = parent_to_subcategories.get(parent_category, [])
    else:
        # Используем только те подкатегории, которые есть в БД
        subcategories = available_subcats
    
    row = []
    keyboard = []
    for i, subcat in enumerate(subcategories, 1):
        row.append(KeyboardButton(text=get_category_with_icon(subcat)))
        if i % 3 == 0 or i == len(subcategories):
            keyboard.append(row)
            row = []
    # Добавляем кнопку 'Назад' отдельной строкой
    keyboard.append([KeyboardButton(text="Назад")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_preorder_categories_keyboard(categories):
    """Клавиатура с категориями предзаказа из БД"""
    if not categories:
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Назад")]], resize_keyboard=True)
    
    row = []
    keyboard = []
    for i, cat in enumerate(categories, 1):
        row.append(KeyboardButton(text=get_category_with_icon(cat)))
        if i % 3 == 0 or i == len(categories):
            keyboard.append(row)
            row = []
    # Добавляем кнопку 'Назад' отдельной строкой
    keyboard.append([KeyboardButton(text="Назад")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)