import json
from db.models import get_db, init_db

def setup_db():
    init_db()


def import_products_from_json(path):
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    with get_db() as conn:
        cur = conn.cursor()
        for prod in items:
            cur.execute(
                "INSERT INTO products (category, name, memory, color, country, price) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    prod["category"],
                    prod["name"],
                    prod["memory"],
                    prod["color"],
                    prod["country"],
                    prod["price"]
                )
            )
        conn.commit()
