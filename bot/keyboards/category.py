from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

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
    """Клавиатура с родительскими категориями, в которых есть товары с указанным source.
    Автоматически получает все категории из БД, включая новые неизвестные бренды."""
    from db.crud import get_available_parent_categories
    
    # Получаем все доступные категории из БД (динамически, без ограничения статическим списком)
    # Сначала получаем для указанного source
    available_categories = get_available_parent_categories(None, source)
    
    # Если нужно включить и simple формат
    if include_simple and source == 'standard':
        available_simple = get_available_parent_categories(None, 'simple')
        # Объединяем и убираем дубликаты
        available_categories = list(set(available_categories + available_simple))
    
    # Сортируем категории для единообразия (известные бренды первыми, затем новые)
    # Можно добавить приоритет для известных брендов, но пока просто сортируем
    available_categories = sorted(available_categories)
    
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

def get_subcategories_keyboard(parent_category, available_subcats=None, source='standard'):
    """Клавиатура с подкатегориями для родительской категории.
    Все подкатегории получаются динамически из БД."""
    if available_subcats is None:
        # Получаем подкатегории динамически из БД
        from db.crud import get_dynamic_parent_to_subcategories
        dynamic_mapping = get_dynamic_parent_to_subcategories(source)
        subcategories = dynamic_mapping.get(parent_category, [])
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