"""db.py — SQLite paths, schema, migrations, and locked transactions.

Operational assets live under SUPERMARKET_DATA_DIR, separate from source:
- database/stock.db: products, bills, bill_items, stock receipts, preferences
- database/khata.db: customer credit ledger

Every write that must be atomic uses BEGIN IMMEDIATE so concurrent sales and
stock-ins serialize instead of corrupting quantities or balances.
"""

import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(os.environ.get("SUPERMARKET_DATA_DIR", Path.home() / ".local" / "share" / "supermarket-ops-bot")).expanduser().resolve()
DB_DIR = ROOT / "database"
STOCK_DB_PATH = DB_DIR / "stock.db"
KHATA_DB_PATH = DB_DIR / "khata.db"

SUPPORTED_UNITS = {"kg", "g", "litre", "ml", "packet", "dozen", "piece"}
PACKAGING_TYPES = {"loose", "packaged"}


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_connection() -> sqlite3.Connection:
    """Connection for stock/billing/product/preference data."""
    return _connect(STOCK_DB_PATH)


def get_khata_connection() -> sqlite3.Connection:
    """Connection for customer credit ledger data."""
    return _connect(KHATA_DB_PATH)


@contextmanager
def transaction(path: Path | None = None):
    """BEGIN IMMEDIATE transaction for atomic writes."""
    conn = _connect(STOCK_DB_PATH if path is None else path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def khata_transaction():
    """BEGIN IMMEDIATE transaction for customer credit writes."""
    with transaction(KHATA_DB_PATH) as conn:
        yield conn


STOCK_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    unit TEXT NOT NULL CHECK (unit IN ('kg','g','litre','ml','packet','dozen','piece')),
    packaging_type TEXT NOT NULL DEFAULT 'packaged' CHECK (packaging_type IN ('loose','packaged')),
    hsn_code TEXT NOT NULL,
    gst_rate REAL NOT NULL CHECK (gst_rate >= 0),
    cost_price REAL NOT NULL CHECK (cost_price >= 0),
    mrp REAL NOT NULL CHECK (mrp >= cost_price),
    qty REAL NOT NULL DEFAULT 0 CHECK (qty >= 0),
    reorder_level REAL NOT NULL DEFAULT 10 CHECK (reorder_level >= 0)
);

CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','finalized')),
    payment_mode TEXT,
    payment_ref TEXT,
    created_at TEXT NOT NULL,
    finalized_at TEXT,
    totals_json TEXT
);

CREATE TABLE IF NOT EXISTS bill_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL REFERENCES bills(id),
    sku TEXT NOT NULL REFERENCES products(sku),
    qty REAL NOT NULL CHECK (qty > 0),
    UNIQUE (bill_id, sku)
);

CREATE TABLE IF NOT EXISTS stock_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL REFERENCES products(sku),
    qty REAL NOT NULL CHECK (qty > 0),
    cost_price REAL NOT NULL CHECK (cost_price >= 0),
    mrp REAL NOT NULL CHECK (mrp >= cost_price),
    received_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    bill_id INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

KHATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS khata (
    customer TEXT PRIMARY KEY,
    balance REAL NOT NULL DEFAULT 0 CHECK (balance >= 0)
);

CREATE TABLE IF NOT EXISTS khata_txns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    txn_type TEXT NOT NULL CHECK (txn_type IN ('credit','payment')),
    created_at TEXT NOT NULL,
    bill_id INTEGER
);
"""


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def init_db():
    stock = get_connection()
    try:
        stock.executescript(STOCK_SCHEMA)
        cols = _column_names(stock, "products")
        if "packaging_type" not in cols:
            stock.execute("ALTER TABLE products ADD COLUMN packaging_type TEXT NOT NULL DEFAULT 'packaged'")
        stock.commit()
    finally:
        stock.close()

    khata = get_khata_connection()
    try:
        khata.executescript(KHATA_SCHEMA)
        khata.commit()
    finally:
        khata.close()
