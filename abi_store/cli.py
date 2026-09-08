"""Allowlisted JSON command interface for an owner-operated Hermes session."""
import argparse
import importlib
import inspect
import json
import sqlite3
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import db
from .inventory import AmbiguousProduct, ProductNotFound
from .khata import CustomerNotFound

OPERATIONS = {
    'inventory.add_product': True,
    'inventory.receive_stock': True,
    'inventory.resolve_product': False,
    'inventory.check_stock': False,
    'inventory.low_stock_items': False,
    'billing.compute_bill': False,
    'billing.create_bill': False,
    'billing.add_line_item': False,
    'billing.edit_line_item': False,
    'billing.remove_line_item': False,
    'billing.get_bill_summary': False,
    'billing.finalize_bill': True,
    'billing.get_finalized_bill': False,
    'khata.khata_credit': True,
    'khata.khata_payment': True,
    'khata.khata_balance': False,
    'preferences.get_preference': False,
    'preferences.set_preference': True,
    'reports.daily_close': False,
    'reports.purchase_summary': False,
    'reports.margin_report': False,
    'documents.generate_invoice_pdf': False,
    'documents.generate_analysis_deck': False,
}


def operation(name):
    if name not in OPERATIONS:
        raise ValueError(f'Unknown operation: {name}')
    module, function = name.split('.')
    return getattr(importlib.import_module(f'abi_store.{module}'), function)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Supermarket Ops Bot: local store operations as JSON')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='Create empty databases; existing data is preserved')
    init.add_argument('--shop-name')
    init.add_argument('--timezone')
    commands.add_parser('status', help='Show storage location and database availability')
    commands.add_parser('operations', help='List allowlisted functions and argument signatures')
    call = commands.add_parser('call', help='Call an operation with a JSON object (stdin by default)')
    call.add_argument('operation')
    call.add_argument('--json', help='Arguments as JSON; omit to read stdin')
    call.add_argument('--confirm', action='store_true', help='Owner has approved this stock, credit, or settings change')
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            if args.timezone:
                ZoneInfo(args.timezone)
            if args.shop_name is not None and not args.shop_name.strip():
                raise ValueError('shop-name must not be blank')
            db.init_db()
            from .preferences import get_preference, set_preference
            for key, value, default in [('shop_name', args.shop_name, 'Your Supermarket'),
                                         ('timezone', args.timezone, 'Asia/Kolkata')]:
                if value is not None or get_preference(key) is None:
                    set_preference(key, value if value is not None else default)
            result = {'data_dir': str(db.ROOT), 'initialized': True}
        elif args.command == 'status':
            result = {'data_dir': str(db.ROOT), 'stock_db_exists': db.STOCK_DB_PATH.is_file(),
                      'khata_db_exists': db.KHATA_DB_PATH.is_file()}
        elif args.command == 'operations':
            result = {name: {'signature': str(inspect.signature(operation(name))),
                             'requires_confirmation': confirmation}
                      for name, confirmation in OPERATIONS.items()}
        else:
            func = operation(args.operation)
            payload = json.loads(args.json if args.json is not None else sys.stdin.read())
            if not isinstance(payload, dict):
                raise ValueError('Arguments must be a JSON object')
            if OPERATIONS[args.operation] and not args.confirm:
                raise ValueError('Owner confirmation required; use --confirm only after approval')
            if not db.STOCK_DB_PATH.is_file() or not db.KHATA_DB_PATH.is_file():
                raise ValueError('Store is not initialized. Run init first.')
            result = func(**payload)
        print(json.dumps({'ok': True, 'result': result}, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error, ZoneInfoNotFoundError,
            ProductNotFound, AmbiguousProduct, CustomerNotFound) as exc:
        error = {'ok': False, 'error': type(exc).__name__, 'message': str(exc)}
        if isinstance(exc, AmbiguousProduct):
            error['candidates'] = exc.candidates
        print(json.dumps(error, allow_nan=False), file=sys.stderr)
        return 1
