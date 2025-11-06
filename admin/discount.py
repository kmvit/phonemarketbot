from db.models import get_db

def get_markup_percent():
    """Получить текущий процент наценки"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'markup_percent'")
        row = cur.fetchone()
        if row:
            try:
                return float(row[0])
            except:
                return 10.0
        return 10.0

def set_markup_percent(percent):
    """Установить процент наценки"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO settings (key, value) 
            VALUES ('markup_percent', ?)
        """, (str(percent),))
        conn.commit()

def get_user_markup_percent(user_id):
    """Получить персональный процент наценки для пользователя"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT markup_percent FROM user_markups WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            try:
                return float(row[0])
            except:
                return None
        return None

def set_user_markup_percent(user_id, percent):
    """Установить персональный процент наценки для пользователя"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO user_markups (user_id, markup_percent, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (user_id, percent))
        conn.commit()

def delete_user_markup(user_id):
    """Удалить персональный процент наценки для пользователя"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM user_markups WHERE user_id = ?", (user_id,))
        conn.commit()
        return cur.rowcount > 0

def get_all_user_markups():
    """Получить все персональные проценты пользователей"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, markup_percent, created_at, updated_at
            FROM user_markups
            ORDER BY updated_at DESC
        """)
        rows = cur.fetchall()
        return [
            {
                "user_id": row[0],
                "markup_percent": row[1],
                "created_at": row[2],
                "updated_at": row[3],
            } for row in rows
        ]

def calculate_price_with_markup(base_price, user_id=None):
    """Рассчитать цену с учетом персонального процента пользователя"""
    if user_id:
        user_markup = get_user_markup_percent(user_id)
        if user_markup is not None:
            # Применяем персональный процент к базовой цене
            return int(base_price * (1 + user_markup / 100))
    # Если нет персонального процента, возвращаем базовую цену
    return base_price

