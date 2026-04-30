import sqlite3
import os
import logging
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DATABASE_PATH", "/opt/three-layer-stations/orders.db")


def get_db_path() -> str:
    return DB_PATH


@contextmanager
def get_db():
    """Context manager for SQLite connection."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist, and run migrations."""
    os.makedirs(os.path.dirname(get_db_path()), exist_ok=True)
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                product_spec TEXT,
                product_image_url TEXT,
                price REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                customer_name TEXT,
                customer_phone TEXT,
                status TEXT DEFAULT 'pending',
                checkout_url TEXT,
                shopify_cart_id TEXT,
                shopify_order_id TEXT,
                cover_product_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("Database initialized at %s", get_db_path())
        # Run migrations for new columns
        migrate_add_columns(conn)


def migrate_add_columns(conn):
    """Add new columns for real product mapping if they don't exist."""
    migrations = [
        ("real_product_name", "TEXT DEFAULT ''"),
        ("real_product_spec", "TEXT DEFAULT ''"),
        ("real_product_image", "TEXT DEFAULT ''"),
        ("shopify_variant_id", "TEXT DEFAULT ''"),
        ("shopify_variant_price", "REAL DEFAULT 0"),
    ]

    # Get existing columns
    cursor = conn.execute("PRAGMA table_info(orders)")
    existing = {row[1] for row in cursor.fetchall()}

    for col_name, col_type in migrations:
        if col_name not in existing:
            logger.info("Adding column '%s' to orders table", col_name)
            conn.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")

    logger.info("Database migrations complete")


def insert_order(order: dict) -> dict:
    """Insert a new order into the database."""
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO orders (id, product_name, product_spec, product_image_url,
                                price, currency, customer_name, customer_phone, status,
                                real_product_name, real_product_spec, real_product_image,
                                shopify_variant_id, shopify_variant_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order["id"],
                order.get("product_name", ""),
                order.get("product_spec", ""),
                order.get("product_image_url", ""),
                order["price"],
                order.get("currency", "USD"),
                order.get("customer_name", ""),
                order.get("customer_phone", ""),
                "pending",
                order.get("real_product_name", order.get("product_name", "")),
                order.get("real_product_spec", order.get("product_spec", "")),
                order.get("real_product_image", order.get("product_image_url", "")),
                order.get("shopify_variant_id", ""),
                order.get("shopify_variant_price", 0),
            ),
        )
    return get_order(order["id"])


def get_order(order_id: str) -> dict | None:
    """Retrieve an order by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)


def update_order(order_id: str, **kwargs) -> dict | None:
    """Update order fields."""
    if not kwargs:
        return get_order(order_id)
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [order_id]
    with get_db() as conn:
        conn.execute(
            f"UPDATE orders SET {set_clause} WHERE id = ?", values
        )
    return get_order(order_id)


def list_orders(limit: int = 50, offset: int = 0) -> list[dict]:
    """List recent orders."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def search_orders(query: str, limit: int = 50) -> list[dict]:
    """Search orders by ID, customer name, product name, or phone."""
    with get_db() as conn:
        pattern = f"%{query}%"
        rows = conn.execute(
            """
            SELECT * FROM orders
            WHERE id LIKE ?
               OR customer_name LIKE ?
               OR customer_phone LIKE ?
               OR product_name LIKE ?
               OR real_product_name LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, pattern, limit),
        ).fetchall()
        return [dict(r) for r in rows]
