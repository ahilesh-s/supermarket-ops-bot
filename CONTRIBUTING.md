# Contributing

Open an issue describing the business rule before adding a new workflow. Include the expected state changes, failure cases and whether the operation must be safe to retry.

## Local checks

```sh
uv sync --extra dev --locked
uv run pytest -q
git diff --check
```

Use temporary databases and fictional customer/product fixtures. Never attach real invoices, ledgers, credentials or database dumps to an issue or pull request.

## Change requirements

- Add a failing behavioral test before fixing a defect or extending a workflow.
- Keep stock deduction, idempotency and ledger changes within their required transaction boundary.
- Test contention and rollback for new multi-row writes.
- Preserve finalized transaction history; changes to pricing or preferences must not rewrite earlier bills.
- Document migrations, backups and compatibility when changing the schema.
- Update CLI arguments, skills and examples together when changing an interface.
- Keep prose specific. Describe supported behavior and limits; avoid claims such as “perfect”, “enterprise-ready” or “manages everything”. No decorative emojis.

Keep pull requests focused. Do not bundle unrelated dependency updates or formatting rewrites with accounting changes.
