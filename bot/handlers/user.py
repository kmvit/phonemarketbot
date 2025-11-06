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
    parent_categories, parent_to_subcategories, get_category_with_icon, category_icons
)
from db.crud import (
    get_products_by_category, get_available_subcategories, add_to_cart,
    get_cart, remove_from_cart, clear_cart, create_order, get_product_by_id, get_order,
    update_cart_quantity
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
        return "🌍 Не указано"
    
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

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start с поддержкой deep links для добавления товара"""
    # Проверяем, есть ли параметр для добавления товара
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
                await state.update_data(product_id=product_id)
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
                    reply_markup=get_main_keyboard()
                )
                return
        except (ValueError, IndexError):
            pass  # Если ошибка, продолжаем как обычный /start
    
    # Обычный /start без параметров
    await state.clear()
    user_id = message.from_user.id
    user_states[user_id] = {'screen': 'main'}
    await message.answer(
        'Добро пожаловать! Выберите действие ниже:',
        reply_markup=get_main_keyboard()
    )

@router.message(lambda m: m.text == "Прайс")
async def show_categories(message: types.Message, state: FSMContext):
    # Очищаем FSM состояние, если было
    await state.clear()
    user_id = message.from_user.id
    user_states[user_id] = {'screen': 'categories'}
    await message.answer(
        "Выберите категорию:",
        reply_markup=get_categories_keyboard()
    )

@router.message(lambda m: m.text == "Назад")
async def go_back(message: types.Message, state: FSMContext):
    # Очищаем FSM состояние, если было
    await state.clear()
    user_id = message.from_user.id
    user_state = user_states.get(user_id, {'screen': 'main'})
    
    # Определяем, куда вернуться на основе текущего состояния
    if user_state.get('screen') == 'subcategories':
        # Возвращаемся к списку родительских категорий
        user_states[user_id] = {'screen': 'categories'}
        await message.answer(
            "Выберите категорию:",
            reply_markup=get_categories_keyboard()
        )
    elif user_state.get('screen') == 'products':
        # Возвращаемся к списку подкатегорий
        parent_cat = user_state.get('parent_category')
        if parent_cat:
            possible_subcats = parent_to_subcategories.get(parent_cat, [])
            available_subcats = get_available_subcategories(parent_cat, possible_subcats)
            
            if available_subcats:
                user_states[user_id] = {'screen': 'subcategories', 'parent_category': parent_cat}
                await message.answer(
                    f"Выберите подкатегорию:",
                    reply_markup=get_subcategories_keyboard(parent_cat, available_subcats)
                )
            else:
                # Если нет подкатегорий, возвращаемся к категориям
                user_states[user_id] = {'screen': 'categories'}
                await message.answer(
                    "Выберите категорию:",
                    reply_markup=get_categories_keyboard()
                )
        else:
            # Если нет информации о родительской категории, возвращаемся к категориям
            user_states[user_id] = {'screen': 'categories'}
            await message.answer(
                "Выберите категорию:",
                reply_markup=get_categories_keyboard()
            )
    else:
        # По умолчанию возвращаемся в главное меню
        user_states[user_id] = {'screen': 'main'}
        await message.answer(
            'Главное меню:',
            reply_markup=get_main_keyboard()
        )

@router.message(lambda m: m.text == "Помощь")
async def help_menu(message: types.Message):
    await message.answer("Это бот для просмотра прайса. Выберите 'Прайс' для просмотра товаров.")

def is_parent_category(text):
    """Проверяет, является ли сообщение выбором родительской категории"""
    if not text:
        return False, None
    for parent_cat in parent_categories:
        if text == get_category_with_icon(parent_cat) or text == parent_cat:
            return True, parent_cat
    return False, None

def is_subcategory(text):
    """Проверяет, является ли сообщение выбором подкатегории"""
    if not text:
        return False, None
    # Проверяем все подкатегории из всех родительских категорий
    for parent_cat, subcats in parent_to_subcategories.items():
        for subcat in subcats:
            if text == get_category_with_icon(subcat) or text == subcat:
                return True, subcat
    return False, None

@router.message(lambda m: is_parent_category(m.text)[0])
async def show_subcategories(message: types.Message):
    """Показывает подкатегории для выбранной родительской категории"""
    user_id = message.from_user.id
    _, parent_cat = is_parent_category(message.text)
    
    # Сохраняем состояние
    user_states[user_id] = {'screen': 'subcategories', 'parent_category': parent_cat}
    
    # Получаем подкатегории, которые есть в БД
    possible_subcats = parent_to_subcategories.get(parent_cat, [])
    available_subcats = get_available_subcategories(parent_cat, possible_subcats)
    
    if not available_subcats:
        await message.answer("В этой категории пока нет товаров.")
        return
    
    await message.answer(
        f"Выберите подкатегорию:",
        reply_markup=get_subcategories_keyboard(parent_cat, available_subcats)
    )

@router.message(lambda m: is_subcategory(m.text)[0])
async def show_products_by_category(message: types.Message):
    """Показывает товары выбранной подкатегории"""
    user_id = message.from_user.id
    _, subcat = is_subcategory(message.text)
    
    # Определяем родительскую категорию для этой подкатегории
    parent_cat = None
    for parent, subcats in parent_to_subcategories.items():
        if subcat in subcats:
            parent_cat = parent
            break
    
    # Сохраняем состояние
    user_states[user_id] = {
        'screen': 'products',
        'parent_category': parent_cat,
        'subcategory': subcat
    }
    
    products = get_products_by_category(subcat)
    if not products:
        await message.answer("В этой категории пока нет товаров.")
        return
    
    # Группируем товары по базовой модели
    category_header = get_category_with_icon(subcat)
    grouped_products = OrderedDict()
    for prod in products:
        base_model = extract_base_model(prod['name'])
        if base_model not in grouped_products:
            grouped_products[base_model] = []
        grouped_products[base_model].append(prod)
    
    # Формируем сообщения с кликабельными ссылками для каждой строки товара
    header = f"<b>{category_header}</b>\n\n"
    header += "Нажмите на строку товара, чтобы добавить в корзину:\n\n"
    
    # Получаем username бота для deep links
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username
    
    current_text = header
    current_len = len(header)
    max_text_len = 3500  # Оставляем запас для текста
    
    for base_model, model_products in grouped_products.items():
        model_header = f"<b>{base_model}</b>\n"
        
        # Проверяем, поместится ли заголовок модели
        if current_len + len(model_header) > max_text_len:
            # Отправляем текущее сообщение
            await message.answer(current_text, parse_mode='HTML', disable_web_page_preview=True)
            # Начинаем новое сообщение
            current_text = header
            current_len = len(header)
        
        current_text += model_header
        current_len += len(model_header)
        
        for prod in model_products:
            country_with_flag = get_country_with_flag(prod['country'])
            final_price = calculate_price_with_markup(prod['price'], user_id)
            product_text = f"{prod['name']}, {country_with_flag}, {final_price}₽"
            
            # Формируем deep link для товара
            deep_link = f"https://t.me/{bot_username}?start=add_{prod['id']}"
            
            # Добавляем товар как кликабельную ссылку в тексте
            product_line = f"<a href=\"{deep_link}\">{product_text}</a>\n"
            
            if current_len + len(product_line) > max_text_len:
                # Отправляем текущее сообщение
                await message.answer(current_text, parse_mode='HTML', disable_web_page_preview=True)
                # Начинаем новое сообщение
                current_text = header
                current_len = len(header)
            
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
        quantity = int(message.text.strip())
        if quantity < 1 or quantity > 100:
            await message.answer(
                "❌ Количество должно быть от 1 до 100.\n"
                "Введите количество еще раз:"
            )
            return
        
        # Получаем product_id из FSM
        data = await state.get_data()
        product_id = data.get('product_id')
        
        if not product_id:
            await message.answer("❌ Ошибка: товар не найден. Попробуйте выбрать товар снова.")
            await state.clear()
            return
        
        # Получаем информацию о товаре
        product = get_product_by_id(product_id)
        if not product:
            await message.answer("❌ Товар не найден")
            await state.clear()
            return
        
        # Добавляем товар в корзину с указанным количеством
        add_to_cart(user_id, product_id, quantity=quantity)
        
        country_with_flag = get_country_with_flag(product['country'])
        final_price = calculate_price_with_markup(product['price'], user_id)
        
        # Очищаем состояние
        await state.clear()
        
        await message.answer(
            f"✅ <b>Товар добавлен в корзину!</b>\n\n"
            f"{product['name']}, {country_with_flag}\n"
            f"Количество: <b>{quantity} шт.</b>\n"
            f"Цена за шт.: <b>{final_price}₽</b>\n"
            f"Итого: <b>{final_price * quantity}₽</b>\n\n"
            f"Перейдите в 'Корзина' для оформления заказа.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите число от 1 до 100.\n"
            "Введите количество еще раз:"
        )


# Обработчик просмотра корзины
@router.message(lambda m: m.text == "Корзина")
async def show_cart(message: types.Message, state: FSMContext):
    """Показывает корзину пользователя"""
    # Очищаем FSM состояние, если было
    await state.clear()
    user_id = message.from_user.id
    cart_items = get_cart(user_id)
    
    if not cart_items:
        await message.answer(
            "🛒 <b>Ваша корзина пуста</b>\n\n"
            "Добавьте товары из прайса, нажав на строку товара.",
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
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
        
        # Создаем строку с кнопками: [-] [количество] [+] [Удалить]
        keyboard_buttons.append([
            InlineKeyboardButton(text="➖", callback_data=decrease_callback),
            InlineKeyboardButton(text=f"{item['quantity']}", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=increase_callback),
            InlineKeyboardButton(text="❌", callback_data=remove_callback)
        ])
    
    text += f"<b>Итого: {total_price}₽</b>"
    
    # Добавляем кнопку оформления заказа
    checkout_callback = CartCallback(action="checkout").pack()
    print(f"DEBUG: Создана кнопка checkout с callback_data: {checkout_callback}")
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
        print(f"DEBUG: Товаров в корзине: {len(cart_items) if cart_items else 0}")
        if not cart_items:
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
                reply_markup=get_main_keyboard()
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
