"""inventory.py — product catalog and stock.

The agent must resolve products through this module and never guess a SKU from
memory. Stock-in is transactional, validates units/loose-vs-packaged, logs every
receipt, and refuses prices that would sell below cost.
"""

import difflib
from datetime import datetime, timezone
from .db import get_connection, transaction, SUPPORTED_UNITS, PACKAGING_TYPES
from .validation import number, text


class ProductNotFound(Exception):
    pass


class AmbiguousProduct(Exception):
    def __init__(self, candidates: list[dict]):
        self.candidates = candidates
        super().__init__(f"Multiple matches: {[c['name'] for c in candidates]}")


def _positive(value: float, field: str):
    return number(value, field, positive=True)


def _validate_unit(unit: str):
    if unit not in SUPPORTED_UNITS:
        raise ValueError(f"Unsupported unit '{unit}'. Use one of: {', '.join(sorted(SUPPORTED_UNITS))}")


def _validate_packaging(packaging_type: str):
    if packaging_type not in PACKAGING_TYPES:
        raise ValueError("packaging_type must be 'loose' or 'packaged'")


def _validate_prices(cost_price: float, mrp: float):
    cost_price = number(cost_price, 'cost_price')
    mrp = number(mrp, 'mrp')
    if mrp < cost_price:
        raise ValueError("Refusing to sell below cost: mrp cannot be below cost_price")


def add_product(sku, name, unit, hsn_code, gst_rate, cost_price, mrp,
                 initial_qty=0, reorder_level=10, packaging_type="packaged"):
    text(sku, "sku")
    text(name, "name")
    _validate_unit(unit)
    _validate_packaging(packaging_type)
    _validate_prices(cost_price, mrp)
    gst_rate = float(number(gst_rate, 'gst_rate', maximum=100))
    initial_qty = float(number(initial_qty, 'initial_qty'))
    reorder_level = float(number(reorder_level, 'reorder_level'))
    cost_price, mrp = float(cost_price), float(mrp)
    with transaction() as conn:
        conn.execute(
            "INSERT INTO products (sku, name, unit, packaging_type, hsn_code, gst_rate, cost_price, "
            "mrp, qty, reorder_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sku, name, unit, packaging_type, hsn_code, gst_rate, cost_price, mrp, initial_qty, reorder_level),
        )


def resolve_product(query: str, cutoff: float = 0.5) -> dict:
    """Deterministic lookup: exact, fuzzy, then substring.

    Returns one product dict or raises AmbiguousProduct/ProductNotFound so the
    agent asks instead of guessing.
    """
    text(query, 'query')
    conn = get_connection()
    try:
        exact_sku = conn.execute('SELECT * FROM products WHERE sku = ?', (query,)).fetchone()
        if exact_sku is not None:
            return dict(exact_sku)
        rows = [dict(r) for r in conn.execute('SELECT * FROM products ORDER BY sku')]
    finally:
        conn.close()
    query_lower = query.strip().lower()
    matches = [r for r in rows if r['name'].lower() == query_lower]
    if not matches:
        names = difflib.get_close_matches(query_lower, sorted({r['name'].lower() for r in rows}), n=5, cutoff=cutoff)
        matches = [r for r in rows if r['name'].lower() in names]
    if not matches:
        matches = [r for r in rows if query_lower in r['name'].lower()]
    if not matches:
        raise ProductNotFound(f"No product matches '{query}'")
    if len(matches) != 1:
        raise AmbiguousProduct(matches)
    return matches[0]


def receive_stock(sku: str, qty: float, cost_price: float = None, mrp: float = None) -> dict:
    """Stock-in. Price/tax facts come from DB unless explicitly updated by owner.

    Uses BEGIN IMMEDIATE so a sale and a stock-in cannot corrupt stock. Never
    deletes stock. Refuses negative/zero receipts and below-cost MRP updates.
    """
    text(sku, "sku")
    qty = float(_positive(qty, "qty"))
    now = datetime.now(timezone.utc).isoformat()
    with transaction() as conn:
        row = conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
        if row is None:
            raise ProductNotFound(sku)
        used_cost = cost_price if cost_price is not None else row["cost_price"]
        used_mrp = mrp if mrp is not None else row["mrp"]
        _validate_prices(used_cost, used_mrp)
        used_cost, used_mrp = float(used_cost), float(used_mrp)
        cost_price = float(cost_price) if cost_price is not None else None
        mrp = float(mrp) if mrp is not None else None

        updated_qty = number(number(row['qty'], 'stock qty') + number(qty, 'qty', positive=True), 'stock qty')
        updates, params = ["qty = ?"], [float(updated_qty)]
        if cost_price is not None:
            updates.append("cost_price = ?")
            params.append(cost_price)
        if mrp is not None:
            updates.append("mrp = ?")
            params.append(mrp)
        params.append(sku)
        conn.execute(f"UPDATE products SET {', '.join(updates)} WHERE sku = ?", params)

        conn.execute(
            "INSERT INTO stock_receipts (sku, qty, cost_price, mrp, received_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (sku, qty, used_cost, used_mrp, now),
        )
        return dict(conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone())


def check_stock(sku: str, qty: float) -> bool:
    text(sku, "sku")
    qty = float(_positive(qty, "qty"))
    conn = get_connection()
    row = conn.execute("SELECT qty FROM products WHERE sku = ?", (sku,)).fetchone()
    conn.close()
    if row is None:
        raise ProductNotFound(sku)
    return row["qty"] >= qty


def low_stock_items() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM products WHERE qty <= reorder_level").fetchall()
    conn.close()
    return [dict(r) for r in rows]
