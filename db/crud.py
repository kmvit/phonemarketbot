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

def sort_categories_smart(categories):
    """
    Умная сортировка категорий с учетом номеров моделей и вариантов.
    Например: iPhone 15, iPhone 15 Pro, iPhone 16, iPhone 16 Pro, iPhone 17, iPhone 17 Air, iPhone 17 Pro
    """
    import re
    
    def get_sort_key(category):
        # Извлекаем бренд, номер модели и вариант
        # Примеры: "iPhone 15 Pro", "Samsung Galaxy S24 Ultra", "Xiaomi 14 Pro"
        
        # Для iPhone
        iphone_match = re.search(r'iPhone\s+(\d+)\s*(.*)', category)
        if iphone_match:
            model_num = int(iphone_match.group(1))
            variant = iphone_match.group(2).strip()
            
            # Определяем приоритет варианта (базовая модель идет первой)
            variant_priority = 0
            if not variant:  # Базовая модель (iPhone 15)
                variant_priority = 0
            elif 'Air' in variant:
                variant_priority = 1
            elif 'Pro Max' in variant:
                variant_priority = 3
            elif 'Pro' in variant:
                variant_priority = 2
            elif 'Ultra' in variant:
                variant_priority = 4
            else:
                variant_priority = 5
                
            return (0, model_num, variant_priority, variant)
        
        # Для Samsung Galaxy
        samsung_match = re.search(r'Samsung Galaxy S(\d+)\s*(.*)', category)
        if samsung_match:
            model_num = int(samsung_match.group(1))
            variant = samsung_match.group(2).strip()
            
            variant_priority = 0
            if not variant:
                variant_priority = 0
            elif 'Ultra' in variant:
                variant_priority = 2
            elif '+' in variant:
                variant_priority = 1
            else:
                variant_priority = 3
                
            return (1, model_num, variant_priority, variant)
        
        # Для Xiaomi
        xiaomi_match = re.search(r'Xiaomi\s+(\d+)\s*(.*)', category)
        if xiaomi_match:
            model_num = int(xiaomi_match.group(1))
            variant = xiaomi_match.group(2).strip()
            
            variant_priority = 0
            if not variant:
                variant_priority = 0
            elif 'Pro' in variant:
                variant_priority = 1
            elif 'Ultra' in variant:
                variant_priority = 2
            else:
                variant_priority = 3
                
            return (2, model_num, variant_priority, variant)
        
        # Для Google Pixel
        pixel_match = re.search(r'Google Pixel\s+(\d+)\s*(.*)', category)
        if pixel_match:
            model_num = int(pixel_match.group(1))
            variant = pixel_match.group(2).strip()
            
            variant_priority = 0
            if not variant:
                variant_priority = 0
            elif 'Pro XL' in variant:
                variant_priority = 2
            elif 'Pro' in variant:
                variant_priority = 1
            else:
                variant_priority = 3
                
            return (3, model_num, variant_priority, variant)
        
        # Для остальных категорий - сортируем по алфавиту
        return (999, 0, 0, category)
    
    return sorted(categories, key=get_sort_key)

def get_available_subcategories(parent_category, possible_subcats=None, source='standard'):
    """Получает список подкатегорий, которые есть в БД для родительской категории с фильтрацией по source"""
    # Получаем динамический маппинг категорий из БД
    dynamic_mapping = get_dynamic_parent_to_subcategories(source)
    
    # Получаем все подкатегории из БД для этой родительской категории
    db_subcats = dynamic_mapping.get(parent_category, [])
    
    if not db_subcats:
        return []
    
    # Если передан список возможных подкатегорий, объединяем его с категориями из БД
    # Это позволяет показывать как статические подкатегории, так и новые из БД
    if possible_subcats is not None:
        # Объединяем статический список и динамические категории из БД
        all_possible = list(set(possible_subcats + db_subcats))
    else:
        # Если список не передан, используем только категории из БД
        all_possible = db_subcats
    
    with get_db() as conn:
        cur = conn.cursor()
        # Получаем уникальные категории из БД, которые есть в списке подкатегорий
        placeholders = ','.join(['?'] * len(all_possible))
        cur.execute(f"""
            SELECT DISTINCT category
            FROM products
            WHERE category IN ({placeholders}) AND source=?
        """, all_possible + [source])
        rows = cur.fetchall()
        categories = [row[0] for row in rows]
        
        # Применяем умную сортировку
        return sort_categories_smart(categories)

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

def detect_parent_category_from_name(category_name):
    """
    Автоматически определяет родительскую категорию на основе названия категории.
    Поддерживает известные бренды и автоматически создает новые родительские категории для неизвестных.
    """
    if not category_name:
        return 'Аксессуары'
    
    category_upper = category_name.upper()
    
    # Маппинг известных брендов (проверяем от более специфичных к общим)
    brand_patterns = [
        # Apple (проверяем первым, так как может содержать другие слова)
        (['IPHONE', 'IPAD', 'MACBOOK', 'APPLE', 'AIRPODS', 'MAC MINI', 'IMAC', 'WATCH'], 'Apple'),
        # Samsung
        (['SAMSUNG'], 'Samsung'),
        # Google Pixel
        (['GOOGLE', 'PIXEL'], 'Google Pixel'),
        # Xiaomi
        (['XIAOMI'], 'Xiaomi'),
        # Redmi
        (['REDMI'], 'Redmi'),
        # POCO
        (['POCO'], 'POCO'),
        # Honor
        (['HONOR'], 'Honor'),
        # Huawei
        (['HUAWEI'], 'Huawei'),
        # Vivo
        (['VIVO'], 'Vivo'),
        # Realme
        (['REALME'], 'Realme'),
        # Yandex
        (['YANDEX'], 'Yandex'),
        # Meta Quest
        (['META', 'QUEST'], 'Meta Quest'),
        # Nintendo
        (['NINTENDO'], 'Nintendo'),
        # Valve
        (['VALVE'], 'Valve'),
        # Sony
        (['SONY'], 'Sony'),
        # GoPro
        (['GOPRO'], 'GoPro'),
        # Insta360
        (['INSTA360'], 'Insta360'),
        # Garmin
        (['GARMIN'], 'Garmin'),
        # Dyson
        (['DYSON'], 'Dyson'),
    ]
    
    # Проверяем известные бренды
    for patterns, parent in brand_patterns:
        if any(pattern in category_upper for pattern in patterns):
            return parent
    
    # Если категория не распознана, пытаемся определить родительскую категорию автоматически
    # Извлекаем первое слово из категории (обычно это бренд)
    words = category_name.split()
    if words:
        first_word = words[0].strip()
        # Если первое слово выглядит как бренд (заглавные буквы или смешанный регистр)
        if first_word and (first_word[0].isupper() or first_word.isupper()):
            # Используем первое слово как родительскую категорию
            return first_word
    
    # По умолчанию - Аксессуары
    return 'Аксессуары'

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
        elif 'Dyson' in category:
            parent = 'Dyson'
        else:
            parent = 'Аксессуары'
        
        if parent not in parent_mapping:
            parent_mapping[parent] = []
        
        if category not in parent_mapping[parent]:
            parent_mapping[parent].append(category)
    
    # Сортируем подкатегории в каждой родительской категории
    for parent in parent_mapping:
        parent_mapping[parent] = sort_categories_smart(parent_mapping[parent])
    
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
