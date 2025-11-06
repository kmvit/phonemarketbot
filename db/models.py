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
        from config import DEFAULT_MARKUP_PERCENT
        cur.execute('''
            INSERT OR IGNORE INTO settings (key, value) 
            VALUES ('markup_percent', ?)
        ''', (str(DEFAULT_MARKUP_PERCENT),))
        
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
        
        # Таблица персональных процентов пользователей
        cur.execute('''
            CREATE TABLE IF NOT EXISTS user_markups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                markup_percent REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
