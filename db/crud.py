from db.models import get_db
from admin.discount import calculate_price_with_markup

def get_country_with_flag(country):
    """Возвращает страну с флагом (всегда возвращает как есть, так как в БД уже сохранен флаг)"""
    if not country:
        return "🌍 Не указано"
    
    country_str = str(country).strip()
    # Возвращаем как есть, так как при загрузке прайса уже добавляется флаг через маппинг
    return country_str

def get_products_by_category(category, source='standard'):
    """Получает товары по категории с фильтрацией по source"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, memory, color, country, price
            FROM products
            WHERE category=? AND source=?
            ORDER BY price
        """, (category, source))
        rows = cur.fetchall()
        return [
            {
                "id": row[0],
                "name": row[1],
                "memory": row[2],
                "color": row[3],
                "country": row[4],
                "price": row[5],
            } for row in rows
        ]

def get_available_parent_categories(possible_parent_cats, source='standard'):
    """Получает список родительских категорий, в которых есть товары с указанным source"""
    if not possible_parent_cats:
        return []
    
    # Получаем динамический маппинг категорий из БД
    dynamic_mapping = get_dynamic_parent_to_subcategories(source)
    
    # Возвращаем только те родительские категории, которые есть в возможных и имеют товары в БД
    available_parents = []
    for parent_cat in possible_parent_cats:
        if parent_cat in dynamic_mapping and dynamic_mapping[parent_cat]:
            available_parents.append(parent_cat)
    
    return available_parents

def get_available_subcategories(parent_category, possible_subcats=None, source='standard'):
    """Получает список подкатегорий, которые есть в БД для родительской категории с фильтрацией по source"""
    # Если не передан список возможных подкатегорий, получаем их динамически
    if possible_subcats is None:
        dynamic_mapping = get_dynamic_parent_to_subcategories(source)
        possible_subcats = dynamic_mapping.get(parent_category, [])
    
    if not possible_subcats:
        return []
    
    with get_db() as conn:
        cur = conn.cursor()
        # Получаем уникальные категории из БД, которые есть в списке возможных подкатегорий
        placeholders = ','.join(['?'] * len(possible_subcats))
        cur.execute(f"""
            SELECT DISTINCT category
            FROM products
            WHERE category IN ({placeholders}) AND source=?
        """, possible_subcats + [source])
        rows = cur.fetchall()
        return [row[0] for row in rows]

def get_dynamic_subcategories_for_parent(parent_category, source='standard'):
    """Получает подкатегории для родительской категории из динамического маппинга"""
    dynamic_mapping = get_dynamic_parent_to_subcategories(source)
    return dynamic_mapping.get(parent_category, [])

def get_all_categories_from_db(source='standard'):
    """Получает все уникальные категории из базы данных для указанного source"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT category
            FROM products
            WHERE source=?
            ORDER BY category
        """, (source,))
        rows = cur.fetchall()
        return [row[0] for row in rows]

def get_dynamic_parent_to_subcategories(source='standard'):
    """
    Создает динамический маппинг родительских категорий к подкатегориям
    на основе данных из базы данных
    """
    categories = get_all_categories_from_db(source)
    
    # Группируем категории по брендам
    parent_mapping = {}
    
    for category in categories:
        # Определяем родительскую категорию по названию
        if 'iPhone' in category or 'iPad' in category or 'MacBook' in category or 'Apple' in category or 'AirPods' in category:
            parent = 'Apple'
        elif 'Samsung' in category:
            parent = 'Samsung'
        elif 'Google' in category or 'Pixel' in category:
            parent = 'Google Pixel'
        elif 'Xiaomi' in category:
            parent = 'Xiaomi'
        elif 'Redmi' in category:
            parent = 'Redmi'
        elif 'POCO' in category:
            parent = 'POCO'
        elif 'Honor' in category:
            parent = 'Honor'
        elif 'Huawei' in category:
            parent = 'Huawei'
        elif 'Vivo' in category:
            parent = 'Vivo'
        elif 'Realme' in category:
            parent = 'Realme'
        elif 'Yandex' in category:
            parent = 'Yandex'
        elif 'Meta' in category:
            parent = 'Meta Quest'
        elif 'Nintendo' in category:
            parent = 'Nintendo'
        elif 'Valve' in category:
            parent = 'Valve'
        elif 'Sony' in category:
            parent = 'Sony'
        elif 'GoPro' in category:
            parent = 'GoPro'
        elif 'Insta360' in category:
            parent = 'Insta360'
        elif 'Garmin' in category:
            parent = 'Garmin'
        else:
            parent = 'Аксессуары'
        
        if parent not in parent_mapping:
            parent_mapping[parent] = []
        
        if category not in parent_mapping[parent]:
            parent_mapping[parent].append(category)
    
    return parent_mapping

