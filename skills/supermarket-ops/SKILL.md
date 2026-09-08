---
name: supermarket-ops
description: "Use when managing supermarket stock, bills or credit."
version: 0.1.0
author: AHILESH (ahilesh-s), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [supermarket, inventory, billing, gst, khata]
    related_skills: [supermarket-analytics]
---
# Supermarket operations

Operate the owner's local store through deterministic Python tools. The database is the source of truth; conversation memory is not a stock ledger.

## When to use

Use for receiving goods, product registration, stock questions, multi-turn bills, invoice retrieval, customer credit and shop settings. Do not use for unrelated personal purchases or unsupported returns and tax filings.

## Prerequisites

Install this repository and run its skill installer. Read this skill's `runtime.json` with `read_file`; it binds a Python interpreter, project directory and data directory. If missing, follow the repository setup guide rather than guessing a store path. Never change the binding to reach another shop without owner approval.

## How to run

Use `terminal` with the bound Python interpreter and this skill's `scripts/run.py`. Run `status` first; if databases are missing, ask for the shop name and initialize with `init --shop-name "Name"`. The runner supplies the correct environment and working directory.

Canonical shape (substitute paths from `runtime.json`, properly quote shell arguments):

    terminal(command='<python> <skill-directory>/scripts/run.py call inventory.resolve_product --json <JSON-object>')

Prefer stdin JSON or safe shell quoting. Never interpolate raw customer text into Python, SQL or shell commands. `operations` lists exact function arguments. Results are JSON; quote tool totals, do not recalculate them.

## Procedure

1. Resolve the product with `inventory.resolve_product(query)`. Multiple candidates require owner selection; never pick a fuzzy candidate without checking name, unit and packaging. Ask for missing catalog facts when registering a product.
2. For new products use `inventory.add_product`; for restocking use `inventory.receive_stock`. Show SKU, units, quantity and any changed cost/MRP before asking approval. Default reorder level is 10 in each product's own unit. Never assume a 20% cost discount; actual cost must be supplied and recorded.
3. Build a bill with `billing.create_bill`, `add_line_item`, `edit_line_item` and `remove_line_item`. Persist the returned bill ID in the conversation; drafts live in SQLite across sessions. Stock is not reserved by a draft.
4. Preview with `billing.get_bill_summary`. Obtain explicit owner approval of bill ID, items, payable and payment mode. Then use `billing.finalize_bill` with one stable, nonempty idempotency key for that confirmed request. A retry must use the same key and arguments. Modes: cash, upi, card, bank_transfer. Do not use credit or khata as a payment mode.
5. Verify the finalized snapshot and requested remaining stock. Generate a PDF through `documents.generate_invoice_pdf(bill_id)` only after finalization. The generator returns a real path; do not invent an attachment or invoice URL.
6. For standalone khata use `khata.khata_credit`, `khata.khata_payment`, `khata.khata_balance`. Resolve the exact customer spelling and confirm the amount before writing. Refuse unknown-customer payments or overpayments. If a write's outcome is uncertain, inspect the ledger before any retry; these calls are NOT idempotent.
7. Close the day or build reports with the supermarket-analytics skill.

Pass `--confirm` only after the owner approves stock, credit, finalization or preference writes. This flag is an accidental-write guard, not authentication. Keep Hermes' own approval and sender controls enabled. Never bypass the CLI through direct SQL to evade confirmation.

## Business rules

- Prices, HSN, GST, cost and unit are catalog facts. Billing takes only SKU and quantity, never arbitrary line prices or tax overrides.
- Supported units: kg, g, litre, ml, packet, dozen, piece. Do not silently convert units or mix loose and packaged variants.
- MRP includes GST. Never sell below cost. Tax calculations and rounding belong in Python.
- Finalized invoices use snapshots, not today's prices or shop details.
- A payment reference is a note, not proof of funds. This project does not connect to banks or payment providers.
- Customer credit is a separate ledger, not an atomic credit-sale checkout. Do not finalize a paid bill for unpaid goods.
- Store owner preferences via `preferences.set_preference`, not global Hermes memory. `shop_name`, `shop_gstin`, and `timezone` are relevant keys.

## Pitfalls

No returns, expiry/batch tracking, purchase orders, multi-store transfers or automatic GST filing are implemented. Invoice PDFs are not a guarantee of legal compliance. SQLite money storage is REAL; this is a small-store starter, not a certified accounting system. Do not claim it manages every possible business process.

## Verification and response style

Read back the exact bill, stock or balance after a write. For uncertain non-idempotent results, reconcile instead of repeating. Report the IDs, payable, stock left or balance concisely. No emojis, hype, fabricated records or process narration. Keep credentials, customer data and generated files private.
