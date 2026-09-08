# Supermarket Ops Bot

Inventory, billing, customer credit and reporting for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Built by AHILESH from the tools used to run Ahilesh Supermarket with Abi, an owner-operated Hermes assistant. This repository packages that work as a reusable Python engine and installable skills. Hermes handles the conversation; SQLite records the business state; Python performs the calculations.

No customer records, live shop databases, credentials or conversation history are included.

## What it does

| Area | Included |
| --- | --- |
| Inventory | Product catalog, loose and packaged goods, stock receipts, per-product reorder levels |
| Checkout | Persistent drafts, line edits, GST-inclusive pricing, atomic stock deduction, idempotent finalization |
| Customer credit | Standalone khata balances, credits and repayments; unknown-customer and overpayment checks |
| Documents | PDF receipts with tax breakdowns and snapshotted item details |
| Reporting | Business-day close, purchasing spend, recorded sales/cost spread, fresh PPTX charts |
| Hermes | Operational skills, a profile-aware installer and a bound JSON command runner |

The default low-stock threshold is 10 in each product's unit. Cost prices are recorded facts, not an assumed discount from MRP. INR and intra-state CGST/SGST are the current pricing model.

## Quick start

Requires Python 3.11 or newer and [uv](https://docs.astral.sh/uv/). Linux/WSL is tested locally; CI exercises Linux with Python 3.11 and 3.13. Hermes needs terminal-tool access. There is no separate model API key for this package; it uses the Hermes installation you already have.

```sh
git clone https://github.com/wolverinelogan-pc/supermarket-ops-bot.git
cd supermarket-ops-bot
uv sync --extra dev
```

Try the full workflow with explicitly fictional data in a new directory:

```sh
uv run python examples/demo.py --output ./demo-store
```

The command prints a finalized bill, day-close figures and paths to a real PDF and PPTX. It refuses to reuse an existing directory. Demo data stays local; use a separate directory for your real store.

### Connect Hermes to your store

```sh
export SUPERMARKET_DATA_DIR="$HOME/.local/share/my-supermarket"
uv run supermarket-ops init --shop-name "Your Supermarket" --timezone Asia/Kolkata
uv run python scripts/install_skills.py --data-dir "$SUPERMARKET_DATA_DIR"
```

The installer respects `HERMES_HOME`, or uses `~/.hermes`. To target a particular profile, pass its home explicitly with `--hermes-home /path/to/profile`. It copies only the bundled skills and a local runtime binding. It does not overwrite existing skills, modify provider settings, replace your personality, or touch other profiles.

Start a new Hermes session and ask:

> Use the supermarket-ops skill. Check the store connection, then help me register my first product. Ask for the catalog facts you need.

The installed runner remembers the selected interpreter and data directory, so later sessions do not depend on a shell export. Keep the clone and its virtual environment in place; reinstall the binding if you move them. Review [setup](docs/setup.md) before handling real transactions.

## Operating model

```text
Owner's request
    |
Hermes + supermarket skills
    |  resolve facts, clarify ambiguity, obtain approval
Bound JSON command runner
    |
Python operations
    +-- stock.db: catalog, receipts, drafts, finalized snapshots
    +-- khata.db: standalone customer credit ledger
    +-- generated/: invoices, charts, presentations
```

A draft does not reserve or deduct stock. Checkout rechecks inventory inside a write transaction. Repeating a confirmed finalization with the same key and payload returns the recorded result. Finalized reports use snapshots rather than today's prices.

Owner approval is part of the workflow, not a security boundary implemented by the model. The CLI's `--confirm` flag prevents accidental writes; it does not authenticate a sender. Keep Hermes' sender allowlists and approval controls enabled, especially on messaging platforms.

## Direct use

```sh
uv run supermarket-ops status
uv run supermarket-ops operations
uv run supermarket-ops call inventory.low_stock_items --json '{}'
uv run supermarket-ops call billing.create_bill --json '{}'
```

Calls return JSON on stdout. Validation failures return JSON on stderr with a nonzero exit code. See [operations](docs/operations.md) for a complete checkout example and [reporting](docs/reporting.md) for accounting definitions.

## Scope and limitations

This is an early small-store operations project, not a complete ERP or a certified accounting product.

- Paid checkout supports cash, UPI, card and bank transfer. It records an owner's payment declaration; it does not verify funds.
- Khata is a standalone ledger. Atomic credit-sale checkout across the two databases is not implemented and credit payment modes are rejected.
- Receiving stock and recording khata entries are not idempotent. Reconcile an uncertain result before retrying.
- Money and quantities use the inherited SQLite REAL schema. Price calculations use decimal rounding, but storage is not an integer-paise accounting ledger.
- Tax output covers the implemented intra-state GST split, not IGST, e-invoicing, return filing or a guarantee of statutory invoice compliance. Have invoice requirements reviewed before production use.
- Returns, refunds, expiry/batch tracking, supplier purchase orders, multi-store transfers and access roles are not implemented.
- Direct database access can bypass application rules. Backups, host permissions and operational supervision are still required.

These boundaries are intentional documentation, not features hidden behind a prompt. Contributions that add missing workflows should include transactional tests and explicit migration plans.

## Development

```sh
uv sync --extra dev --locked
uv run pytest -q
```

Tests use temporary stores and cover checkout, contention, snapshots, invalid inputs, reporting, artifacts, CLI and skill installation. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## Project layout

```text
abi_store/     Python engine and JSON CLI
skills/        Hermes operations, analytics and SQLite-development skills
scripts/       Profile-aware skill installer
examples/      Isolated fictional demonstration
tests/         Behavioral and integration tests
docs/          Setup, operations, reporting and provenance
```

## Credits and license

Created and maintained by [AHILESH](https://github.com/wolverinelogan-pc), with Abi/Hermes as a development collaborator. Hermes Agent is built by Nous Research and is a separate project; this repository is not an official Nous Research product.

MIT licensed. See [LICENSE](LICENSE) and [provenance](docs/provenance.md).
