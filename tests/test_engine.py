from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from decimal import Decimal
import sqlite3
import pytest
from abi_store import db, billing as b, inventory as inv, khata as k


@pytest.mark.parametrize('amount', [True, float('nan'), float('inf'), -1, 0])
def test_invalid_khata_amount(amount):
    with pytest.raises(ValueError):
        k.khata_credit('Customer', amount)
    k.khata_credit('Customer', 10)
    with pytest.raises(ValueError):
        k.khata_payment('Customer', amount)
    assert k.khata_balance('Customer') == 10


@pytest.mark.parametrize('customer', ['', ' ', None])
def test_invalid_customer(customer):
    for fn in [lambda: k.khata_credit(customer,10), lambda: k.khata_payment(customer,1), lambda: k.khata_balance(customer)]:
        with pytest.raises(ValueError):
            fn()


def test_khata_decimal_settlement_and_overpayment():
    assert k.khata_credit('Customer', 0.1) == 0.1
    assert k.khata_credit('Customer', 0.2) == 0.3
    with pytest.raises(ValueError):
        k.khata_payment('Customer', 0.31)
    assert k.khata_payment('Customer', 0.3) == 0
    with pytest.raises(k.CustomerNotFound):
        k.khata_payment('Unknown', 1)


def test_receipt_decimal_prices():
    product()
    assert inv.receive_stock('A', Decimal('0.5'), cost_price=Decimal('1.2'), mrp=Decimal('2.5'))['mrp'] == 2.5



def test_stock_receipt_cannot_overflow():
    product(initial_qty=1e308)
    with pytest.raises(ValueError):
        inv.receive_stock('A', 1e308)
    assert inv.resolve_product('A')['qty'] == 1e308


def test_concurrent_competing_sales_cannot_oversell():
    product(initial_qty=1)
    bills = [draft(), draft()]
    start = Barrier(2)
    def sell(bill):
        start.wait(timeout=5)
        try:
            return b.finalize_bill(bill, str(bill), 'cash')
        except ValueError:
            return None
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(sell, bills))
    assert sum(result is not None for result in results) == 1
    assert inv.resolve_product('A')['qty'] == 0


@pytest.mark.parametrize('mode', ['cash', 'upi', 'card', 'bank_transfer'])
def test_supported_payment_modes(mode):
    product()
    assert b.finalize_bill(draft(), 'key', mode)['payment_mode'] == mode


def test_duplicate_line_add_checks_combined_stock():
    product(initial_qty=1)
    bill = draft()
    with pytest.raises(ValueError):
        b.add_line_item(bill,'A',1)
    assert b.get_bill_summary(bill)['lines'][0]['qty'] == 1


def test_half_paisa_rounding_and_tax_conservation():
    product(mrp=1.005, gst_rate=18)
    totals = b.compute_bill([{'sku':'A', 'qty':1}])
    assert totals['grand_total'] == 1.01
    line = totals['lines'][0]
    assert Decimal(str(line['taxable_value'])) + Decimal(str(line['cgst'])) + Decimal(str(line['sgst'])) == Decimal('1.01')


def test_khata_rollback_on_transaction_log_failure():
    k.khata_credit('Customer', 10)
    with db.khata_transaction() as conn:
        conn.execute("CREATE TRIGGER refuse_log BEFORE INSERT ON khata_txns BEGIN SELECT RAISE(ABORT,'test failure'); END")
    for fn in [k.khata_credit, k.khata_payment]:
        with pytest.raises(sqlite3.IntegrityError):
            fn('Customer', 1)
        assert k.khata_balance('Customer') == 10


def test_concurrent_khata_payments_refuse_overpayment():
    k.khata_credit('Customer', 10)
    start = Barrier(2)
    def pay():
        start.wait(timeout=5)
        try:
            return k.khata_payment('Customer', 10)
        except ValueError:
            return None
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: pay(), range(2)))
    assert results.count(0) == 1
    assert results.count(None) == 1
    assert k.khata_balance('Customer') == 0



def draft():
    bill = b.create_bill()
    b.add_line_item(bill, 'A', 1)
    return bill


def test_snapshot_and_half_up():
    product(mrp=2.5)
    with db.transaction(db.STOCK_DB_PATH) as conn:
        conn.executemany('INSERT INTO preferences VALUES (?, ?)', [('shop_name','My Shop'), ('shop_gstin','GST123')])
    bill = draft()
    result = b.finalize_bill(bill, 'key', 'cash')
    assert result['payable'] == 3
    assert result['lines'][0]['cost_price'] == 1
    assert result['shop_name'] == 'My Shop'
    assert result['shop_gstin'] == 'GST123'
    inv.receive_stock('A', 1, mrp=99)
    with db.transaction(db.STOCK_DB_PATH) as conn:
        conn.execute("UPDATE preferences SET value='changed'")
    assert b.get_bill_summary(bill) == b.get_finalized_bill(bill) == result
    with pytest.raises(ValueError):
        b.get_bill_summary(999)


@pytest.mark.parametrize('qty', [True, float('inf'), float('nan'), -1, 0])
def test_invalid_bill_qty(qty):
    product()
    bill = draft()
    with pytest.raises(ValueError):
        b.compute_bill([{'sku':'A', 'qty':qty}])
    with pytest.raises(ValueError):
        b.add_line_item(bill, 'A', qty)
    with pytest.raises(ValueError):
        b.edit_line_item(bill, 'A', qty)
    assert b.get_bill_summary(bill)['lines'][0]['qty'] == 1


