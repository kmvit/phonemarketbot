from aiogram import Router, types
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import Optional
import re
from collections import OrderedDict
from bot.keyboards.category import (
    get_main_keyboard, get_categories_keyboard, get_subcategories_keyboard,
    parent_categories, parent_to_subcategories, get_category_with_icon, category_icons,
    get_preorder_categories_keyboard
)
from db.crud import (
    get_products_by_category, get_available_subcategories, add_to_cart,
    get_cart, remove_from_cart, clear_cart, create_order, get_product_by_id, get_order,
    update_cart_quantity, get_dynamic_subcategories_for_parent,
    get_preorder_products_by_category, get_preorder_available_subcategories,
    get_preorder_categories, get_preorder_product_by_id, add_to_preorder_cart,
    get_preorder_cart, remove_from_preorder_cart, update_preorder_cart_quantity
)
from admin.discount import calculate_price_with_markup

router = Router()

# Хранилище состояний пользователей для навигации назад
# Формат: {user_id: {'screen': 'categories'|'subcategories'|'products', 'parent_category': str, 'subcategory': str}}
user_states = {}

# Callback data класс для корзины
class CartCallback(CallbackData, prefix="cart"):
    action: str
    cart_id: Optional[int] = None
    quantity: Optional[int] = None

# FSM состояния для добавления товара в корзину
class AddToCartStates(StatesGroup):
    waiting_for_quantity = State()

def get_country_with_flag(country):
    """Возвращает страну с флагом (всегда возвращает как есть, так как в БД уже сохранен флаг)"""
    if not country:
        return ""
    
    country_str = str(country).strip()
    # Возвращаем как есть, так как при загрузке прайса уже добавляется флаг через маппинг
    return country_str

def extract_base_model(product_name):
    """Извлекает базовую модель из названия товара (без памяти и цвета)"""
    if not product_name:
        return product_name
    
    # Убираем память (64Gb, 128Gb, 256Gb, 512Gb, 1Tb, 2Tb и т.д.)
    name = re.sub(r'\s+\d+\s*(Gb|Tb)', '', product_name, flags=re.IGNORECASE)
    
    # Убираем цвета (список цветов)
    colors = ['Black', 'Blue', 'Red', 'Midnight', 'Starlight', 'Purple', 'Yellow', 
              'Green', 'Pink', 'White', 'Silver', 'Gold', 'Space Gray', 'Sp. Gray',
              'Teal', 'Ultramarine', 'Desert', 'Natural', 'Lavender', 'Sage', 'Mist Blue',
              'Orange', 'Rose Gold', 'Jet Black', 'Light Gold', 'Cloud White', 'Sky Blue',
              'Space Black', 'Light Blush', 'Pur Fog', 'Star', 'Mid', 'Plum', 'Ink',
              'Natural', 'Nat', 'Blue Ocean', 'Green Alpine', 'Black Ocean', 'Denim',
              'Mil Lp', 'Link']
    
    for color in colors:
        # Убираем цвет с учетом регистра и границ слов
        name = re.sub(r'\s+' + re.escape(color) + r'\b', '', name, flags=re.IGNORECASE)
    
    # Убираем лишние пробелы
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name

def extract_model_with_color(product_name):
    """Извлекает модель с цветом из названия товара (базовая модель + память + цвет)"""
    if not product_name:
        return product_name
    
    # Убираем лишние пробелы
    name = product_name.strip()
    
    # Если в названии есть запятая, берем все до первой запятой
    # (обычно после цвета идет запятая и страна/код модели)
    if ',' in name:
        return name.split(',')[0].strip()
    
    # Список цветов (от длинных к коротким, чтобы сначала находить составные цвета)
    colors = ['Space Gray', 'Sp. Gray', 'Rose Gold', 'Jet Black', 'Light Gold', 
              'Cloud White', 'Sky Blue', 'Space Black', 'Light Blush', 'Pur Fog',
              'Blue Ocean', 'Green Alpine', 'Black Ocean', 'Mist Blue', 'Mil Lp',
              'Black', 'Blue', 'Red', 'Midnight', 'Starlight', 'Purple', 'Yellow', 
              'Green', 'Pink', 'White', 'Silver', 'Gold', 'Teal', 'Ultramarine', 
              'Desert', 'Natural', 'Lavender', 'Sage', 'Orange', 'Star', 'Mid', 
              'Plum', 'Ink', 'Nat', 'Denim', 'Link']
    
    # Ищем цвет в названии (от длинных к коротким)
    for color in colors:
        # Ищем цвет в конце названия (после памяти обычно идет цвет)
        pattern = r'(.+\s+' + re.escape(color) + r'\b)'
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Если цвет не найден, возвращаем название как есть
    return name

def extract_memory_from_name(product_name):
    """Извлекает память из названия товара (64Gb, 128Gb, 256Gb, 512Gb, 1Tb, 2Tb и т.д.)"""
    if not product_name:
        return None
    
    # Форматы с единицами измерения (1TB, 2TB, 128Gb, 256Gb и т.д.)
    patterns = [
        r'(\d+)\s*TB',  # 1TB, 2TB, 4TB, 8TB
        r'(\d+)\s*Tb',  # 1Tb, 2Tb, 4Tb, 8Tb
        r'(\d+)\s*GB',  # 128GB, 256GB, 512GB
        r'(\d+)\s*Gb',  # 64Gb, 128Gb, 256Gb, 512Gb
    ]
    for pattern in patterns:
        match = re.search(pattern, product_name, re.IGNORECASE)
        if match:
            value = match.group(1)
            unit = 'TB' if 'TB' in pattern.upper() else 'GB'
            return f"{value}{unit}"
    
    # Просто цифры (128, 256, 512, 1024) - типичные значения памяти в ГБ
    number_match = re.search(r'\b(128|256|512|1024|2048|4096)\b', product_name, re.IGNORECASE)
    if number_match:
        value = number_match.group(1)
        return f"{value}GB"
    
    return None

def extract_color(product_name):
    """Извлекает цвет из названия товара"""
    if not product_name:
        return None
    
    # Список возможных цветов (от длинных к коротким)
    colors = [
        'Space Gray', 'Sp. Gray', 'Space Black', 'Rose Gold', 'Jet Black', 
        'Light Gold', 'Cloud White', 'Sky Blue', 'Light Blush', 'Pur Fog',
        'Blue Ocean', 'Green Alpine', 'Black Ocean', 'Mist Blue', 'Mil Lp',
        'Black', 'Blue', 'Red', 'Midnight', 'Starlight', 'Purple', 'Yellow', 
        'Green', 'Pink', 'White', 'Silver', 'Gold', 'Teal', 'Ultramarine', 
        'Desert', 'Natural', 'Lavender', 'Sage', 'Orange', 'Star', 'Mid', 
        'Plum', 'Ink', 'Nat', 'Denim', 'Link'
    ]
    
    # Сортируем цвета по длине (от длинных к коротким)
    colors_sorted = sorted(colors, key=len, reverse=True)
    
    for color in colors_sorted:
        # Ищем цвет с учетом границ слов
        pattern = r'\b' + re.escape(color) + r'\b'
        if re.search(pattern, product_name, re.IGNORECASE):
            return color
    
    return None

