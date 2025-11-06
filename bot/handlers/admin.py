import os
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from config import ADMIN_IDS, PRICE_UPLOAD_DIR
from admin.markup import get_admin_keyboard
from admin.price_loader import load_price_from_excel_auto
from admin.discount import (
    get_markup_percent, set_markup_percent,
    get_user_markup_percent, set_user_markup_percent,
    delete_user_markup, get_all_user_markups
)
from bot.keyboards.category import get_main_keyboard
from db.models import get_db
from db.crud import get_all_orders, get_order

router = Router()

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
    
    await message.answer(
        "📤 <b>Загрузка прайса</b>\n\n"
        "Отправьте Excel файл с прайсом.\n"
        "Файл будет обработан и товары загружены в базу данных.",
        parse_mode='HTML'
    )

@router.message(lambda m: m.document and m.document.file_name and m.document.file_name.endswith(('.xlsx', '.xls')))
async def handle_price_file(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        # Создаем директорию, если её нет
        os.makedirs(PRICE_UPLOAD_DIR, exist_ok=True)
        
        # Скачиваем файл
        file_info = await message.bot.get_file(message.document.file_id)
        file_path = os.path.join(PRICE_UPLOAD_DIR, message.document.file_name)
        
        await message.bot.download_file(file_info.file_path, file_path)
        
        # Загружаем прайс
        await message.answer("⏳ Обработка файла...")
        products_count = load_price_from_excel_auto(file_path)
        
        await message.answer(
            f"✅ <b>Прайс успешно загружен!</b>\n\n"
            f"Загружено товаров: <b>{products_count}</b>\n"
            f"Наценка применена: <b>{get_markup_percent()}%</b>",
            parse_mode='HTML',
            reply_markup=get_admin_keyboard()
        )
        
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

@router.message(lambda m: m.text == "⚙️ Настройка наценки")
async def set_markup_prompt(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    current_markup = get_markup_percent()
    await message.answer(
        f"⚙️ <b>Настройка наценки</b>\n\n"
        f"Текущая наценка: <b>{current_markup}%</b>\n\n"
        f"Отправьте новый процент наценки числом.\n"
        f"Например: <code>15</code> для 15%",
        parse_mode='HTML'
    )

@router.message(lambda m: m.text and m.text.isdigit() and is_admin(m.from_user.id))
async def set_markup_value(message: types.Message):
    """Обработчик установки наценки"""
    try:
        percent = float(message.text)
        if percent < 0 or percent > 1000:
            await message.answer("❌ Процент должен быть от 0 до 1000.")
            return
        
        set_markup_percent(percent)
        await message.answer(
            f"✅ Наценка установлена: <b>{percent}%</b>\n\n"
            f"Новая наценка будет применяться к новым загрузкам прайса.",
            parse_mode='HTML',
            reply_markup=get_admin_keyboard()
        )
    except ValueError:
        await message.answer("❌ Введите корректное число.")

@router.message(lambda m: m.text == "📈 Текущая наценка")
async def show_current_markup(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    markup = get_markup_percent()
    
    # Получаем статистику товаров
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products")
        products_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(DISTINCT category) FROM products")
        categories_count = cur.fetchone()[0]
    
    await message.answer(
        f"📈 <b>Статистика</b>\n\n"
        f"Текущая наценка: <b>{markup}%</b>\n"
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
    
    markup = get_markup_percent()
    
    stats_text = (
        f"📋 <b>Статистика базы данных</b>\n\n"
        f"Всего товаров: <b>{total_products}</b>\n"
        f"Категорий: <b>{total_categories}</b>\n"
        f"Текущая наценка: <b>{markup}%</b>\n\n"
        f"<b>Топ-5 категорий:</b>\n"
    )
    
    for i, (category, count) in enumerate(top_categories, 1):
        stats_text += f"{i}. {category}: <b>{count}</b> товаров\n"
    
    await message.answer(stats_text, parse_mode='HTML', reply_markup=get_admin_keyboard())

@router.message(lambda m: m.text == "🔙 Назад")
async def admin_back(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        'Главное меню:',
        reply_markup=get_main_keyboard()
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
        "👤 <b>Персональные проценты</b>\n\n"
        "Выберите действие:\n\n"
        "• <code>+user [ID] [процент]</code> - добавить/изменить процент пользователю\n"
        "• <code>-user [ID]</code> - удалить процент пользователя\n"
        "• <code>list</code> - список всех персональных процентов\n"
        "• <code>check [ID]</code> - проверить процент пользователя\n\n"
        "Примеры:\n"
        "<code>+user 123456789 5</code> - установить 5% пользователю с ID 123456789\n"
        "<code>-user 123456789</code> - удалить процент у пользователя\n"
        "<code>check 123456789</code> - проверить процент пользователя",
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
                "❌ Неверный формат. Используйте: <code>+user [ID] [процент]</code>\n"
                "Пример: <code>+user 123456789 5</code>",
                parse_mode='HTML'
            )
            return
        
        user_id = int(parts[1])
        percent = float(parts[2])
        
        if percent < -100 or percent > 1000:
            await message.answer("❌ Процент должен быть от -100 до 1000.")
            return
        
        set_user_markup_percent(user_id, percent)
        
        await message.answer(
            f"✅ Персональный процент установлен:\n\n"
            f"👤 ID пользователя: <code>{user_id}</code>\n"
            f"📊 Процент: <b>{percent}%</b>\n\n"
            f"Процент будет применяться к ценам товаров для этого пользователя.",
            parse_mode='HTML',
            reply_markup=get_admin_keyboard()
        )
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Используйте: <code>+user [ID] [процент]</code>\n"
            "Пример: <code>+user 123456789 5</code>",
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
                f"✅ Персональный процент удален для пользователя <code>{user_id}</code>",
                parse_mode='HTML',
                reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer(
                f"❌ Персональный процент не найден для пользователя <code>{user_id}</code>",
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
            "📋 <b>Персональные проценты</b>\n\n"
            "Персональных процентов нет.",
            parse_mode='HTML',
            reply_markup=get_admin_keyboard()
        )
        return
    
    text = "📋 <b>Персональные проценты</b>\n\n"
    
    for markup in markups:
        text += f"👤 ID: <code>{markup['user_id']}</code>\n"
        text += f"📊 Процент: <b>{markup['markup_percent']}%</b>\n"
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
        markup = get_user_markup_percent(user_id)
        
        if markup is not None:
            await message.answer(
                f"👤 <b>Пользователь:</b> <code>{user_id}</code>\n"
                f"📊 <b>Персональный процент:</b> <b>{markup}%</b>",
                parse_mode='HTML',
                reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer(
                f"👤 <b>Пользователь:</b> <code>{user_id}</code>\n"
                f"📊 <b>Персональный процент:</b> не установлен\n\n"
                f"Используется стандартная наценка: <b>{get_markup_percent()}%</b>",
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
