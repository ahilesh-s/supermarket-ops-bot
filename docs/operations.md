# Operations

The Python API is importable as `abi_store`. The CLI exposes a fixed allowlist rather than arbitrary imports or code execution:

```sh
uv run supermarket-ops operations
```

This prints signatures and which operations require the accidental-write confirmation flag. `call` takes a JSON object via `--json` or stdin. Successful calls return `{"ok":true,"result":...}`. Errors go to stderr with exit status 1; CLI syntax errors use argparse's exit status 2.

## Catalog and receiving

The following is a fictional example, not a live product record. Obtain approval before creating or changing real catalog data.

```sh
uv run supermarket-ops call inventory.add_product --confirm --json \
  '{"sku":"DEMO-RICE","name":"Demonstration Rice","unit":"kg","packaging_type":"loose","hsn_code":"1006","gst_rate":0,"cost_price":40,"mrp":50}'
uv run supermarket-ops call inventory.receive_stock --confirm --json \
  '{"sku":"DEMO-RICE","qty":20}'
uv run supermarket-ops call inventory.resolve_product --json '{"query":"DEMO-RICE"}'
uv run supermarket-ops call inventory.low_stock_items --json '{}'
```

Product registration is distinct from receiving. Prefer starting at zero and using receipts for physical stock-in so purchasing reports have receipt records. `initial_qty` is available for opening balances but is not a purchase receipt. Quantities are in the product's declared unit; there is no automatic conversion between grams and kilograms or pieces and dozens.

A receipt may update cost and MRP only when explicitly supplied. The default reorder level is 10; it is a per-product field, not a total-store count.

## Checkout

```sh
uv run supermarket-ops call billing.create_bill --json '{}'
```

Use the returned bill ID below; do not assume it is 1 on an existing store.

```sh
uv run supermarket-ops call billing.add_line_item --json \
  '{"bill_id":1,"sku":"DEMO-RICE","qty":2}'
uv run supermarket-ops call billing.get_bill_summary --json '{"bill_id":1}'
```

Show the owner the preview and payment mode. After approval:

```sh
uv run supermarket-ops call billing.finalize_bill --confirm --json \
  '{"bill_id":1,"idempotency_key":"owner-confirmed-sale-001","payment_mode":"cash"}'
uv run supermarket-ops call billing.get_finalized_bill --json '{"bill_id":1}'
uv run supermarket-ops call documents.generate_invoice_pdf --json '{"bill_id":1}'
```

Use a unique key for each separately approved checkout and reuse the same key and payload for retries. A key is not a password and does not authorize the sale. Valid modes are `cash`, `upi`, `card`, `bank_transfer`; a payment reference is optional metadata.

Drafts do not reserve stock. A successful preview is not a guarantee of availability at finalization. Competing checkouts are serialized and a shortage rolls back the entire checkout. Finalized drafts cannot be edited through the public API.

MRP is tax-inclusive; CGST and SGST are extracted rather than added. Price calculations use decimal half-up rounding, with the payable rounded to the nearest rupee. Keep `grand_total`, `payable` and `round_off` distinct in reconciliation.

## Customer credit

```sh
uv run supermarket-ops call khata.khata_credit --confirm --json \
  '{"customer":"Demonstration Customer","amount":100}'
uv run supermarket-ops call khata.khata_payment --confirm --json \
  '{"customer":"Demonstration Customer","amount":25}'
uv run supermarket-ops call khata.khata_balance --json \
  '{"customer":"Demonstration Customer"}'
```

These are standalone ledger entries, not a checkout on credit. The first credit opens a balance. Payments reject unknown customers and amounts exceeding the balance. Customer names are exact identifiers, not a full customer management system; resolve ambiguity before posting. A `bill_id` reference, where accepted, is informational and does not make two database writes atomic.

Stock receipts and khata changes lack idempotency keys. If a timeout leaves the outcome uncertain, inspect records before retrying. Do not automate blind retries.

## Reporting

```sh
uv run supermarket-ops call reports.daily_close --json '{"date":"2026-01-15"}'
uv run supermarket-ops call reports.purchase_summary --json \
  '{"start_date":"2026-01-01","end_date":"2026-01-31"}'
uv run supermarket-ops call reports.margin_report --json \
  '{"start_date":"2026-01-01","end_date":"2026-01-31"}'
uv run supermarket-ops call documents.generate_analysis_deck --json \
  '{"start_date":"2026-01-01","end_date":"2026-01-31"}'
```

Example dates are literal examples. Select the owner's actual reporting period in the configured business timezone. An empty period is reported as empty, not filled with demonstration transactions.
