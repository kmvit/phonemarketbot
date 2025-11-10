from db.models import get_db

def get_markup_amount():
    """Получить текущую сумму наценки"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'markup_amount'")
        row = cur.fetchone()
        if row:
            try:
                return float(row[0])
            except:
                return 0.0
        return 0.0

def set_markup_amount(amount):
    """Установить сумму наценки"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO settings (key, value) 
            VALUES ('markup_amount', ?)
        """, (str(amount),))
        conn.commit()

def get_user_markup_amount(user_id):
    """Получить персональную сумму наценки для пользователя"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT markup_amount FROM user_markups WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            try:
                return float(row[0])
            except:
                return None
        return None

def set_user_markup_amount(user_id, amount):
    """Установить персональную сумму наценки для пользователя"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO user_markups (user_id, markup_amount, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (user_id, amount))
        conn.commit()

def delete_user_markup(user_id):
    """Удалить персональную сумму наценки для пользователя"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM user_markups WHERE user_id = ?", (user_id,))
        conn.commit()
        return cur.rowcount > 0

def get_all_user_markups():
    """Получить все персональные суммы наценки пользователей"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, markup_amount, created_at, updated_at
            FROM user_markups
            ORDER BY updated_at DESC
        """)
        rows = cur.fetchall()
        return [
            {
                "user_id": row[0],
                "markup_amount": row[1],
                "created_at": row[2],
                "updated_at": row[3],
            } for row in rows
        ]

def calculate_price_with_markup(base_price, user_id=None):
    """Рассчитать цену с учетом персональной суммы наценки пользователя"""
    if user_id:
        user_markup = get_user_markup_amount(user_id)
        if user_markup is not None:
            # Применяем персональную сумму к базовой цене
            return int(base_price + user_markup)
    
    # Применяем стандартную наценку
    markup_amount = get_markup_amount()
    return int(base_price + markup_amount)

