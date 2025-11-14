import sqlite3
from config import DATABASE_PATH

CATEGORIES = [
    "iPhone 13", "iPhone 14", "iPhone 15", "iPhone 16", "iPhone 17",
    "Samsung", "Xiaomi", "Аксессуары"
]

def get_db():
    return sqlite3.connect(DATABASE_PATH)

def init_db():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                name TEXT,
                memory TEXT,
                color TEXT,
                country TEXT,
                price INTEGER,
                source TEXT DEFAULT 'standard'
            )
        ''')
        # Миграция: добавляем колонку source, если её нет
        try:
            cur.execute("ALTER TABLE products ADD COLUMN source TEXT DEFAULT 'standard'")
        except sqlite3.OperationalError:
            # Колонка уже существует, игнорируем ошибку
            pass
        
        # Обновляем существующие записи без source на 'standard'
        cur.execute("UPDATE products SET source = 'standard' WHERE source IS NULL")
        
        # Таблица для настроек (наценка)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        # Устанавливаем дефолтную наценку, если её нет
        from config import DEFAULT_MARKUP_AMOUNT, DEFAULT_PREORDER_MARKUP_AMOUNT
        cur.execute('''
            INSERT OR IGNORE INTO settings (key, value) 
            VALUES ('markup_amount', ?)
        ''', (str(DEFAULT_MARKUP_AMOUNT),))
        # Устанавливаем дефолтную наценку для предзаказа, если её нет
        cur.execute('''
            INSERT OR IGNORE INTO settings (key, value) 
            VALUES ('preorder_markup_amount', ?)
        ''', (str(DEFAULT_PREORDER_MARKUP_AMOUNT),))
        
        # Таблица корзины
        cur.execute('''
            CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица заказов
        cur.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_username TEXT,
                user_first_name TEXT,
                user_last_name TEXT,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_price INTEGER
            )
        ''')
        
        # Таблица позиций заказа
        cur.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price INTEGER NOT NULL
            )
        ''')
        
        # Таблица персональных наценок пользователей
        # Миграция: проверяем, существует ли старая таблица с markup_percent
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_markups'")
        table_exists = cur.fetchone()
        
        if table_exists:
            # Проверяем, есть ли старая колонка markup_percent
            cur.execute("PRAGMA table_info(user_markups)")
            columns = [col[1] for col in cur.fetchall()]
            
            if 'markup_percent' in columns and 'markup_amount' not in columns:
                # Миграция: создаем новую таблицу с правильной структурой
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS user_markups_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL UNIQUE,
                        markup_amount REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                # Копируем данные (проценты не конвертируем в суммы, так как это разные единицы)
                # Просто создаем новую таблицу, старые данные теряются
                cur.execute("DROP TABLE user_markups")
                cur.execute("ALTER TABLE user_markups_new RENAME TO user_markups")
            elif 'markup_amount' not in columns:
                # Если нет ни одной колонки, создаем таблицу заново
                cur.execute("DROP TABLE IF EXISTS user_markups")
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS user_markups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL UNIQUE,
                        markup_amount REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
        else:
            # Таблица не существует, создаем новую
            cur.execute('''
                CREATE TABLE IF NOT EXISTS user_markups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    markup_amount REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        
        # Миграция settings: удаляем старый ключ markup_percent, если он существует
        cur.execute("DELETE FROM settings WHERE key = 'markup_percent'")
        
        # Таблица товаров предзаказа (отдельная от основного прайса)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS preorder_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                name TEXT,
                memory TEXT,
                color TEXT,
                country TEXT,
                price INTEGER
            )
        ''')
        
        # Таблица корзины предзаказа (отдельная от основной корзины)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS preorder_cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
