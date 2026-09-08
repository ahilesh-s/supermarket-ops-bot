"""Generate a small, explicitly fictional shop and its PDF/PPTX artifacts."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory; existing paths are refused')
    args = parser.parse_args()
    root = args.output.expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error(f'Output already exists: {root}. Choose a new directory.')
    os.environ['SUPERMARKET_DATA_DIR'] = str(root)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from abi_store import (init_db, set_preference, add_product, receive_stock, create_bill,
                           add_line_item, finalize_bill, generate_invoice_pdf,
                           generate_analysis_deck, khata_credit, khata_payment, daily_close)
    init_db()
    set_preference('shop_name', 'Demonstration Market')
    set_preference('timezone', 'Asia/Kolkata')
    add_product('DEMO-RICE', 'Demonstration Rice', 'kg', '1006', 0, 40, 50, packaging_type='loose')
    receive_stock('DEMO-RICE', 20)
    bill_id = create_bill()
    add_line_item(bill_id, 'DEMO-RICE', 2)
    bill = finalize_bill(bill_id, 'demo-checkout-1', 'cash')
    # Standalone opening balance, NOT a credit payment for the cash bill above.
    khata_credit('Demonstration Customer', 100)
    balance = khata_payment('Demonstration Customer', 25)
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat()
    result = {'sample_data': True, 'data_dir': str(root), 'bill': bill,
              'standalone_khata_balance': balance, 'close': daily_close(today),
              'invoice': generate_invoice_pdf(bill_id),
              'deck': generate_analysis_deck(today, today)}
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
