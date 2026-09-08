"""Transactional billing with immutable priced snapshots.

Financial calculations use Decimal(str(value)) and ROUND_HALF_UP. The legacy
SQLite schema still stores quantities/prices as REAL; this is not an integer
minor-unit accounting engine. Credit checkout is deliberately unsupported until
stock and the separate khata ledger can be committed atomically.
"""
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from .db import get_connection, transaction
from .inventory import ProductNotFound, _validate_prices
from .validation import number, text, money


PAYMENT_MODES = ('cash', 'upi', 'card', 'bank_transfer')


def _round2(x: float) -> float:
    return float(money(x))


def _price_line(product: dict, qty: float) -> dict:
    """Back inclusive GST out of the rounded retail line amount."""
    qty = number(qty, 'qty', positive=True)
    _validate_prices(product['cost_price'], product['mrp'])
    mrp = number(product['mrp'], 'mrp')
    gst = number(product['gst_rate'], 'gst_rate', maximum=100)
    line_total = money(mrp * qty)
    taxable = money(line_total / (1 + gst / 100))
    tax = line_total - taxable
    cgst = money(tax / 2)
    return {
        'sku': product['sku'], 'name': product['name'], 'hsn_code': product['hsn_code'],
        'unit': product['unit'], 'qty': float(qty), 'mrp': float(mrp),
        'cost_price': float(product['cost_price']), 'gst_rate': float(gst),
        'taxable_value': float(taxable), 'cgst': float(cgst),
        'sgst': float(tax - cgst), 'line_total': float(line_total),
    }


