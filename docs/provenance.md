# Provenance and publication boundary

Supermarket Ops Bot originates in AHILESH's owner-operated supermarket project. Abi is the name used for the Hermes assistant helping operate and develop that project.

## Included and generalized

- The `abi_store` inventory, billing, khata, preferences, database, reporting and document modules.
- Operational rules from the original supermarket skill and shop-specific personality notes, rewritten into portable operational skills.
- SQLite transaction-development guidance, including explicit distinctions between design targets and implemented behavior.
- Reusable reporting and presentation patterns from one-off analysis scripts, consolidated into the supported report generator rather than publishing dated, shop-bound scripts as entry points.
- New portability settings, JSON CLI, skill installer, fictional demonstration and automated regression tests for this public distribution.

The import namespace `abi_store` is retained to keep continuity with the original tools. Display names and storage locations are configurable.

## Intentionally excluded

Live stock and khata databases; customer records; invoices and performance decks; generated chart files; one-time stock-update and purchase-entry scripts containing operational inputs; authentication files; Hermes conversation history, global memories and provider settings; virtual environments and caches.

Generic third-party Hermes skills are not copied wholesale. PDF, chart and PowerPoint functionality uses the declared Python dependencies. Hermes itself remains a separate upstream dependency with its own license and documentation.

The public package does not modify the original deployed shop. Existing private-store data migration is a separate operation requiring a backup and review, not an install side effect.