def get_product_by_id(product_id):
    """Получает товар по ID"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, memory, color, country, price, category
            FROM products
            WHERE id=?
        """, (product_id,))
        row = cur.fetchone()
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "memory": row[2],
                "color": row[3],
                "country": row[4],
                "price": row[5],
                "category": row[6],
            }
        return None

def add_to_cart(user_id, product_id, quantity=1):
    """Добавляет товар в корзину пользователя"""
    with get_db() as conn:
        cur = conn.cursor()
        # Проверяем, есть ли уже этот товар в корзине
        cur.execute("""
            SELECT id, quantity FROM cart
            WHERE user_id=? AND product_id=?
        """, (user_id, product_id))
        existing = cur.fetchone()
        
        if existing:
            # Увеличиваем количество
            new_quantity = existing[1] + quantity
            cur.execute("""
                UPDATE cart SET quantity=?
                WHERE id=?
            """, (new_quantity, existing[0]))
        else:
            # Добавляем новый товар
            cur.execute("""
                INSERT INTO cart (user_id, product_id, quantity)
                VALUES (?, ?, ?)
            """, (user_id, product_id, quantity))
        conn.commit()
        return True

def get_cart(user_id):
    """Получает корзину пользователя с информацией о товарах"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.product_id, c.quantity, p.name, p.memory, p.color, p.country, p.price
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id=?
            ORDER BY c.created_at
        """, (user_id,))
        rows = cur.fetchall()
        return [
            {
                "cart_id": row[0],
                "product_id": row[1],
                "quantity": row[2],
                "name": row[3],
                "memory": row[4],
                "color": row[5],
                "country": row[6],
                "price": row[7],
            } for row in rows
        ]

