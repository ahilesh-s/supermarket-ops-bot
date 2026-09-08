---
name: sqlite-tool-transactions
description: "Use when building transactional SQLite business tools."
version: 0.1.0
author: AHILESH (ahilesh-s), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [sqlite, transactions, testing]
    related_skills: []
---
# Transactional store-tool development

## When to use

Use when extending or reviewing the Python store engine, not for ordinary sales. Treat these as development requirements; they do not assert that every target guarantee already exists in the current release.

## Procedure

1. Use `read_file` to inspect schema and write paths, then reproduce the bug in an isolated temporary database using `terminal`. Never test changes against a live shop.
2. Use integer minor money units and scaled quantities for new ledger designs; convert from Decimal strings and reject bool, nonfinite values and unsupported precision. Existing REAL schemas need explicit migrations, not a silent reinterpretation.
3. Use short BEGIN IMMEDIATE transactions for owned connections. For caller-owned transactions use unique SAVEPOINTs and never commit or roll back the caller's outer transaction.
4. Aggregate quantities per SKU and conditionally update stock only where available quantity meets the request. Every affected SKU and ledger row must roll back together on a shortage.
5. Check idempotency inside the same transaction as side effects; bind keys to the operation and input payload. Replays must return the persisted result, not run a second write.
6. Snapshot product costs, taxes and shop preferences at finalization. Protect finalized records against later edits. For future untrusted-user adapters, bind pending confirmations to authenticated owners, expiring requests and fingerprints; model-supplied flags are not authorization.
7. Separate credit sales from paid sales and repayments from revenue. Persist UTC timestamps and filter dates in an explicit business timezone.

## Pitfalls

WAL plus two separate SQLite files does not provide an atomic cross-file credit sale. Do not present a two-call paid checkout plus khata credit as one transaction. Direct filesystem/SQL access can bypass application rules; permissions and backups remain the deployer's responsibility.

## Verification

Use `terminal` to run tests for concurrent competing checkout, full multi-SKU rollback, duplicate SKU aggregation, idempotency key conflicts, immutable-history behavior, tax HALF_UP rounding and local-midnight boundaries. New confirmation or outer-transaction adapters must add replay/staleness and outer rollback tests before being described as supported.
