"""Standalone customer credit ledger (not integrated with checkout).

Each operation is atomic, but has NO idempotency key and is NOT retry safe.
Amounts/balances are calculated with Decimal; legacy SQLite storage is REAL.
"""
from datetime import datetime, timezone
from .db import khata_transaction, get_khata_connection
from .validation import number, text


class CustomerNotFound(Exception):
    pass


def _positive(amount: float):
    return number(amount, 'amount', positive=True)


def khata_credit(customer: str, amount: float, bill_id: int = None) -> float:
    """Add independent credit, creating the customer if needed. Not retry safe."""
    text(customer, 'customer')
    amount = _positive(amount)
    now = datetime.now(timezone.utc).isoformat()
    with khata_transaction() as conn:
        row = conn.execute('SELECT balance FROM khata WHERE customer=?', (customer,)).fetchone()
        balance = number(row['balance'], 'balance') if row else 0
        updated = number(balance + amount, 'balance')
        conn.execute('INSERT INTO khata (customer,balance) VALUES (?,?) '
                     'ON CONFLICT(customer) DO UPDATE SET balance=excluded.balance', (customer, float(updated)))
        conn.execute("INSERT INTO khata_txns (customer,amount,txn_type,created_at,bill_id) VALUES (?,?,'credit',?,?)",
                     (customer, float(amount), now, bill_id))
        return float(updated)


def khata_payment(customer: str, amount: float) -> float:
    """Settle independent debt; refuse unknown customers/overpayment. Not retry safe."""
    text(customer, 'customer')
    amount = _positive(amount)
    now = datetime.now(timezone.utc).isoformat()
    with khata_transaction() as conn:
        row = conn.execute('SELECT balance FROM khata WHERE customer=?', (customer,)).fetchone()
        if row is None:
            raise CustomerNotFound(customer)
        balance = number(row['balance'], 'balance')
        if amount > balance:
            raise ValueError(f'Payment {amount} exceeds khata balance {balance}')
        updated = balance - amount
        conn.execute('UPDATE khata SET balance=? WHERE customer=?', (float(updated), customer))
        conn.execute("INSERT INTO khata_txns (customer,amount,txn_type,created_at) VALUES (?,?,'payment',?)",
                     (customer, float(amount), now))
        return float(updated)


def khata_balance(customer: str) -> float:
    text(customer, 'customer')
    conn = get_khata_connection()
    try:
        row = conn.execute('SELECT balance FROM khata WHERE customer=?', (customer,)).fetchone()
        if row is None:
            raise CustomerNotFound(customer)
        return row['balance']
    finally:
        conn.close()