def extract_sim_type(country):
    """Извлекает тип SIM из поля country (eSim, Sim + eSIM и т.д.)"""
    if not country:
        return None
    
    country_str = str(country).strip()
    
    # Ищем тип SIM в строке country
    # Паттерны: "eSim", "eSIM", "Sim + eSIM", "Sim+eSIM", "Sim + eSim" и т.д.
    sim_patterns = [
        r'Sim\s*\+\s*eSIM',  # Sim + eSIM
        r'Sim\s*\+\s*eSim',  # Sim + eSim
        r'eSIM',              # eSIM
        r'eSim',              # eSim
    ]
    
    for pattern in sim_patterns:
        match = re.search(pattern, country_str, re.IGNORECASE)
        if match:
            sim_type = match.group(0)
            # Нормализуем формат
            if 'Sim + eSIM' in sim_type or 'Sim + eSim' in sim_type:
                return 'Sim + eSIM'
            elif 'eSIM' in sim_type or 'eSim' in sim_type:
                return 'eSim'
    
    return None

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start с поддержкой deep links для добавления товара"""
    # Проверяем, есть ли параметр для добавления товара предзаказа
    if message.text and "preorder_" in message.text:
        try:
            # Извлекаем ID товара предзаказа из параметра
            parts = message.text.split("preorder_")
            if len(parts) > 1:
                product_id = int(parts[1].split()[0])
                user_id = message.from_user.id
                
                product = get_preorder_product_by_id(product_id)
                if not product:
                    await message.answer("❌ Товар предзаказа не найден")
                    return
                
                # Сохраняем product_id и флаг предзаказа в FSM
                await state.update_data(product_id=product_id, is_preorder=True)
                await state.set_state(AddToCartStates.waiting_for_quantity)
                
                # Показываем товар и запрашиваем количество
                country_with_flag = get_country_with_flag(product['country'])
                final_price = calculate_price_with_markup(product['price'], user_id, is_preorder=True)
                
                await message.answer(
                    f"📦 <b>Товар предзаказа:</b>\n\n"
                    f"{product['name']}\n"
                    f"{country_with_flag}\n"
                    f"Цена: <b>{final_price}₽</b>\n\n"
                    f"Введите количество товара (число от 1 до 100):",
                    parse_mode='HTML',
                    reply_markup=get_main_keyboard(user_id)
                )
                return
        except (ValueError, IndexError):
            pass  # Если ошибка, продолжаем как обычный /start
    
    # Проверяем, есть ли параметр для добавления обычного товара
    if message.text and "add_" in message.text:
        try:
            # Извлекаем ID товара из параметра
            parts = message.text.split("add_")
            if len(parts) > 1:
                product_id = int(parts[1].split()[0])
                user_id = message.from_user.id
                
                product = get_product_by_id(product_id)
                if not product:
                    await message.answer("❌ Товар не найден")
                    return
                
                # Сохраняем product_id в FSM и переводим в состояние ожидания количества
                await state.update_data(product_id=product_id, is_preorder=False)
                await state.set_state(AddToCartStates.waiting_for_quantity)
                
                # Показываем товар и запрашиваем количество
                country_with_flag = get_country_with_flag(product['country'])
                final_price = calculate_price_with_markup(product['price'], user_id)
                
                await message.answer(
                    f"📦 <b>Товар:</b>\n\n"
                    f"{product['name']}\n"
                    f"{country_with_flag}\n"
                    f"Цена: <b>{final_price}₽</b>\n\n"
                    f"Введите количество товара (число от 1 до 100):",
                    parse_mode='HTML',
                    reply_markup=get_main_keyboard(user_id)
                )
                return
        except (ValueError, IndexError):
            pass  # Если ошибка, продолжаем как обычный /start
    
    # Обычный /start без параметров
    await state.clear()
    user_id = message.from_user.id
    user_states[user_id] = {'screen': 'main'}
    
    welcome_text = """Предзаказ BBSTORE



У вас есть возможность оформить предзаказ и выбрать расширенную гарантию — до 1 года за дополнительную плату. Все детали можно уточнить у администратора после оформления.



Условия предзаказа:

• Оплата: задаток 40%

• Срок поставки: 2–7 дней (обычно до 3 дней)

• Выдача: в нашем магазине



⸻



Обращаем ваше внимание, что сроки выполнения предзаказа могут изменяться по причинам, не зависящим от магазина.
К таким причинам относятся:

• задержки у поставщика или логистических служб;

• отсутствие нужной модели или партии товара;

• таможенные или транспортные задержки;

• производственные ограничения или прекращение выпуска устройства.



Мы заранее предупреждаем, что в отдельных случаях предзаказ может быть перенесён или отменён поставщиком.
Если выполнение предзаказа становится невозможным, мы уведомляем покупателя и возвращаем уплаченный задаток в полном объёме.



⸻



📦 Если вы находитесь не в Москве



Для покупателей из регионов доступна услуга подготовки и передачи заказа:

• аккуратно собираем и упаковываем товар;

• можем передать заказ вашему курьеру;

• можем доставить его к автобусу, поезду, самолёту или в выбранную вами транспортную компанию.



