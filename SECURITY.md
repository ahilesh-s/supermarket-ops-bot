# Security and operational safety

This project is intended for a trusted owner-operated Hermes installation. It is not an authenticated multi-tenant service.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting on this repository when available. Do not publish an exploit containing customer data, tokens or a live shop database. If private reporting is unavailable, open an issue asking for a private contact without disclosing sensitive details.

## Deployment boundaries

- Limit Hermes messaging access to trusted senders. Keep terminal approval controls enabled.
- A model-supplied `--confirm` flag is not proof of owner authorization. Untrusted-user adapters need a separate authenticated approval boundary.
- The data directory contains customer balances and transaction history. Restrict filesystem permissions and encrypt backups where appropriate.
- Do not commit `.env`, runtime bindings, databases, generated invoices or reports.
- Calls outside finalization may not be idempotent. A timeout is an unknown result, not proof of rollback.
- SQLite files should stay on local storage, not an unverified network share. Pause writes when taking a coordinated backup of both databases; use SQLite's backup API rather than copying a live WAL database file alone.
- Python-level checks do not protect against a user with direct SQL or filesystem access.
- Review tax and invoice requirements with a qualified local adviser before relying on generated documents.

There is no telemetry, hosted backend, payment-provider integration or model credential storage in the store engine. Installing skills does not change Hermes' provider authentication.
