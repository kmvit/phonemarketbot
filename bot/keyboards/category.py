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
    """Клавиатура с родительскими категориями, в которых есть товары с указанным source"""
    from db.crud import get_available_parent_categories, sort_categories_smart
    
    # Получаем все категории из БД (без фильтрации по хардкод списку)
    available_categories = get_available_parent_categories(None, source)
    
    # Если нужно включить и simple формат
    if include_simple and source == 'standard':
        available_simple = get_available_parent_categories(None, 'simple')
        # Объединяем и убираем дубликаты
        available_categories = list(set(available_categories + available_simple))
    
    # Применяем умную сортировку
    available_categories = sort_categories_smart(available_categories)
    
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
        # Получаем подкатегории из БД
        from db.crud import get_available_subcategories
        subcategories_standard = get_available_subcategories(parent_category, None, 'standard')
        subcategories_simple = get_available_subcategories(parent_category, None, 'simple')
        subcategories = list(set(subcategories_standard + subcategories_simple))
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