Все детали отправки и передачи заказа обсуждаются заранее с менеджером."""
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(user_id)
    )

@router.message(lambda m: m.text == "Прайс")
async def show_categories(message: types.Message, state: FSMContext):
    # Очищаем FSM состояние, если было
    await state.clear()
    user_id = message.from_user.id
    user_states[user_id] = {'screen': 'categories', 'source': 'standard'}
    
    # Получаем категории, в которых есть товары (проверяем оба source: 'standard' и 'simple')
    from db.crud import get_available_parent_categories
    from bot.keyboards.category import parent_categories
    
    # Проверяем категории для обоих source
    available_standard = get_available_parent_categories(parent_categories, 'standard')
    available_simple = get_available_parent_categories(parent_categories, 'simple')
    # Объединяем и убираем дубликаты
    available_categories = list(set(available_standard + available_simple))
    
    if not available_categories:
        await message.answer(
            "❌ В прайсе пока нет товаров.\n\n"
            "Администратор должен загрузить прайс через админку.",
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    await message.answer(
        "Выберите категорию:",
        reply_markup=get_categories_keyboard('standard')
    )

@router.message(lambda m: m.text == "Предзаказ")
async def show_preorder_info(message: types.Message, state: FSMContext):
    # Очищаем FSM состояние, если было
    await state.clear()
    user_id = message.from_user.id
    
    # Отправляем информационное сообщение о предзаказе
    preorder_text = (
        "<b>Предзаказ BBSTORE</b>\n\n"
        "У вас есть возможность оформить предзаказ и выбрать расширенную гарантию — до 1 года за дополнительную плату. Все детали можно уточнить у администратора после оформления.\n\n"
        "<b>Условия предзаказа:</b>\n"
        "• Оплата: задаток 40%\n"
        "• Срок поставки: 2–7 дней (обычно до 3 дней)\n"
        "• Выдача: в нашем магазине\n\n"
        "⸻\n\n"
        "Обращаем ваше внимание, что сроки выполнения предзаказа могут изменяться по причинам, не зависящим от магазина.\n"
        "К таким причинам относятся:\n"
        "• задержки у поставщика или логистических служб;\n"
        "• отсутствие нужной модели или партии товара;\n"
        "• таможенные или транспортные задержки;\n"
        "• производственные ограничения или прекращение выпуска устройства.\n\n"
        "Мы заранее предупреждаем, что в отдельных случаях предзаказ может быть перенесён или отменён поставщиком.\n"
        "Если выполнение предзаказа становится невозможным, мы уведомляем покупателя и возвращаем уплаченный задаток в полном объёме.\n\n"
        "⸻\n\n"
        "📦 <b>Если вы находитесь не в Москве</b>\n\n"
        "Для покупателей из регионов доступна услуга подготовки и передачи заказа:\n"
        "• аккуратно собираем и упаковываем товар;\n"
        "• можем передать заказ вашему курьеру;\n"
        "• можем доставить его к автобусу, поезду, самолёту или в выбранную вами транспортную компанию.\n\n"
        "Все детали отправки и передачи заказа обсуждаются заранее с менеджером."
    )
    
    # Получаем категории предзаказа из БД
    preorder_categories = get_preorder_categories()
    
    if not preorder_categories:
        await message.answer(
            preorder_text + "\n\n❌ В предзаказе пока нет товаров.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    user_states[user_id] = {'screen': 'preorder_categories', 'is_preorder': True}
    await message.answer(
        preorder_text,
        parse_mode='HTML',
        reply_markup=get_preorder_categories_keyboard(preorder_categories)
    )

@router.message(lambda m: m.text == "Назад")
async def go_back(message: types.Message, state: FSMContext):
    # Очищаем FSM состояние, если было
    await state.clear()
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {'screen': 'main'})
    
    # Проверяем, это предзаказ или обычный прайс
    is_preorder = user_state.get('is_preorder', False)
    
    if is_preorder:
        # Логика для предзаказа
        if user_state.get('screen') == 'preorder_products':
            # Возвращаемся к категориям предзаказа
            preorder_categories = get_preorder_categories()
            user_states[user_id] = {'screen': 'preorder_categories', 'is_preorder': True}
            await message.answer(
                "Выберите категорию:",
                reply_markup=get_preorder_categories_keyboard(preorder_categories)
            )
        else:
            # Возвращаемся в главное меню
            user_states[user_id] = {'screen': 'main'}
            await message.answer(
                'Главное меню:',
                reply_markup=get_main_keyboard(user_id)
            )
    else:
        # Логика для обычного прайса
        source = user_state.get('source', 'standard')
        
        if user_state.get('screen') == 'subcategories':
            # Возвращаемся к главному меню
            user_states[user_id] = {'screen': 'main'}
            await message.answer(
                'Главное меню:',
                reply_markup=get_main_keyboard(user_id)
            )
        elif user_state.get('screen') == 'products':
            # Возвращаемся к списку подкатегорий той же родительской категории
            parent_cat = user_state.get('parent_category')
            if parent_cat:
                # Получаем подкатегории для этой родительской категории (проверяем оба source)
                available_subcats_standard = get_available_subcategories(parent_cat, None, 'standard')
                available_subcats_simple = get_available_subcategories(parent_cat, None, 'simple')
                # Объединяем и убираем дубликаты
                available_subcats = list(set(available_subcats_standard + available_subcats_simple))
                
                # Применяем сортировку после объединения
                from db.crud import sort_categories_smart
                available_subcats = sort_categories_smart(available_subcats)
                
                if available_subcats:
                    user_states[user_id] = {'screen': 'subcategories', 'parent_category': parent_cat, 'source': source}
                    await message.answer(
                        f"Выберите подкатегорию:",
                        reply_markup=get_subcategories_keyboard(parent_cat, available_subcats)
                    )
                else:
                    # Если нет подкатегорий, возвращаемся к главному меню
                    user_states[user_id] = {'screen': 'main'}
                    await message.answer(
                        'Главное меню:',
                        reply_markup=get_main_keyboard(user_id)
                    )
            else:
                # Если нет информации о родительской категории, возвращаемся к главному меню
                user_states[user_id] = {'screen': 'main'}
                await message.answer(
                    'Главное меню:',
                    reply_markup=get_main_keyboard(user_id)
                )
        else:
            # По умолчанию возвращаемся в главное меню
            user_states[user_id] = {'screen': 'main'}
            await message.answer(
                'Главное меню:',
                reply_markup=get_main_keyboard(user_id)
            )

@router.message(lambda m: m.text == "📞 Связаться с администратором")
async def contact_admin(message: types.Message):
    """Обработчик кнопки 'Связаться с администратором'"""
    from config import ADMIN_HELP
    
    if not ADMIN_HELP:
        await message.answer(
            "❌ Администратор не настроен. Обратитесь к разработчику бота.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        return
    
    # Создаем Inline кнопку с ссылкой на администратора
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💬 Написать администратору",
            url=f"tg://user?id={ADMIN_HELP}"
        )]
    ])
    
    await message.answer(
        "📞 <b>Связаться с администратором</b>\n\n"
        "Нажмите на кнопку ниже, чтобы открыть чат с администратором:",
        parse_mode='HTML',
        reply_markup=keyboard
    )

def is_parent_category(text, user_state=None):
    """Проверяет, является ли сообщение выбором родительской категории"""
    if not text:
        return False, None
    
    # Пропускаем, если это предзаказ
    if user_state and user_state.get('is_preorder'):
        return False, None
    
    for parent_cat in parent_categories:
        if text == get_category_with_icon(parent_cat) or text == parent_cat:
            return True, parent_cat
    return False, None

def is_subcategory(text, user_state=None):
    """Проверяет, является ли сообщение выбором подкатегории"""
    if not text:
        return False, None
    
    # Пропускаем, если это предзаказ
    if user_state and user_state.get('is_preorder'):
        return False, None
    
    # Получаем динамический маппинг категорий из БД
    from db.crud import get_dynamic_parent_to_subcategories
    
    # Проверяем оба source: 'standard' и 'simple'
    for source in ['standard', 'simple']:
        dynamic_mapping = get_dynamic_parent_to_subcategories(source)
        
        # Проверяем все подкатегории из всех родительских категорий
        for parent_cat, subcats in dynamic_mapping.items():
            for subcat in subcats:
                if text == get_category_with_icon(subcat) or text == subcat:
                    return True, subcat
    
    return False, None

@router.message(lambda m: is_parent_category(m.text, user_states.get(m.from_user.id, {}))[0])
async def show_subcategories(message: types.Message):
    """Показывает подкатегории для выбранной родительской категории"""
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {'screen': 'main', 'source': 'standard'})
    _, parent_cat = is_parent_category(message.text, user_state)
    
    # Получаем source из состояния пользователя (по умолчанию 'standard')
    source = user_state.get('source', 'standard')
    
    # Сохраняем состояние
    user_states[user_id] = {'screen': 'subcategories', 'parent_category': parent_cat, 'source': source}
    
    # Получаем подкатегории, которые есть в БД (проверяем оба source: 'standard' и 'simple')
    available_subcats_standard = get_available_subcategories(parent_cat, None, 'standard')
    available_subcats_simple = get_available_subcategories(parent_cat, None, 'simple')
    # Объединяем и убираем дубликаты
    available_subcats = list(set(available_subcats_standard + available_subcats_simple))
    
    # Применяем сортировку после объединения
    from db.crud import sort_categories_smart
    available_subcats = sort_categories_smart(available_subcats)
    
    if not available_subcats:
        await message.answer("В этой категории пока нет товаров.")
        return
    
    await message.answer(
        f"Выберите подкатегорию:",
        reply_markup=get_subcategories_keyboard(parent_cat, available_subcats)
    )

    return True

@router.message(lambda m: is_subcategory(m.text, user_states.get(m.from_user.id, {}))[0])
async def show_products_by_category(message: types.Message):
    """Показывает товары выбранной подкатегории"""
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {})
    _, subcat = is_subcategory(message.text, user_state)
    
    # Получаем source из состояния пользователя (по умолчанию 'standard')
    source = user_state.get('source', 'standard')
    
    # Определяем родительскую категорию для этой подкатегории
    parent_cat = None
    from db.crud import get_dynamic_parent_to_subcategories
    
    # Проверяем оба source: 'standard' и 'simple'
    for check_source in ['standard', 'simple']:
        dynamic_mapping = get_dynamic_parent_to_subcategories(check_source)
        for parent, subcats in dynamic_mapping.items():
            if subcat in subcats:
                parent_cat = parent
                break
        if parent_cat:
            break
    
    # Сохраняем состояние
    user_states[user_id] = {
        'screen': 'products',
        'parent_category': parent_cat,
        'subcategory': subcat,
        'source': source
    }
    
    # Получаем товары из обоих source ('standard' и 'simple')
    products_standard = get_products_by_category(subcat, 'standard')
    products_simple = get_products_by_category(subcat, 'simple')
    # Объединяем товары
    products = products_standard + products_simple
    
    if not products:
        await message.answer("В этой категории пока нет товаров.")
        return
    
    # Группируем товары только по памяти
    category_header = get_category_with_icon(subcat)
    
    # Группируем по памяти
    memory_groups = OrderedDict()
    for prod in products:
        memory = extract_memory_from_name(prod['name'])
        if not memory:
            memory = 'Без памяти'  # Если память не найдена
        if memory not in memory_groups:
            memory_groups[memory] = []
        memory_groups[memory].append(prod)
    
    # Формируем сообщения с кликабельными ссылками для каждой строки товара
    header = f"<b>{category_header}</b>\n\n"
    header += "Нажмите на строку товара, чтобы добавить в корзину:\n\n"
    
    # Получаем username бота для deep links
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username
    
    current_text = header
    current_len = len(header)
    max_text_len = 3500  # Оставляем запас для текста
    is_first_message = True  # Флаг для первого сообщения
    
    # Функция для сортировки памяти (чтобы 256GB, 512GB, 1TB, 2TB шли в правильном порядке)
    def get_memory_sort_key(memory):
        if not memory or memory == 'Без памяти':
            return (999, '')
        # Извлекаем число и единицу
        match = re.search(r'(\d+)(GB|TB)', memory, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            unit = match.group(2).upper()
            # TB имеет больший вес (умножаем на 1000)
            multiplier = 1000 if unit == 'TB' else 1
            return (0, value * multiplier)
        return (999, memory)
    
    # Сортируем группы памяти
    sorted_memories = sorted(memory_groups.keys(), key=get_memory_sort_key)
    
    for memory in sorted_memories:
        memory_products = memory_groups[memory]
        
        # Заголовок для группы памяти - берем первый товар и извлекаем модель с памятью
        if memory_products:
            first_prod = memory_products[0]
            # Извлекаем базовую модель и добавляем память
            base_model = extract_base_model(first_prod['name'])
            memory_header = f"<b>📱 {base_model} {memory}</b>\n"
        else:
            memory_header = f"<b>📱 {memory}</b>\n"
        
        # Проверяем, поместится ли заголовок памяти
        if current_len + len(memory_header) > max_text_len:
            # Отправляем текущее сообщение
            await message.answer(current_text, parse_mode='HTML', disable_web_page_preview=True)
            # Начинаем новое сообщение без заголовка категории
            current_text = ""
            current_len = 0
            is_first_message = False
        
        current_text += memory_header
        current_len += len(memory_header)
        
        # Сортируем товары внутри группы памяти по цвету, типу SIM и цене
        def sort_key(prod):
            # Извлекаем цвет для сортировки
            color = extract_color(prod['name']) or ''
            # Извлекаем тип SIM
            sim_type = extract_sim_type(prod['country']) or ''
            # Сортируем: цвет, тип SIM, цена
            return (color, sim_type, prod['price'])
        
        memory_products_sorted = sorted(memory_products, key=sort_key)
        
        for prod in memory_products_sorted:
            # Извлекаем тип SIM из country
            sim_type = extract_sim_type(prod['country'])
            final_price = calculate_price_with_markup(prod['price'], user_id)
            
            # Формируем текст товара в формате: название — тип SIM, цена
            if sim_type:
                product_text = f"{prod['name']} — {sim_type}, {final_price}₽"
            else:
                product_text = f"{prod['name']}, {final_price}₽"
            
            # Формируем deep link для товара
            deep_link = f"https://t.me/{bot_username}?start=add_{prod['id']}"
            
            # Добавляем товар как кликабельную ссылку в тексте
            product_line = f"<a href=\"{deep_link}\">{product_text}</a>\n"
            
            if current_len + len(product_line) > max_text_len:
                # Отправляем текущее сообщение
                await message.answer(current_text, parse_mode='HTML', disable_web_page_preview=True)
                # Начинаем новое сообщение без заголовка категории
                current_text = ""
                current_len = 0
                is_first_message = False
            
            current_text += product_line
            current_len += len(product_line)
        
        current_text += "\n"
        current_len += 1
    
    # Отправляем последнее сообщение
    if current_len > len(header):
        await message.answer(current_text, parse_mode='HTML', disable_web_page_preview=True)
    
    # Отправляем кнопку "Назад"
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Назад")]],
        resize_keyboard=True
    )
    await message.answer("Нажмите на строку товара для добавления в корзину", reply_markup=back_keyboard)

# Обработчик ввода количества товара
@router.message(StateFilter(AddToCartStates.waiting_for_quantity))
async def process_quantity(message: types.Message, state: FSMContext):
    """Обработчик ввода количества товара для добавления в корзину"""
    user_id = message.from_user.id
    
    # Проверяем, что введено число
    try:
        # Проверяем, что message.text существует и не пустой
        if not message.text:
            await message.answer(
                "❌ Пожалуйста, введите число от 1 до 100.\n"
                "Введите количество еще раз:"
            )
            return
        
        quantity = int(message.text.strip())
        if quantity < 1 or quantity > 100:
            await message.answer(
                "❌ Количество должно быть от 1 до 100.\n"
                "Введите количество еще раз:"
            )
            return
        
        # Получаем product_id и флаг предзаказа из FSM
        data = await state.get_data()
        product_id = data.get('product_id')
        is_preorder = data.get('is_preorder', False)
        
        if not product_id:
            await message.answer("❌ Ошибка: товар не найден. Попробуйте выбрать товар снова.")
            await state.clear()
            return
        
        # Получаем информацию о товаре
        if is_preorder:
            product = get_preorder_product_by_id(product_id)
            if not product:
                await message.answer("❌ Товар предзаказа не найден")
                await state.clear()
                return
            
            # Добавляем товар в корзину предзаказа
            add_to_preorder_cart(user_id, product_id, quantity=quantity)
            cart_type = "корзину предзаказа"
        else:
            product = get_product_by_id(product_id)
            if not product:
                await message.answer("❌ Товар не найден")
                await state.clear()
                return
            
            # Добавляем товар в обычную корзину
            add_to_cart(user_id, product_id, quantity=quantity)
            cart_type = "корзину"
        
        country_with_flag = get_country_with_flag(product['country'])
        # Применяем правильную наценку в зависимости от типа товара
        final_price = calculate_price_with_markup(product['price'], user_id, is_preorder=is_preorder)
        
        # Очищаем состояние
        await state.clear()
        
        await message.answer(
            f"✅ <b>Товар добавлен в {cart_type}!</b>\n\n"
            f"{product['name']}, {country_with_flag}\n"
            f"Количество: <b>{quantity} шт.</b>\n"
            f"Цена за шт.: <b>{final_price}₽</b>\n"
            f"Итого: <b>{final_price * quantity}₽</b>\n\n"
            f"Перейдите в 'Корзина' для оформления заказа.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user_id)
        )
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите число от 1 до 100.\n"
            "Введите количество еще раз:"
        )


# Обработчик просмотра корзины
@router.message(lambda m: m.text == "Корзина")
async def show_cart(message: types.Message, state: FSMContext):
    """Показывает корзину пользователя (обычную и предзаказа)"""
    # Очищаем FSM состояние, если было
    await state.clear()
    user_id = message.from_user.id
    
    # Получаем обе корзины
    cart_items = get_cart(user_id)
    preorder_cart_items = get_preorder_cart(user_id)
    
    if not cart_items and not preorder_cart_items:
        await message.answer(
            "🛒 <b>Ваша корзина пуста</b>\n\n"
            "Добавьте товары из прайса или предзаказа, нажав на строку товара.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    # Формируем сообщение с товарами
    text = "🛒 <b>Ваша корзина</b>\n\n"
    total_price = 0
    keyboard_buttons = []
    
    # Обычные товары
    if cart_items:
        text += "<b>Обычные товары:</b>\n"
        for item in cart_items:
            country_with_flag = get_country_with_flag(item['country'])
            final_price = calculate_price_with_markup(item['price'], user_id)
            item_price = final_price * item['quantity']
            total_price += item_price
            text += f"{item['name']}, {country_with_flag}\n"
            text += f"Количество: <b>{item['quantity']} шт.</b> × {final_price}₽ = {item_price}₽\n\n"
            
            # Кнопки для изменения количества и удаления
            decrease_callback = CartCallback(action="change_qty", cart_id=item['cart_id'], quantity=item['quantity'] - 1).pack()
            increase_callback = CartCallback(action="change_qty", cart_id=item['cart_id'], quantity=item['quantity'] + 1).pack()
            remove_callback = CartCallback(action="remove", cart_id=item['cart_id']).pack()
            
            # Создаем строку с кнопками: [-] [количество] [+] [Удалить]
            keyboard_buttons.append([
                InlineKeyboardButton(text="➖", callback_data=decrease_callback),
                InlineKeyboardButton(text=f"{item['quantity']}", callback_data="noop"),
                InlineKeyboardButton(text="➕", callback_data=increase_callback),
                InlineKeyboardButton(text="❌", callback_data=remove_callback)
            ])
    
    # Товары предзаказа
    if preorder_cart_items:
        text += "<b>Товары предзаказа:</b>\n"
        for item in preorder_cart_items:
            country_with_flag = get_country_with_flag(item['country'])
            final_price = calculate_price_with_markup(item['price'], user_id, is_preorder=True)
            item_price = final_price * item['quantity']
            total_price += item_price
            text += f"{item['name']}, {country_with_flag}\n"
            text += f"Количество: <b>{item['quantity']} шт.</b> × {final_price}₽ = {item_price}₽\n\n"
            
            # Кнопки для изменения количества и удаления предзаказа
            decrease_callback = CartCallback(action="change_qty_preorder", cart_id=item['cart_id'], quantity=item['quantity'] - 1).pack()
            increase_callback = CartCallback(action="change_qty_preorder", cart_id=item['cart_id'], quantity=item['quantity'] + 1).pack()
            remove_callback = CartCallback(action="remove_preorder", cart_id=item['cart_id']).pack()
            
            keyboard_buttons.append([
                InlineKeyboardButton(text="➖", callback_data=decrease_callback),
                InlineKeyboardButton(text=f"{item['quantity']}", callback_data="noop"),
                InlineKeyboardButton(text="➕", callback_data=increase_callback),
                InlineKeyboardButton(text="❌", callback_data=remove_callback)
            ])
    
    text += f"<b>Итого: {total_price}₽</b>"
    
    # Добавляем кнопку оформления заказа
    checkout_callback = CartCallback(action="checkout").pack()
    keyboard_buttons.append([InlineKeyboardButton(
        text="✅ Оформить заказ",
        callback_data=checkout_callback
    )])
    
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(
        text,
        parse_mode='HTML',
        reply_markup=inline_keyboard
    )

# Обработчик для кнопки количества (неактивная кнопка)
@router.callback_query(lambda c: c.data == "noop")
async def handle_noop_callback(callback: types.CallbackQuery):
    """Обработчик для неактивной кнопки (показывает количество)"""
    await callback.answer()

# Обработчик callback для корзины (удаление, оформление)
@router.callback_query(lambda c: c.data and c.data.startswith("cart:"))
async def handle_cart_callback(callback: types.CallbackQuery):
    """Обработчик callback для корзины"""
    print(f"DEBUG: handle_cart_callback вызван! callback.data={callback.data}")
    
    # Парсим callback_data вручную
    try:
        callback_data = CartCallback.unpack(callback.data)
        print(f"DEBUG: Распарсен callback_data: action={callback_data.action}, cart_id={callback_data.cart_id}")
    except Exception as e:
        print(f"DEBUG: Ошибка парсинга callback_data: {e}")
        await callback.answer()
        return
    
    user_id = callback.from_user.id
    
    # Отвечаем на callback сразу, чтобы убрать индикатор загрузки
    await callback.answer()
    
    if callback_data.action == "change_qty_preorder":
        # Обработка изменения количества для предзаказа
        if callback_data.cart_id and callback_data.quantity is not None:
            if callback_data.quantity <= 0:
                removed = remove_from_preorder_cart(user_id, callback_data.cart_id)
                if removed:
                    await callback.answer("✅ Товар удален из корзины предзаказа")
                else:
                    await callback.answer("❌ Ошибка при удалении товара", show_alert=True)
            else:
                updated = update_preorder_cart_quantity(user_id, callback_data.cart_id, callback_data.quantity)
                if updated:
                    await callback.answer(f"✅ Количество изменено: {callback_data.quantity} шт.")
                else:
                    await callback.answer("❌ Ошибка при изменении количества", show_alert=True)
            
            # Перезагружаем корзину - просто обновляем сообщение
            cart_items = get_cart(user_id)
            preorder_cart_items = get_preorder_cart(user_id)
            
            if not cart_items and not preorder_cart_items:
                await callback.message.edit_text(
                    "🛒 <b>Ваша корзина пуста</b>\n\n"
                    "Добавьте товары из прайса или предзаказа, нажав на строку товара.",
                    parse_mode='HTML'
                )
                return
            
            # Формируем сообщение с товарами (копируем логику из show_cart)
            text = "🛒 <b>Ваша корзина</b>\n\n"
            total_price = 0
            keyboard_buttons = []
            
            if cart_items:
                text += "<b>Обычные товары:</b>\n"
                for item in cart_items:
                    country_with_flag = get_country_with_flag(item['country'])
                    final_price = calculate_price_with_markup(item['price'], user_id)
                    item_price = final_price * item['quantity']
                    total_price += item_price
                    text += f"{item['name']}, {country_with_flag}\n"
                    text += f"Количество: <b>{item['quantity']} шт.</b> × {final_price}₽ = {item_price}₽\n\n"
                    
                    decrease_callback = CartCallback(action="change_qty", cart_id=item['cart_id'], quantity=item['quantity'] - 1).pack()
                    increase_callback = CartCallback(action="change_qty", cart_id=item['cart_id'], quantity=item['quantity'] + 1).pack()
                    remove_callback = CartCallback(action="remove", cart_id=item['cart_id']).pack()
                    
                    keyboard_buttons.append([
                        InlineKeyboardButton(text="➖", callback_data=decrease_callback),
                        InlineKeyboardButton(text=f"{item['quantity']}", callback_data="noop"),
                        InlineKeyboardButton(text="➕", callback_data=increase_callback),
                        InlineKeyboardButton(text="❌", callback_data=remove_callback)
                    ])
            
            if preorder_cart_items:
                text += "<b>Товары предзаказа:</b>\n"
                for item in preorder_cart_items:
                    country_with_flag = get_country_with_flag(item['country'])
                    final_price = calculate_price_with_markup(item['price'], user_id, is_preorder=True)
                    item_price = final_price * item['quantity']
                    total_price += item_price
                    text += f"{item['name']}, {country_with_flag}\n"
                    text += f"Количество: <b>{item['quantity']} шт.</b> × {final_price}₽ = {item_price}₽\n\n"
                    
                    decrease_callback = CartCallback(action="change_qty_preorder", cart_id=item['cart_id'], quantity=item['quantity'] - 1).pack()
                    increase_callback = CartCallback(action="change_qty_preorder", cart_id=item['cart_id'], quantity=item['quantity'] + 1).pack()
                    remove_callback = CartCallback(action="remove_preorder", cart_id=item['cart_id']).pack()
                    
                    keyboard_buttons.append([
                        InlineKeyboardButton(text="➖", callback_data=decrease_callback),
                        InlineKeyboardButton(text=f"{item['quantity']}", callback_data="noop"),
                        InlineKeyboardButton(text="➕", callback_data=increase_callback),
                        InlineKeyboardButton(text="❌", callback_data=remove_callback)
                    ])
            
            text += f"<b>Итого: {total_price}₽</b>"
            
            checkout_callback = CartCallback(action="checkout").pack()
            keyboard_buttons.append([InlineKeyboardButton(
                text="✅ Оформить заказ",
                callback_data=checkout_callback
            )])
            
            inline_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            try:
                await callback.message.edit_text(
                    text,
                    parse_mode='HTML',
                    reply_markup=inline_keyboard
                )
            except:
                await callback.message.answer(
                    text,
                    parse_mode='HTML',
                    reply_markup=inline_keyboard
                )
            return
    
    if callback_data.action == "remove_preorder":
        # Обработка удаления товара предзаказа
        if callback_data.cart_id:
            removed = remove_from_preorder_cart(user_id, callback_data.cart_id)
            if removed:
                await callback.answer("✅ Товар удален из корзины предзаказа")
                # Перезагружаем корзину (используем ту же логику)
                cart_items = get_cart(user_id)
                preorder_cart_items = get_preorder_cart(user_id)
                
                if not cart_items and not preorder_cart_items:
                    await callback.message.edit_text(
                        "🛒 <b>Ваша корзина пуста</b>\n\n"
                        "Добавьте товары из прайса или предзаказа, нажав на строку товара.",
                        parse_mode='HTML'
                    )
                    return
                
                text = "🛒 <b>Ваша корзина</b>\n\n"
                total_price = 0
                keyboard_buttons = []
                
                if cart_items:
                    text += "<b>Обычные товары:</b>\n"
                    for item in cart_items:
                        country_with_flag = get_country_with_flag(item['country'])
                        final_price = calculate_price_with_markup(item['price'], user_id)
                        item_price = final_price * item['quantity']
                        total_price += item_price
                        text += f"{item['name']}, {country_with_flag}\n"
                        text += f"Количество: <b>{item['quantity']} шт.</b> × {final_price}₽ = {item_price}₽\n\n"
                        
                        decrease_callback = CartCallback(action="change_qty", cart_id=item['cart_id'], quantity=item['quantity'] - 1).pack()
                        increase_callback = CartCallback(action="change_qty", cart_id=item['cart_id'], quantity=item['quantity'] + 1).pack()
                        remove_callback = CartCallback(action="remove", cart_id=item['cart_id']).pack()
                        
                        keyboard_buttons.append([
                            InlineKeyboardButton(text="➖", callback_data=decrease_callback),
                            InlineKeyboardButton(text=f"{item['quantity']}", callback_data="noop"),
                            InlineKeyboardButton(text="➕", callback_data=increase_callback),
                            InlineKeyboardButton(text="❌", callback_data=remove_callback)
                        ])
                
                if preorder_cart_items:
                    text += "<b>Товары предзаказа:</b>\n"
                    for item in preorder_cart_items:
                        country_with_flag = get_country_with_flag(item['country'])
                        final_price = calculate_price_with_markup(item['price'], user_id, is_preorder=True)
                        item_price = final_price * item['quantity']
                        total_price += item_price
                        text += f"{item['name']}, {country_with_flag}\n"
                        text += f"Количество: <b>{item['quantity']} шт.</b> × {final_price}₽ = {item_price}₽\n\n"
                        
                        decrease_callback = CartCallback(action="change_qty_preorder", cart_id=item['cart_id'], quantity=item['quantity'] - 1).pack()
                        increase_callback = CartCallback(action="change_qty_preorder", cart_id=item['cart_id'], quantity=item['quantity'] + 1).pack()
                        remove_callback = CartCallback(action="remove_preorder", cart_id=item['cart_id']).pack()
                        
                        keyboard_buttons.append([
                            InlineKeyboardButton(text="➖", callback_data=decrease_callback),
                            InlineKeyboardButton(text=f"{item['quantity']}", callback_data="noop"),
                            InlineKeyboardButton(text="➕", callback_data=increase_callback),
                            InlineKeyboardButton(text="❌", callback_data=remove_callback)
                        ])
                
                text += f"<b>Итого: {total_price}₽</b>"
                
                checkout_callback = CartCallback(action="checkout").pack()
                keyboard_buttons.append([InlineKeyboardButton(
                    text="✅ Оформить заказ",
                    callback_data=checkout_callback
                )])
                
                inline_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                
                try:
                    await callback.message.edit_text(
                        text,
                        parse_mode='HTML',
                        reply_markup=inline_keyboard
                    )
                except:
                    await callback.message.answer(
                        text,
                        parse_mode='HTML',
                        reply_markup=inline_keyboard
                    )
            else:
                await callback.answer("❌ Ошибка при удалении товара", show_alert=True)
        return
    
    if callback_data.action == "change_qty":
        if callback_data.cart_id and callback_data.quantity is not None:
            if callback_data.quantity <= 0:
                # Если количество стало 0 или меньше, удаляем товар
                removed = remove_from_cart(user_id, callback_data.cart_id)
                if removed:
                    await callback.answer("✅ Товар удален из корзины")
                else:
                    await callback.answer("❌ Ошибка при удалении товара", show_alert=True)
            else:
                # Обновляем количество
                updated = update_cart_quantity(user_id, callback_data.cart_id, callback_data.quantity)
                if updated:
                    await callback.answer(f"✅ Количество изменено: {callback_data.quantity} шт.")
                else:
                    await callback.answer("❌ Ошибка при изменении количества", show_alert=True)
            
            # Обновляем сообщение с корзиной
            cart_items = get_cart(user_id)
            
            if not cart_items:
                await callback.message.edit_text(
                    "🛒 <b>Ваша корзина пуста</b>\n\n"
                    "Добавьте товары из прайса, нажав на строку товара.",
                    parse_mode='HTML'
                )
                return
            
            # Формируем сообщение с товарами
            text = "🛒 <b>Ваша корзина</b>\n\n"
            total_price = 0
            keyboard_buttons = []
            
            for item in cart_items:
                country_with_flag = get_country_with_flag(item['country'])
                final_price = calculate_price_with_markup(item['price'], user_id)
                item_price = final_price * item['quantity']
                total_price += item_price
                text += f"{item['name']}, {country_with_flag}\n"
                text += f"Количество: <b>{item['quantity']} шт.</b> × {final_price}₽ = {item_price}₽\n\n"
                
                # Кнопки для изменения количества и удаления
                decrease_callback = CartCallback(action="change_qty", cart_id=item['cart_id'], quantity=item['quantity'] - 1).pack()
                increase_callback = CartCallback(action="change_qty", cart_id=item['cart_id'], quantity=item['quantity'] + 1).pack()
                remove_callback = CartCallback(action="remove", cart_id=item['cart_id']).pack()
                
                keyboard_buttons.append([
                    InlineKeyboardButton(text="➖", callback_data=decrease_callback),
                    InlineKeyboardButton(text=f"{item['quantity']}", callback_data="noop"),
                    InlineKeyboardButton(text="➕", callback_data=increase_callback),
                    InlineKeyboardButton(text="❌", callback_data=remove_callback)
                ])
            
            text += f"<b>Итого: {total_price}₽</b>"
            
            # Добавляем кнопку оформления заказа
            checkout_callback = CartCallback(action="checkout").pack()
            keyboard_buttons.append([InlineKeyboardButton(
                text="✅ Оформить заказ",
                callback_data=checkout_callback
            )])
            
            inline_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            try:
                await callback.message.edit_text(
                    text,
                    parse_mode='HTML',
                    reply_markup=inline_keyboard
                )
            except:
                await callback.message.answer(
                    text,
                    parse_mode='HTML',
                    reply_markup=inline_keyboard
                )
            return
    
    if callback_data.action == "remove":
        if callback_data.cart_id:
            removed = remove_from_cart(user_id, callback_data.cart_id)
            if removed:
                # Уже ответили выше, просто отправляем сообщение
                await callback.message.answer("✅ Товар удален из корзины")
                
                # Обновляем сообщение с корзиной
                cart_items = get_cart(user_id)
                
                if not cart_items:
                    await callback.message.edit_text(
                        "🛒 <b>Ваша корзина пуста</b>\n\n"
                        "Добавьте товары из прайса, нажав на строку товара.",
                        parse_mode='HTML'
                    )
                    return
                
                # Формируем сообщение с товарами
                text = "🛒 <b>Ваша корзина</b>\n\n"
                total_price = 0
                keyboard_buttons = []
                
                for item in cart_items:
                    country_with_flag = get_country_with_flag(item['country'])
                    final_price = calculate_price_with_markup(item['price'], user_id)
                    item_price = final_price * item['quantity']
                    total_price += item_price
                    text += f"{item['name']}, {country_with_flag}\n"
                    text += f"Количество: <b>{item['quantity']} шт.</b> × {final_price}₽ = {item_price}₽\n\n"
                    
                    # Кнопки для изменения количества и удаления
                    decrease_callback = CartCallback(action="change_qty", cart_id=item['cart_id'], quantity=item['quantity'] - 1).pack()
                    increase_callback = CartCallback(action="change_qty", cart_id=item['cart_id'], quantity=item['quantity'] + 1).pack()
                    remove_callback = CartCallback(action="remove", cart_id=item['cart_id']).pack()
                    
                    keyboard_buttons.append([
                        InlineKeyboardButton(text="➖", callback_data=decrease_callback),
                        InlineKeyboardButton(text=f"{item['quantity']}", callback_data="noop"),
                        InlineKeyboardButton(text="➕", callback_data=increase_callback),
                        InlineKeyboardButton(text="❌", callback_data=remove_callback)
                    ])
                
                text += f"<b>Итого: {total_price}₽</b>"
                
                # Добавляем кнопку оформления заказа
                keyboard_buttons.append([InlineKeyboardButton(
                    text="✅ Оформить заказ",
                    callback_data=CartCallback(action="checkout").pack()
                )])
                
                inline_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                
                try:
                    await callback.message.edit_text(
                        text,
                        parse_mode='HTML',
                        reply_markup=inline_keyboard
                    )
                except:
                    # Если не удалось обновить сообщение, отправляем новое
                    await callback.message.answer(
                        text,
                        parse_mode='HTML',
                        reply_markup=inline_keyboard
                    )
            else:
                await callback.answer("❌ Ошибка при удалении товара", show_alert=True)
    
    elif callback_data.action == "checkout":
        print(f"DEBUG: Обработка checkout для user_id={user_id}")
        cart_items = get_cart(user_id)
        preorder_cart_items = get_preorder_cart(user_id)
        total_items = (len(cart_items) if cart_items else 0) + (len(preorder_cart_items) if preorder_cart_items else 0)
        print(f"DEBUG: Товаров в корзине: {len(cart_items) if cart_items else 0}, товаров предзаказа: {len(preorder_cart_items) if preorder_cart_items else 0}, всего: {total_items}")
        if not cart_items and not preorder_cart_items:
            # Показываем alert, так как уже ответили выше
            try:
                await callback.message.answer("❌ Корзина пуста")
            except:
                pass
            return
        
        # Создаем заказ
        order_id = create_order(
            user_id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name
        )
        
        if order_id:
            # Показываем alert, так как уже ответили выше
            try:
                await callback.message.answer("✅ Заказ оформлен!")
            except:
                pass
            await callback.message.answer(
                f"✅ <b>Заказ #{order_id} успешно оформлен!</b>\n\n"
                "Администратор получит уведомление о вашем заказе.",
                parse_mode='HTML',
                reply_markup=get_main_keyboard(callback.from_user.id)
            )
            
            # Отправляем уведомление админу
            from config import ADMIN_IDS
            bot = callback.bot
            
            order = get_order(order_id)
            if order:
                admin_text = f"📦 <b>Новый заказ #{order_id}</b>\n\n"
                admin_text += f"👤 <b>Пользователь:</b>\n"
                if order['user_username']:
                    admin_text += f"@{order['user_username']}\n"
                admin_text += f"Имя: {order['user_first_name'] or 'Не указано'}\n"
                admin_text += f"Фамилия: {order['user_last_name'] or 'Не указано'}\n"
                admin_text += f"ID: <code>{order['user_id']}</code>\n"
                admin_text += f"Ссылка: <a href='tg://user?id={order['user_id']}'>Написать пользователю</a>\n\n"
                admin_text += f"<b>Позиции:</b>\n"
                
                for item in order['items']:
                    admin_text += f"• {item['product_name']}\n"
                    admin_text += f"  Количество: {item['quantity']} шт. × {item['price']}₽ = {item['quantity'] * item['price']}₽\n"
                
                admin_text += f"\n<b>Итого: {order['total_price']}₽</b>"
                
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(admin_id, admin_text, parse_mode='HTML')
                    except:
                        pass
        else:
            try:
                await callback.message.answer("❌ Ошибка при оформлении заказа")
            except:
                pass

# Функция-фильтр для проверки, что это выбор категории предзаказа
def is_preorder_category_selection(message: types.Message) -> bool:
    """Проверяет, является ли сообщение выбором категории предзаказа"""
    if not message.text:
        return False
    
    # Исключаем системные кнопки
    system_buttons = ["Прайс", "Предзаказ", "Корзина", "Админка", "📞 Связаться с администратором", "Назад", 
                      "📊 Загрузить прайс", "📦 Прайс предзаказа", "⚙️ Настройка наценки",
                      "📈 Текущая наценка", "📋 Статистика", "🔙 Назад", "📦 Заказы",
                      "👤 Персональные проценты"]
    if message.text in system_buttons:
        return False
    
    # Проверяем состояние пользователя
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {})
    
    # Должно быть в режиме предзаказа и на экране категорий
    is_preorder = user_state.get('is_preorder', False)
    screen = user_state.get('screen', '')
    
    if not is_preorder or screen != 'preorder_categories':
        return False
    
    # Проверяем, что это не админ (но только если он не в режиме предзаказа)
    from config import ADMIN_IDS
    if user_id in ADMIN_IDS:
        # Админы тоже могут использовать предзаказ, но только если они явно в этом режиме
        # Проверка уже сделана выше через is_preorder
        pass
    
    # Проверяем, что это действительно категория из предзаказа
    preorder_categories = get_preorder_categories()
    if not preorder_categories:
        return False
    
    category_text = message.text
    
    # Убираем иконку из текста для сравнения
    category_clean = category_text
    for icon in category_icons.values():
        if category_text.startswith(icon + " "):
            category_clean = category_text[len(icon) + 1:].strip()
            break
    
    # Проверяем, есть ли такая категория в предзаказе
    return category_clean in preorder_categories

# Обработчик выбора категории предзаказа (должен быть в конце, после всех специфичных обработчиков)
@router.message(is_preorder_category_selection)
async def handle_preorder_category(message: types.Message, state: FSMContext):
    """Обработчик выбора категории предзаказа"""
    user_id = message.from_user.id
    category_text = message.text
    
    # Убираем иконку из текста для сравнения
    category_clean = category_text
    for icon in category_icons.values():
        if category_text.startswith(icon + " "):
            category_clean = category_text[len(icon) + 1:].strip()
            break
    
    # Получаем товары предзаказа по категории (проверка категории уже была в фильтре)
    products = get_preorder_products_by_category(category_clean)
    if not products:
        await message.answer("В этой категории предзаказа пока нет товаров.")
        return
    
    # Сохраняем состояние
    user_states[user_id] = {
        'screen': 'preorder_products',
        'category': category_clean,
        'is_preorder': True
    }
    
    # Группируем товары только по памяти
    category_header = get_category_with_icon(category_clean)
    
    # Группируем по памяти
    memory_groups = OrderedDict()
    for prod in products:
        memory = extract_memory_from_name(prod['name'])
        if not memory:
            memory = 'Без памяти'  # Если память не найдена
        if memory not in memory_groups:
            memory_groups[memory] = []
        memory_groups[memory].append(prod)
    
    # Формируем сообщения с кликабельными ссылками для каждой строки товара
    header = f"<b>{category_header}</b>\n\n"
    header += "Нажмите на строку товара, чтобы добавить в корзину предзаказа:\n\n"
    
    # Получаем username бота для deep links
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username
    
    current_text = header
    current_len = len(header)
    max_text_len = 3500  # Оставляем запас для текста
    is_first_message = True  # Флаг для первого сообщения
    
    # Функция для сортировки памяти (чтобы 256GB, 512GB, 1TB, 2TB шли в правильном порядке)
    def get_memory_sort_key(memory):
        if not memory or memory == 'Без памяти':
            return (999, '')
        # Извлекаем число и единицу
        match = re.search(r'(\d+)(GB|TB)', memory, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            unit = match.group(2).upper()
            # TB имеет больший вес (умножаем на 1000)
            multiplier = 1000 if unit == 'TB' else 1
            return (0, value * multiplier)
        return (999, memory)
    
    # Сортируем группы памяти
    sorted_memories = sorted(memory_groups.keys(), key=get_memory_sort_key)
    
    for memory in sorted_memories:
        memory_products = memory_groups[memory]
        
        # Заголовок для группы памяти - берем первый товар и извлекаем модель с памятью
        if memory_products:
            first_prod = memory_products[0]
            # Извлекаем базовую модель и добавляем память
            base_model = extract_base_model(first_prod['name'])
            memory_header = f"<b>📱 {base_model} {memory}</b>\n"
        else:
            memory_header = f"<b>📱 {memory}</b>\n"
        
        # Проверяем, поместится ли заголовок памяти
        if current_len + len(memory_header) > max_text_len:
            # Отправляем текущее сообщение
            await message.answer(current_text, parse_mode='HTML', disable_web_page_preview=True)
            # Начинаем новое сообщение без заголовка категории
            current_text = ""
            current_len = 0
            is_first_message = False
        
        current_text += memory_header
        current_len += len(memory_header)
        
        # Сортируем товары внутри группы памяти по цвету, типу SIM и цене
        def sort_key(prod):
            # Извлекаем цвет для сортировки
            color = extract_color(prod['name']) or ''
            # Извлекаем тип SIM
            sim_type = extract_sim_type(prod['country']) or ''
            # Сортируем: цвет, тип SIM, цена
            return (color, sim_type, prod['price'])
        
        memory_products_sorted = sorted(memory_products, key=sort_key)
        
        for prod in memory_products_sorted:
            # Извлекаем тип SIM из country
            sim_type = extract_sim_type(prod['country'])
            final_price = calculate_price_with_markup(prod['price'], user_id, is_preorder=True)
            
            # Формируем текст товара в формате: название — тип SIM, цена
            if sim_type:
                product_text = f"{prod['name']} — {sim_type}, {final_price}₽"
            else:
                product_text = f"{prod['name']}, {final_price}₽"
            
            # Формируем deep link для товара предзаказа
            deep_link = f"https://t.me/{bot_username}?start=preorder_{prod['id']}"
            
            # Добавляем товар как кликабельную ссылку в тексте
            product_line = f"<a href=\"{deep_link}\">{product_text}</a>\n"
            
            if current_len + len(product_line) > max_text_len:
                # Отправляем текущее сообщение
                await message.answer(current_text, parse_mode='HTML', disable_web_page_preview=True)
                # Начинаем новое сообщение без заголовка категории
                current_text = ""
                current_len = 0
                is_first_message = False
            
            current_text += product_line
            current_len += len(product_line)
        
        current_text += "\n"
        current_len += 1
    
    # Отправляем последнее сообщение
    if current_len > len(header):
        await message.answer(current_text, parse_mode='HTML', disable_web_page_preview=True)
    
    # Отправляем кнопку "Назад"
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    back_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Назад")]],
        resize_keyboard=True
    )
    await message.answer("Нажмите на строку товара для добавления в корзину предзаказа", reply_markup=back_keyboard)
