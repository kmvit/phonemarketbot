import os
from aiogram import Router, types
from aiogram.filters import Command, StateFilter
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from config import ADMIN_IDS, PRICE_UPLOAD_DIR
from bot.handlers.user import AddToCartStates
from admin.markup import get_admin_keyboard
from admin.price_loader import load_price_from_excel_auto, load_preorder_price_from_excel_auto
from admin.discount import (
    get_markup_amount, set_markup_amount,
    get_preorder_markup_amount, set_preorder_markup_amount,
    get_user_markup_amount, set_user_markup_amount,
    delete_user_markup, get_all_user_markups
)
from bot.keyboards.category import get_main_keyboard
from db.models import get_db
from db.crud import get_all_orders, get_order

router = Router()

# Хранилище состояний загрузки прайса для админов
# Формат: {user_id: 'standard' | 'preorder'}
price_upload_states = {}

# Хранилище состояний для установки наценки
# Формат: {user_id: 'standard' | 'preorder' | False}
markup_setting_states = {}

def is_admin(user_id):
    """Проверка, является ли пользователь админом"""
    return user_id in ADMIN_IDS

@router.message(lambda m: m.text == "Админка")
async def admin_menu(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админке.")
        return
    
    await message.answer(
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode='HTML'
    )

@router.message(lambda m: m.text == "📊 Загрузить прайс")
async def upload_price_prompt(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    price_upload_states[user_id] = 'standard'
    
    await message.answer(
        "📤 <b>Загрузка прайса</b>\n\n"
        "Отправьте Excel файл с прайсом.\n"
        "Файл будет обработан и товары загружены в базу данных.",
        parse_mode='HTML'
    )

@router.message(lambda m: m.text == "📦 Прайс предзаказа")
async def upload_preorder_price_prompt(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    price_upload_states[user_id] = 'preorder'
    
    await message.answer(
        "📤 <b>Загрузка прайса предзаказа</b>\n\n"
        "Отправьте Excel файл с прайсом предзаказа.\n"
        "Файл будет обработан и товары загружены в базу данных.",
        parse_mode='HTML'
    )

@router.message(lambda m: m.document and m.document.file_name and m.document.file_name.endswith(('.xlsx', '.xls')))
async def handle_price_file(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    # Определяем тип прайса из состояния (по умолчанию 'standard')
    price_type = price_upload_states.get(user_id, 'standard')
    
    try:
        # Создаем директорию, если её нет
        os.makedirs(PRICE_UPLOAD_DIR, exist_ok=True)
        
        # Скачиваем файл
        file_info = await message.bot.get_file(message.document.file_id)
        file_path = os.path.join(PRICE_UPLOAD_DIR, message.document.file_name)
        
        await message.bot.download_file(file_info.file_path, file_path)
        
        # Загружаем прайс
        await message.answer("⏳ Обработка файла...")
        
        if price_type == 'preorder':
            # Загружаем прайс предзаказа в отдельную таблицу
            products_count = load_preorder_price_from_excel_auto(file_path)
            price_type_text = "предзаказа"
        else:
            # Загружаем обычный прайс
            from admin.price_loader import detect_file_format
            file_format = detect_file_format(file_path)
            if file_format == 'simple':
                final_source = 'simple'
            else:
                final_source = 'standard'
            products_count = load_price_from_excel_auto(file_path, source=final_source)
            price_type_text = "обычного"
        
        # Показываем текущую наценку (она будет применяться при отображении товаров)
        if price_type == 'preorder':
            current_markup = get_preorder_markup_amount()
        else:
            current_markup = get_markup_amount()
        
        await message.answer(
            f"✅ <b>Прайс {price_type_text} успешно загружен!</b>\n\n"
            f"Загружено товаров: <b>{products_count}</b>\n"
            f"Текущая наценка: <b>{current_markup}₽</b> (применяется при отображении товаров)",
            parse_mode='HTML',
            reply_markup=get_admin_keyboard()
        )
        
        # Очищаем состояние загрузки
        if user_id in price_upload_states:
            del price_upload_states[user_id]
        
        # Удаляем временный файл
        try:
            os.remove(file_path)
        except:
            pass
            
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при загрузке прайса:</b>\n\n{str(e)}",
            parse_mode='HTML',
            reply_markup=get_admin_keyboard()
        )
        # Очищаем состояние загрузки при ошибке
        if user_id in price_upload_states:
            del price_upload_states[user_id]

@router.message(lambda m: m.text == "⚙️ Настройка наценки")
async def set_markup_prompt(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    markup_setting_states[user_id] = 'standard'  # Устанавливаем флаг для обычной наценки
    
    current_markup = get_markup_amount()
    await message.answer(
        f"⚙️ <b>Настройка наценки (основной прайс)</b>\n\n"
        f"Текущая наценка: <b>{current_markup}₽</b>\n\n"
        f"Отправьте новую сумму наценки числом.\n"
        f"Например: <code>100</code> для наценки 100₽",
        parse_mode='HTML'
    )

@router.message(lambda m: m.text == "⚙️ Наценка предзаказа")
async def set_preorder_markup_prompt(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    markup_setting_states[user_id] = 'preorder'  # Устанавливаем флаг для наценки предзаказа
    
    current_markup = get_preorder_markup_amount()
    await message.answer(
        f"⚙️ <b>Настройка наценки (предзаказ)</b>\n\n"
        f"Текущая наценка предзаказа: <b>{current_markup}₽</b>\n\n"
        f"Отправьте новую сумму наценки числом.\n"
        f"Например: <code>100</code> для наценки 100₽",
        parse_mode='HTML'
    )

# Функция-фильтр для проверки, что это установка наценки (не ввод количества товара)
def is_markup_setting(message: types.Message) -> bool:
    """Проверяет, что это установка наценки, а не ввод количества товара"""
    if not message.text or not message.text.replace('.', '').isdigit():
        return False
    
    if not is_admin(message.from_user.id):
        return False
    
    # Проверяем, что админ действительно хочет установить наценку (нажал на кнопку)
    user_id = message.from_user.id
    markup_state = markup_setting_states.get(user_id, False)
    if not markup_state:
        return False
    
    return True

@router.message(
    is_markup_setting,
    ~StateFilter(AddToCartStates.waiting_for_quantity)  # Не обрабатываем, если пользователь в состоянии ожидания количества
)
async def set_markup_value(message: types.Message, state: FSMContext):
    """Обработчик установки наценки"""
    user_id = message.from_user.id
    markup_type = markup_setting_states.get(user_id, False)
    
    try:
        amount = float(message.text)
        if amount < 0:
            await message.answer("❌ Сумма наценки должна быть неотрицательной.")
            # Не очищаем состояние, чтобы админ мог попробовать еще раз
            return
        
        if markup_type == 'preorder':
            set_preorder_markup_amount(amount)
            markup_text = "предзаказа"
        else:
            set_markup_amount(amount)
            markup_text = "основного прайса"
        
        # Очищаем состояние после успешной установки
        if user_id in markup_setting_states:
            del markup_setting_states[user_id]
        
        await message.answer(
            f"✅ Наценка {markup_text} установлена: <b>{amount}₽</b>\n\n"
            f"Новая наценка будет применяться к новым загрузкам прайса.",
            parse_mode='HTML',
            reply_markup=get_admin_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите корректное число.")
        # Не очищаем состояние, чтобы админ мог попробовать еще раз

@router.message(lambda m: m.text == "📈 Текущая наценка")
async def show_current_markup(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    markup = get_markup_amount()
    preorder_markup = get_preorder_markup_amount()
    
    # Получаем статистику товаров
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products")
        products_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(DISTINCT category) FROM products")
        categories_count = cur.fetchone()[0]
    
    await message.answer(
        f"📈 <b>Статистика</b>\n\n"
        f"Наценка основного прайса: <b>{markup}₽</b>\n"
        f"Наценка предзаказа: <b>{preorder_markup}₽</b>\n"
        f"Товаров в базе: <b>{products_count}</b>\n"
        f"Категорий: <b>{categories_count}</b>",
        parse_mode='HTML',
        reply_markup=get_admin_keyboard()
    )

@router.message(lambda m: m.text == "📋 Статистика")
async def show_statistics(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    with get_db() as conn:
        cur = conn.cursor()
        
        # Общая статистика
        cur.execute("SELECT COUNT(*) FROM products")
        total_products = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(DISTINCT category) FROM products")
        total_categories = cur.fetchone()[0]
        
        # Топ категорий
        cur.execute("""
            SELECT category, COUNT(*) as count 
            FROM products 
            GROUP BY category 
            ORDER BY count DESC 
            LIMIT 5
        """)
        top_categories = cur.fetchall()
    
    markup = get_markup_amount()
    preorder_markup = get_preorder_markup_amount()
    
    stats_text = (
        f"📋 <b>Статистика базы данных</b>\n\n"
        f"Всего товаров: <b>{total_products}</b>\n"
        f"Категорий: <b>{total_categories}</b>\n"
        f"Наценка основного прайса: <b>{markup}₽</b>\n"
        f"Наценка предзаказа: <b>{preorder_markup}₽</b>\n\n"
        f"<b>Топ-5 категорий:</b>\n"
    )
    
    for i, (category, count) in enumerate(top_categories, 1):
        stats_text += f"{i}. {category}: <b>{count}</b> товаров\n"
    
    await message.answer(stats_text, parse_mode='HTML', reply_markup=get_admin_keyboard())

@router.message(lambda m: m.text == "🔙 Назад")
async def admin_back(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    # Очищаем состояние установки наценки при выходе из админки
    user_id = message.from_user.id
    if user_id in markup_setting_states:
        del markup_setting_states[user_id]
    
    await message.answer(
        'Главное меню:',
        reply_markup=get_main_keyboard(message.from_user.id)
    )

@router.message(lambda m: m.text == "📦 Заказы")
async def show_orders(message: types.Message):
    """Показывает все заказы админу"""
    if not is_admin(message.from_user.id):
        return
    
    orders = get_all_orders()
    
    if not orders:
        await message.answer(
            "📦 <b>Заказы</b>\n\n"
            "Заказов пока нет.",
            parse_mode='HTML',
            reply_markup=get_admin_keyboard()
        )
        return
    
    # Отправляем список заказов
    orders_text = f"📦 <b>Все заказы</b> (всего: {len(orders)})\n\n"
    
    for order in orders[:10]:  # Показываем последние 10 заказов
        status_emoji = "🆕" if order['status'] == 'new' else "✅" if order['status'] == 'completed' else "⏳"
        orders_text += f"{status_emoji} <b>Заказ #{order['id']}</b>\n"
        orders_text += f"Пользователь: {order['user_first_name'] or 'Не указано'}\n"
        if order['user_username']:
            orders_text += f"@{order['user_username']}\n"
        orders_text += f"ID: <code>{order['user_id']}</code>\n"
        orders_text += f"Сумма: <b>{order['total_price']}₽</b>\n"
        orders_text += f"Статус: {order['status']}\n"
        orders_text += f"Дата: {order['created_at']}\n\n"
    
    if len(orders) > 10:
        orders_text += f"\n<i>Показаны последние 10 из {len(orders)} заказов</i>"
    
    await message.answer(
        orders_text,
        parse_mode='HTML',
        reply_markup=get_admin_keyboard()
    )
    
    # Отправляем детали каждого заказа отдельным сообщением
    for order in orders[:10]:
        order_details = get_order(order['id'])
        if order_details:
            detail_text = f"📦 <b>Заказ #{order_details['id']}</b>\n\n"
            detail_text += f"👤 <b>Пользователь:</b>\n"
            if order_details['user_username']:
                detail_text += f"@{order_details['user_username']}\n"
            detail_text += f"Имя: {order_details['user_first_name'] or 'Не указано'}\n"
            detail_text += f"Фамилия: {order_details['user_last_name'] or 'Не указано'}\n"
            detail_text += f"ID: <code>{order_details['user_id']}</code>\n"
            detail_text += f"Ссылка: <a href='tg://user?id={order_details['user_id']}'>Написать пользователю</a>\n\n"
            detail_text += f"<b>Позиции:</b>\n"
            
            for item in order_details['items']:
                detail_text += f"• {item['product_name']}\n"
                detail_text += f"  Количество: {item['quantity']} шт. × {item['price']}₽ = {item['quantity'] * item['price']}₽\n"
            
            detail_text += f"\n<b>Итого: {order_details['total_price']}₽</b>\n"
            detail_text += f"Статус: {order_details['status']}\n"
            detail_text += f"Дата: {order_details['created_at']}"
            
            await message.answer(
                detail_text,
                parse_mode='HTML'
            )

# Обработчики для персональных процентов
@router.message(lambda m: m.text == "👤 Персональные проценты")
async def user_markups_menu(message: types.Message):
    """Меню управления персональными процентами"""
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        "👤 <b>Персональные наценки</b>\n\n"
        "Выберите действие:\n\n"
        "• <code>+user [ID] [сумма]</code> - добавить/изменить сумму наценки пользователю\n"
        "• <code>-user [ID]</code> - удалить наценку пользователя\n"
        "• <code>list</code> - список всех персональных наценок\n"
        "• <code>check [ID]</code> - проверить наценку пользователя\n\n"
        "Примеры:\n"
        "<code>+user 123456789 100</code> - установить наценку 100₽ пользователю с ID 123456789\n"
        "<code>-user 123456789</code> - удалить наценку у пользователя\n"
        "<code>check 123456789</code> - проверить наценку пользователя",
        parse_mode='HTML',
        reply_markup=get_admin_keyboard()
    )

@router.message(lambda m: m.text and m.text.startswith("+user") and is_admin(m.from_user.id))
async def add_user_markup(message: types.Message):
    """Добавить/изменить персональный процент пользователю"""
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer(
                "❌ Неверный формат. Используйте: <code>+user [ID] [сумма]</code>\n"
                "Пример: <code>+user 123456789 100</code>",
                parse_mode='HTML'
            )
            return
        
        user_id = int(parts[1])
        amount = float(parts[2])
        
        if amount < 0:
            await message.answer("❌ Сумма наценки должна быть неотрицательной.")
            return
        
        set_user_markup_amount(user_id, amount)
        
        await message.answer(
            f"✅ Персональная наценка установлена:\n\n"
            f"👤 ID пользователя: <code>{user_id}</code>\n"
            f"📊 Сумма: <b>{amount}₽</b>\n\n"
            f"Наценка будет применяться к ценам товаров для этого пользователя.",
            parse_mode='HTML',
            reply_markup=get_admin_keyboard()
        )
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Используйте: <code>+user [ID] [сумма]</code>\n"
            "Пример: <code>+user 123456789 100</code>",
            parse_mode='HTML'
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}", parse_mode='HTML')

@router.message(lambda m: m.text and m.text.startswith("-user") and is_admin(m.from_user.id))
async def remove_user_markup(message: types.Message):
    """Удалить персональный процент пользователя"""
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer(
                "❌ Неверный формат. Используйте: <code>-user [ID]</code>\n"
                "Пример: <code>-user 123456789</code>",
                parse_mode='HTML'
            )
            return
        
        user_id = int(parts[1])
        
        deleted = delete_user_markup(user_id)
        
        if deleted:
            await message.answer(
                f"✅ Персональная наценка удалена для пользователя <code>{user_id}</code>",
                parse_mode='HTML',
                reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer(
                f"❌ Персональная наценка не найдена для пользователя <code>{user_id}</code>",
                parse_mode='HTML',
                reply_markup=get_admin_keyboard()
            )
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Используйте: <code>-user [ID]</code>\n"
            "Пример: <code>-user 123456789</code>",
            parse_mode='HTML'
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}", parse_mode='HTML')

@router.message(lambda m: m.text and m.text.lower() == "list" and is_admin(m.from_user.id))
async def list_user_markups(message: types.Message):
    """Показать список всех персональных процентов"""
    markups = get_all_user_markups()
    
    if not markups:
        await message.answer(
            "📋 <b>Персональные наценки</b>\n\n"
            "Персональных наценок нет.",
            parse_mode='HTML',
            reply_markup=get_admin_keyboard()
        )
        return
    
    text = "📋 <b>Персональные наценки</b>\n\n"
    
    for markup in markups:
        text += f"👤 ID: <code>{markup['user_id']}</code>\n"
        text += f"📊 Сумма: <b>{markup['markup_amount']}₽</b>\n"
        text += f"📅 Обновлено: {markup['updated_at']}\n\n"
    
    if len(markups) > 10:
        text += f"\n<i>Показано {len(markups)} пользователей</i>"
    
    await message.answer(
        text,
        parse_mode='HTML',
        reply_markup=get_admin_keyboard()
    )

@router.message(lambda m: m.text and m.text.startswith("check") and is_admin(m.from_user.id))
async def check_user_markup(message: types.Message):
    """Проверить персональный процент пользователя"""
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer(
                "❌ Неверный формат. Используйте: <code>check [ID]</code>\n"
                "Пример: <code>check 123456789</code>",
                parse_mode='HTML'
            )
            return
        
        user_id = int(parts[1])
        markup = get_user_markup_amount(user_id)
        
        if markup is not None:
            await message.answer(
                f"👤 <b>Пользователь:</b> <code>{user_id}</code>\n"
                f"📊 <b>Персональная наценка:</b> <b>{markup}₽</b>",
                parse_mode='HTML',
                reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer(
                f"👤 <b>Пользователь:</b> <code>{user_id}</code>\n"
                f"📊 <b>Персональная наценка:</b> не установлена\n\n"
                f"Используется стандартная наценка: <b>{get_markup_amount()}₽</b>",
                parse_mode='HTML',
                reply_markup=get_admin_keyboard()
            )
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Используйте: <code>check [ID]</code>\n"
            "Пример: <code>check 123456789</code>",
            parse_mode='HTML'
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}", parse_mode='HTML')