def update_cart_quantity(user_id, cart_id, quantity):
    """Обновляет количество товара в корзине"""
    if quantity <= 0:
        return remove_from_cart(user_id, cart_id)
    
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE cart SET quantity=?
            WHERE id=? AND user_id=?
        """, (quantity, cart_id, user_id))
        conn.commit()
        return cur.rowcount > 0

def remove_from_cart(user_id, cart_id):
    """Удаляет товар из корзины"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM cart
            WHERE id=? AND user_id=?
        """, (cart_id, user_id))
        conn.commit()
        return cur.rowcount > 0

def clear_cart(user_id):
    """Очищает корзину пользователя"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM cart
            WHERE user_id=?
        """, (user_id,))
        conn.commit()
        return True

def create_order(user_id, user_username, user_first_name, user_last_name):
    """Создает заказ из корзины пользователя (обычной и предзаказа)"""
    with get_db() as conn:
        cur = conn.cursor()
        all_items = []
        
        # Получаем товары из обычной корзины
        cur.execute("""
            SELECT c.id, c.product_id, c.quantity, p.name, p.memory, p.color, p.country, p.price
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id=?
            ORDER BY c.created_at
        """, (user_id,))
        rows = cur.fetchall()
        
        for row in rows:
            all_items.append({
                "cart_id": row[0],
                "product_id": row[1],
                "quantity": row[2],
                "name": row[3],
                "memory": row[4],
                "color": row[5],
                "country": row[6],
                "price": row[7],
                "is_preorder": False
            })
        
        # Получаем товары из корзины предзаказа
        cur.execute("""
            SELECT c.id, c.product_id, c.quantity, p.name, p.memory, p.color, p.country, p.price
            FROM preorder_cart c
            JOIN preorder_products p ON c.product_id = p.id
            WHERE c.user_id=?
            ORDER BY c.created_at
        """, (user_id,))
        rows = cur.fetchall()
        
        for row in rows:
            all_items.append({
                "cart_id": row[0],
                "product_id": row[1],
                "quantity": row[2],
                "name": row[3],
                "memory": row[4],
                "color": row[5],
                "country": row[6],
                "price": row[7],
                "is_preorder": True
            })
        
        if not all_items:
            return None
        
        # Вычисляем общую стоимость с учетом персонального процента пользователя
        total_price = 0
        for item in all_items:
            final_price = calculate_price_with_markup(item['price'], user_id, is_preorder=item['is_preorder'])
            total_price += final_price * item['quantity']
        
        # Создаем заказ
        cur.execute("""
            INSERT INTO orders (user_id, user_username, user_first_name, user_last_name, total_price)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, user_username, user_first_name, user_last_name, total_price))
        order_id = cur.lastrowid
        
        # Добавляем позиции заказа с учетом персонального процента
        for item in all_items:
            final_price = calculate_price_with_markup(item['price'], user_id, is_preorder=item['is_preorder'])
            # Формируем название товара с флагом страны (как в корзине)
            country_with_flag = get_country_with_flag(item['country'])
            product_name = f"{item['name']}, {country_with_flag}"
            # Добавляем пометку о предзаказе в начало названия товара
            if item['is_preorder']:
                product_name = f"[ПРЕДЗАКАЗ] {product_name}"
            cur.execute("""
                INSERT INTO order_items (order_id, product_id, product_name, quantity, price)
                VALUES (?, ?, ?, ?, ?)
            """, (order_id, item['product_id'], product_name, item['quantity'], final_price))
        
        # Очищаем обе корзины в том же соединении
        cur.execute("""
            DELETE FROM cart
            WHERE user_id=?
        """, (user_id,))
        cur.execute("""
            DELETE FROM preorder_cart
            WHERE user_id=?
        """, (user_id,))
        
        conn.commit()
        return order_id

def get_order(order_id):
    """Получает заказ с позициями"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, user_id, user_username, user_first_name, user_last_name, status, created_at, total_price
            FROM orders
            WHERE id=?
        """, (order_id,))
        order_row = cur.fetchone()
        
        if not order_row:
            return None
        
        order = {
            "id": order_row[0],
            "user_id": order_row[1],
            "user_username": order_row[2],
            "user_first_name": order_row[3],
            "user_last_name": order_row[4],
            "status": order_row[5],
            "created_at": order_row[6],
            "total_price": order_row[7],
            "items": []
        }
        
        cur.execute("""
            SELECT product_id, product_name, quantity, price
            FROM order_items
            WHERE order_id=?
        """, (order_id,))
        items = cur.fetchall()
        
        for item in items:
            order["items"].append({
                "product_id": item[0],
                "product_name": item[1],
                "quantity": item[2],
                "price": item[3],
            })
        
        return order

