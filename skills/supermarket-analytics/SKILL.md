---
name: supermarket-analytics
description: "Use when closing store days or reporting performance."
version: 0.1.0
author: AHILESH (ahilesh-s), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [supermarket, reporting, analytics, invoices]
    related_skills: [supermarket-ops]
---
# Store close and performance reporting

Produce data-led reports from finalized transactions. Report what the records support, including empty periods and missing information.

## When to use

Use for day close, restocking spend, margin analysis and performance presentations. Do not use to file tax returns or to present purchasing cash outflow as cost of goods sold.

## Prerequisites and how to run

Read this skill's `runtime.json` with `read_file`. Use `terminal` to call its `scripts/run.py` with the configured Python. The runner binds the store directory and works from any current directory. Do not use a different profile's store.

    terminal(command='<python> <skill-directory>/scripts/run.py call reports.daily_close --json <JSON-object>')

Pass JSON with `date`, or `start_date` and `end_date` as required. `operations` reports signatures. Dates must be YYYY-MM-DD; interpret the owner’s requested period in the configured `timezone` (default Asia/Kolkata). Obtain current dates through a tool, never guess.

## Procedure

1. Resolve the exact period. Use `reports.daily_close(date)` for one day, `purchase_summary(start_date,end_date)` for receipt spend, and `margin_report(start_date,end_date)` for the recorded sales/cost spread.
2. Keep finalized sales, rounded customer payments, tax, restocking purchases and standalone khata repayments distinct. The reported margin is not net accounting profit. Do not use a default margin assumption to fabricate cost history.
3. Generate a new deck with `documents.generate_analysis_deck(start_date,end_date)`. It reads current records and generates fresh charts; never reuse an old deck and change its title or dates.
4. Inspect the returned PPTX structure/content and reconcile its totals against report outputs. Use `read_file` for content. A real PowerPoint artifact is required, not a markdown slide outline.
5. Label stock-health information as current stock, not period-end inventory. Zero sales means no finalized transactions were found, not a failed business or proof of lost sales.
6. Share only the requested artifact and concise totals. Respect the active platform: a local path is not automatically an attachment.

## Pitfalls

Historical cost must come from bill snapshots. Missing legacy cost cannot be reconstructed from today's catalog. A period's top items must consider every sold SKU, not just each day's top five. Mixed units must not be added into a single quantity KPI. Low-stock alerts are per-product units and default to 10.

## Verification

Check start/end dates, timezone, bill count, sales total and artifact existence. For an empty period produce an explicitly empty report, not sample data. Keep professional typography, neutral language and a restrained palette; no emojis or unsupported recommendations.
