# Project instructions

This repository is the reusable source, not a live shop. Do not initialize, inspect or modify another user's data directory while developing.

Use `uv sync --extra dev --locked` and `uv run pytest -q`. Run behavior changes against temporary SQLite databases. Never use real customer fixtures or credentials.

Read the relevant module and skill before editing. Keep API signatures, JSON CLI, tests and operational instructions consistent. Use explicit transactions for stock and ledger writes. Preserve finalized snapshots. Do not claim that a confirmation flag provides authentication or that two separate database calls are atomic.

Documentation should be concise, technical and honest about limitations. No decorative emojis, promotional superlatives or invented benchmarks. Credit AHILESH as the project author and Hermes/Abi as a development collaborator.