def _aggregate(lines: list[dict]) -> dict:
    def total(field):
        return money(sum((Decimal(str(line[field])) for line in lines), Decimal(0)))
    taxable, cgst, sgst, grand = (total(f) for f in ('taxable_value', 'cgst', 'sgst', 'line_total'))
    payable = int(grand.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    return {
        'lines': lines, 'subtotal_taxable': float(taxable), 'total_cgst': float(cgst),
        'total_sgst': float(sgst), 'total_tax': float(cgst + sgst),
        'grand_total': float(grand), 'round_off': float(Decimal(payable) - grand), 'payable': payable,
    }


def _compute(conn, line_items):
    lines = []
    for item in line_items:
        text(item['sku'], 'sku')
        number(item['qty'], 'qty', positive=True)
        row = conn.execute('SELECT * FROM products WHERE sku=?', (item['sku'],)).fetchone()
        if row is None:
            raise ProductNotFound(item['sku'])
        lines.append(_price_line(dict(row), item['qty']))
    return _aggregate(lines)


def compute_bill(line_items: list[dict]) -> dict:
    """Live catalog preview, read from a consistent database snapshot."""
    conn = get_connection()
    try:
        conn.execute('BEGIN')
        return _compute(conn, line_items)
    finally:
        conn.close()


def create_bill() -> int:
    with transaction() as conn:
        cur = conn.execute("INSERT INTO bills (status, created_at) VALUES ('draft', ?)",
                           (datetime.now(timezone.utc).isoformat(),))
        return cur.lastrowid


def _get_bill(conn, bill_id: int):
    bill = conn.execute('SELECT * FROM bills WHERE id=?', (bill_id,)).fetchone()
    if bill is None:
        raise ValueError(f'No such bill {bill_id}')
    return bill


def _draft(conn, bill_id):
    bill = _get_bill(conn, bill_id)
    if bill['status'] != 'draft':
        raise ValueError('Bill is already finalized')
    return bill


def _stock(conn, sku, qty):
    row = conn.execute('SELECT qty FROM products WHERE sku=?', (sku,)).fetchone()
    if row is None:
        raise ProductNotFound(sku)
    if number(row['qty'], 'stock qty') < qty:
        raise ValueError(f'Not enough stock of {sku} for {qty}')


def add_line_item(bill_id: int, sku: str, qty: float):
    text(sku, 'sku')
    qty = number(qty, 'qty', positive=True)
    with transaction() as conn:
        _draft(conn, bill_id)
        existing = conn.execute('SELECT qty FROM bill_items WHERE bill_id=? AND sku=?', (bill_id, sku)).fetchone()
        combined = qty + (number(existing['qty'], 'qty', positive=True) if existing else 0)
        _stock(conn, sku, combined)
        conn.execute('INSERT INTO bill_items (bill_id,sku,qty) VALUES (?,?,?) '
                     'ON CONFLICT(bill_id,sku) DO UPDATE SET qty=excluded.qty',
                     (bill_id, sku, float(combined)))


def remove_line_item(bill_id: int, sku: str):
    text(sku, 'sku')
    with transaction() as conn:
        _draft(conn, bill_id)
        conn.execute('DELETE FROM bill_items WHERE bill_id=? AND sku=?', (bill_id, sku))


def edit_line_item(bill_id: int, sku: str, new_qty: float):
    """Set a positive draft quantity; removal must be explicit."""
    text(sku, 'sku')
    qty = number(new_qty, 'qty', positive=True)
    with transaction() as conn:
        _draft(conn, bill_id)
        _stock(conn, sku, qty)
        cur = conn.execute('UPDATE bill_items SET qty=? WHERE bill_id=? AND sku=?', (float(qty), bill_id, sku))
        if cur.rowcount == 0:
            raise ValueError(f'No line item {sku} on bill {bill_id}')


def _snapshot(bill):
    return {'bill_id': bill['id'], 'finalized_at': bill['finalized_at'],
            'payment_mode': bill['payment_mode'], 'payment_ref': bill['payment_ref'],
            **json.loads(bill['totals_json'])}


def get_bill_summary(bill_id: int) -> dict:
    """Live draft preview or frozen finalized snapshot; missing bills raise."""
    conn = get_connection()
    try:
        conn.execute('BEGIN')
        bill = _get_bill(conn, bill_id)
        if bill['status'] == 'finalized':
            return _snapshot(bill)
        items = conn.execute('SELECT sku,qty FROM bill_items WHERE bill_id=? ORDER BY id', (bill_id,)).fetchall()
        return _compute(conn, items)
    finally:
        conn.close()


def finalize_bill(bill_id: int, idempotency_key: str, payment_mode: str,
                  payment_ref: str = None) -> dict:
    """Atomically price, deduct stock and persist a retry result.

    A key is bound to the exact bill, payment mode and reference. Retrying that
    payload replays its result; reusing the key for any other payload refuses.
    """
    text(idempotency_key, 'idempotency_key')
    if payment_mode not in PAYMENT_MODES:
        raise ValueError('Unsupported payment mode; use cash/upi/card/bank_transfer. Credit sales are not supported.')
    if payment_ref is not None and not isinstance(payment_ref, str):
        raise ValueError('payment_ref must be a string or None')
    with transaction() as conn:
        existing = conn.execute('SELECT bill_id,result_json FROM idempotency_keys WHERE key=?', (idempotency_key,)).fetchone()
        if existing is not None:
            prior = _get_bill(conn, existing['bill_id'])
            if existing['bill_id'] != bill_id or prior['payment_mode'] != payment_mode or prior['payment_ref'] != payment_ref:
                raise ValueError('Idempotency key is already bound to a different bill or payment payload')
            return json.loads(existing['result_json'])
        _draft(conn, bill_id)
        items = conn.execute('SELECT sku,qty FROM bill_items WHERE bill_id=? ORDER BY id', (bill_id,)).fetchall()
        if not items:
            raise ValueError('Bill has no line items')
        lines = []
        for item in items:
            row = conn.execute('SELECT * FROM products WHERE sku=?', (item['sku'],)).fetchone()
            if row is None:
                raise ProductNotFound(item['sku'])
            line = _price_line(dict(row), item['qty'])
            cur = conn.execute('UPDATE products SET qty=qty-? WHERE sku=? AND qty>=? AND mrp>=cost_price',
                               (item['qty'], item['sku'], item['qty']))
            if cur.rowcount != 1:
                raise ValueError(f"Not enough stock of {item['sku']} to finalize")
            lines.append(line)
        prefs = dict(conn.execute("SELECT key,value FROM preferences WHERE key IN ('shop_name','shop_gstin')").fetchall())
        totals = {**_aggregate(lines), 'shop_name': prefs.get('shop_name', ''), 'shop_gstin': prefs.get('shop_gstin', '')}
        now = datetime.now(timezone.utc).isoformat()
        result = {'bill_id': bill_id, 'finalized_at': now, 'payment_mode': payment_mode, 'payment_ref': payment_ref, **totals}
        conn.execute("UPDATE bills SET status='finalized',payment_mode=?,payment_ref=?,finalized_at=?,totals_json=? WHERE id=?",
                     (payment_mode, payment_ref, now, json.dumps(totals, allow_nan=False), bill_id))
        conn.execute('INSERT INTO idempotency_keys (key,bill_id,result_json,created_at) VALUES (?,?,?,?)',
                     (idempotency_key, bill_id, json.dumps(result, allow_nan=False), now))
        return result


def get_finalized_bill(bill_id: int) -> dict:
    """Read historical prices and shop identity, never today's catalog."""
    conn = get_connection()
    try:
        bill = _get_bill(conn, bill_id)
        if bill['status'] != 'finalized':
            raise ValueError(f'Bill {bill_id} is not finalized yet')
        return _snapshot(bill)
    finally:
        conn.close()
