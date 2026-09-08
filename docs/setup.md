# Setup and data ownership

## Installation

Install [Hermes Agent](https://hermes-agent.nousresearch.com/docs/) separately. This repository requires its terminal tool; it does not replace the Hermes runtime or choose a language model.

Clone the repository and run `uv sync --extra dev`. The lockfile records resolved dependencies; subsequent installations and CI use `uv sync --extra dev --locked`.

Python 3.11+ is required. The documented shell examples use Linux/WSL. For Windows without WSL, use the same Python scripts and set environment variables using your shell's syntax. Linux CI is not a claim of Windows desktop validation.

## Choose the store directory

The engine reads `SUPERMARKET_DATA_DIR` once when imported. If unset it defaults to `~/.local/share/supermarket-ops-bot`. Use a different directory for each independent shop and each demo.

```sh
export SUPERMARKET_DATA_DIR="$HOME/.local/share/my-supermarket"
uv run supermarket-ops init --shop-name "My Supermarket" --timezone Asia/Kolkata
uv run supermarket-ops status
```

`init` creates empty schemas and preserves existing rows. Explicit name/timezone arguments update those preferences; omitted arguments preserve existing values. Do not point an installation at a private legacy shop until you have reviewed compatibility and backed it up.

The data root contains:

```text
database/stock.db
database/khata.db
generated/invoices/
generated/presentations/
generated/charts/
```

## Install the Hermes skills

```sh
uv run python scripts/install_skills.py --data-dir "$SUPERMARKET_DATA_DIR"
```

The target is `$HERMES_HOME/skills`, falling back to `~/.hermes/skills`. An explicit `--hermes-home` selects a profile without changing the active global configuration. The installer refuses to overwrite any of its target skill directories. Review and move an existing version to a backup outside the skills directory before installing an update.

Each installed skill has a local `runtime.json` containing the Python interpreter, project directory and selected data directory. It contains no credentials. The bound runner overrides an inherited `SUPERMARKET_DATA_DIR` to avoid accidentally operating another store. Moving the clone or virtual environment invalidates the binding; reinstall it deliberately.

Start a new Hermes conversation so the skill catalog reloads. Ask it to load `supermarket-ops` and run `status` through the skill runner. A successful JSON status with both databases present verifies the local store connection. The installer itself does not test a live language-model conversation or messaging channel.

Official reference: [Hermes Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills).

## Configure shop facts

Set the actual shop name, business timezone and GSTIN via the preferences operation. No valid GSTIN is invented or shipped in the demo. Each product needs a SKU, name, unit, loose/packaged classification, HSN, GST rate, acquisition cost and GST-inclusive retail MRP. Confirm those facts with the owner.

```sh
uv run supermarket-ops call preferences.set_preference --confirm \
  --json '{"key":"shop_name","value":"My Supermarket"}'
```

For real operations, obtain approval before passing `--confirm`. Finalized bills snapshot shop identity and product facts, so correcting preferences later does not rewrite old invoices.

## Messaging

Telegram or another gateway channel is configured in Hermes, not this package. Use official Hermes messaging setup, keep sender allowlists enabled and test with a trusted owner. Do not expose the Python operations directly to arbitrary users.

No scheduled jobs or bot tokens are installed. Add daily-close reminders only after deciding the shop's timezone, closing time and delivery destination.

## Backup and recovery

Restrict access to the data directory. Pause writes, then use SQLite's backup API for each database into a dated private backup directory. Keep both databases and configuration together. Do not copy only a live `.db` file while WAL files may contain uncheckpointed writes. Validate backups with `PRAGMA integrity_check` and test restoration into a separate directory before relying on them.

`stock.db` and `khata.db` are not one distributed transaction. The release deliberately does not support an atomic credit checkout across them.

## Uninstall

Remove only the skills installed by this project from the chosen Hermes home. Deleting the source checkout does not remove store data. Do not delete the data directory as part of ordinary software cleanup; archive it deliberately under your retention policy.