def get_all_orders():
    """Получает все заказы (для админа)"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, user_id, user_username, user_first_name, user_last_name, status, created_at, total_price
            FROM orders
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        return [
            {
                "id": row[0],
                "user_id": row[1],
                "user_username": row[2],
                "user_first_name": row[3],
                "user_last_name": row[4],
                "status": row[5],
                "created_at": row[6],
                "total_price": row[7],
            } for row in rows
        ]

# ========== ФУНКЦИИ ДЛЯ ПРЕДЗАКАЗА ==========

def get_preorder_products_by_category(category):
    """Получает товары предзаказа по категории"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, memory, color, country, price
            FROM preorder_products
            WHERE category=?
            ORDER BY price
        """, (category,))
        rows = cur.fetchall()
        return [
            {
                "id": row[0],
                "name": row[1],
                "memory": row[2],
                "color": row[3],
                "country": row[4],
                "price": row[5],
            } for row in rows
        ]

def get_preorder_available_subcategories(parent_category, possible_subcats):
    """Получает список подкатегорий предзаказа, которые есть в БД для родительской категории"""
    if not possible_subcats:
        return []
    
    with get_db() as conn:
        cur = conn.cursor()
        # Получаем уникальные категории из БД предзаказа, которые есть в списке возможных подкатегорий
        placeholders = ','.join(['?'] * len(possible_subcats))
        cur.execute(f"""
            SELECT DISTINCT category
            FROM preorder_products
            WHERE category IN ({placeholders})
        """, possible_subcats)
        rows = cur.fetchall()
        return [row[0] for row in rows]

def get_preorder_categories():
    """Получает список всех уникальных категорий из предзаказа"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT category
            FROM preorder_products
            ORDER BY category
        """)
        rows = cur.fetchall()
        return [row[0] for row in rows]

def get_preorder_product_by_id(product_id):
    """Получает товар предзаказа по ID"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, memory, color, country, price, category
            FROM preorder_products
            WHERE id=?
        """, (product_id,))
        row = cur.fetchone()
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "memory": row[2],
                "color": row[3],
                "country": row[4],
                "price": row[5],
                "category": row[6],
            }
        return None

def add_to_preorder_cart(user_id, product_id, quantity=1):
    """Добавляет товар в корзину предзаказа пользователя"""
    with get_db() as conn:
        cur = conn.cursor()
        # Проверяем, есть ли уже этот товар в корзине предзаказа
        cur.execute("""
            SELECT id, quantity FROM preorder_cart
            WHERE user_id=? AND product_id=?
        """, (user_id, product_id))
        existing = cur.fetchone()
        
        if existing:
            # Увеличиваем количество
            new_quantity = existing[1] + quantity
            cur.execute("""
                UPDATE preorder_cart SET quantity=?
                WHERE id=?
            """, (new_quantity, existing[0]))
        else:
            # Добавляем новый товар
            cur.execute("""
                INSERT INTO preorder_cart (user_id, product_id, quantity)
                VALUES (?, ?, ?)
            """, (user_id, product_id, quantity))
        conn.commit()
        return True

def get_preorder_cart(user_id):
    """Получает корзину предзаказа пользователя с информацией о товарах"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.product_id, c.quantity, p.name, p.memory, p.color, p.country, p.price
            FROM preorder_cart c
            JOIN preorder_products p ON c.product_id = p.id
            WHERE c.user_id=?
            ORDER BY c.created_at
        """, (user_id,))
        rows = cur.fetchall()
        return [
            {
                "cart_id": row[0],
                "product_id": row[1],
                "quantity": row[2],
                "name": row[3],
                "memory": row[4],
                "color": row[5],
                "country": row[6],
                "price": row[7],
            } for row in rows
        ]

def update_preorder_cart_quantity(user_id, cart_id, quantity):
    """Обновляет количество товара в корзине предзаказа"""
    if quantity <= 0:
        return remove_from_preorder_cart(user_id, cart_id)
    
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE preorder_cart SET quantity=?
            WHERE id=? AND user_id=?
        """, (quantity, cart_id, user_id))
        conn.commit()
        return cur.rowcount > 0

def remove_from_preorder_cart(user_id, cart_id):
    """Удаляет товар из корзины предзаказа"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM preorder_cart
            WHERE id=? AND user_id=?
        """, (cart_id, user_id))
        conn.commit()
        return cur.rowcount > 0

def clear_preorder_cart(user_id):
    """Очищает корзину предзаказа пользователя"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM preorder_cart
            WHERE user_id=?
        """, (user_id,))
        conn.commit()
        return True

def clear_all_products():
    """Очищает все товары из базы данных (основной прайс и предзаказ)"""
    with get_db() as conn:
        cur = conn.cursor()
        
        # Получаем количество товаров до удаления для статистики
        cur.execute("SELECT COUNT(*) FROM products")
        products_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM preorder_products")
        preorder_products_count = cur.fetchone()[0]
        
        # Удаляем все товары
        cur.execute("DELETE FROM products")
        cur.execute("DELETE FROM preorder_products")
        
        # Также очищаем корзины, так как товары больше не существуют
        cur.execute("DELETE FROM cart")
        cur.execute("DELETE FROM preorder_cart")
        
        conn.commit()
        
        return {
            "products_deleted": products_count,
            "preorder_products_deleted": preorder_products_count
        }