@pytest.mark.parametrize('mode', ['credit', 'khata', '', 'Cash', None])
def test_unsupported_payment(mode):
    product()
    bill = draft()
    with pytest.raises(ValueError):
        b.finalize_bill(bill, 'key', mode)
    assert inv.resolve_product('A')['qty'] == 20


@pytest.mark.parametrize('key', ['', ' ', None])
def test_blank_idempotency_key(key):
    product()
    with pytest.raises(ValueError):
        b.finalize_bill(draft(), key, 'cash')


def test_idempotency_payload_binding():
    product()
    bill, other = draft(), draft()
    result = b.finalize_bill(bill, 'key', 'upi', 'ref')
    assert b.finalize_bill(bill, 'key', 'upi', 'ref') == result
    for args in [(other, 'upi', 'ref'), (bill, 'cash', 'ref'), (bill, 'upi', 'different')]:
        with pytest.raises(ValueError):
            b.finalize_bill(args[0], 'key', args[1], args[2])
    assert inv.resolve_product('A')['qty'] == 19


def test_finalized_edits_refused():
    product()
    bill = draft()
    b.finalize_bill(bill, 'key', 'cash')
    for action in [lambda: b.add_line_item(bill,'A',1), lambda: b.edit_line_item(bill,'A',2), lambda: b.remove_line_item(bill,'A')]:
        with pytest.raises(ValueError):
            action()


def test_concurrent_retry_is_one_sale(monkeypatch):
    product()
    bill = draft()
    barrier = Barrier(2)
    original = b.get_connection
    # Force the legacy pre-transaction idempotency SELECTs to both see no key.
    class Conn:
        def __init__(self): self.conn = original()
        def execute(self, sql, params=()):
            cur = self.conn.execute(sql, params)
            if 'SELECT result_json FROM idempotency_keys' in sql:
                barrier.wait(timeout=5)
            return cur
        def close(self): self.conn.close()
    monkeypatch.setattr(b, 'get_connection', Conn)
    start = Barrier(2)
    def run():
        start.wait(timeout=5)
        return b.finalize_bill(bill, 'same', 'cash')
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert results[0] == results[1]
    assert inv.resolve_product('A')['qty'] == 19


@pytest.mark.parametrize('action', ['add', 'remove', 'edit'])
def test_draft_check_holds_writer_lock(monkeypatch, action):
    product()
    bill = draft()
    checked, release = Event(), Event()
    original = b._get_bill
    def paused(conn, bill_id):
        row = original(conn, bill_id)
        checked.set()
        assert release.wait(5)
        return row
    monkeypatch.setattr(b, '_get_bill', paused)
    actions = {'add':lambda: b.add_line_item(bill,'A',1), 'remove':lambda: b.remove_line_item(bill,'A'), 'edit':lambda: b.edit_line_item(bill,'A',2)}
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(actions[action])
        try:
            assert checked.wait(2), 'edit skipped draft status check'
            conn = sqlite3.connect(db.STOCK_DB_PATH, timeout=0.05)
            try:
                with pytest.raises(sqlite3.OperationalError, match='locked'):
                    conn.execute('BEGIN IMMEDIATE')
            finally:
                conn.close()
        finally:
            release.set()
        future.result()


def test_finalize_rolls_back_all_skus_and_key():
    product()
    product('B', 'Banana')
    bill = draft()
    b.add_line_item(bill,'B',2)
    with db.transaction(db.STOCK_DB_PATH) as conn:
        conn.execute("UPDATE products SET qty=0 WHERE sku='B'")
    with pytest.raises(ValueError):
        b.finalize_bill(bill,'key','cash')
    assert inv.resolve_product('A')['qty'] == 20
    conn = db.get_connection()
    try:
        assert conn.execute('SELECT status FROM bills WHERE id=?',(bill,)).fetchone()[0] == 'draft'
        assert conn.execute('SELECT count(*) FROM idempotency_keys').fetchone()[0] == 0
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_DIR', tmp_path)
    monkeypatch.setattr(db, 'STOCK_DB_PATH', tmp_path / 'stock.db')
    monkeypatch.setattr(db, 'KHATA_DB_PATH', tmp_path / 'khata.db')
    # Explicit path also isolates older transaction implementations.
    monkeypatch.setattr(b, 'transaction', lambda: db.transaction(db.STOCK_DB_PATH))
    monkeypatch.setattr(inv, 'transaction', lambda: db.transaction(db.STOCK_DB_PATH))
    db.init_db()


def product(sku='A', name='Apple', **kw):
    args = dict(unit='piece', hsn_code='1', gst_rate=5, cost_price=1, mrp=10, initial_qty=20)
    args.update(kw)
    inv.add_product(sku, name, **args)


@pytest.mark.parametrize('field,value', [('sku',' '), ('name',''), ('gst_rate',101), ('gst_rate',float('inf')), ('mrp',float('inf')), ('cost_price',True), ('initial_qty',float('nan')), ('reorder_level',True)])
def test_invalid_product(field, value):
    with pytest.raises(ValueError):
        product(**{field:value})


def test_resolver_keeps_duplicate_names_and_prefers_sku():
    product('A', 'Apple')
    product('B', 'Apple')
    assert inv.resolve_product('A')['sku'] == 'A'
    with pytest.raises(inv.AmbiguousProduct) as exc:
        inv.resolve_product('Apple')
    assert {p['sku'] for p in exc.value.candidates} == {'A', 'B'}
    assert inv.resolve_product('A')['reorder_level'] == 10


@pytest.mark.parametrize('qty', [True, float('nan'), float('inf'), 0, -1])
def test_invalid_stock_qty(qty):
    product()
    with pytest.raises(ValueError):
        inv.receive_stock('A', qty)
    with pytest.raises(ValueError):
        inv.check_stock('A', qty)
