# Reporting and generated documents

## Contract and dates

`daily_close(date)`, `purchase_summary(start_date, end_date)`,
`margin_report(start_date, end_date)` and `generate_analysis_deck(start_date,
end_date)` accept strict `YYYY-MM-DD` dates. Invalid calendar dates, noncanonical
strings, and reversed ranges raise `ValueError` before output paths are created.
The terminal date `9999-12-31` is rejected because filtering needs the following
midnight.

Dates are inclusive **business dates**, using the `timezone` preference (an IANA
zone, default `Asia/Kolkata`). Invalid timezone preferences fail explicitly.
Local midnight and midnight after the last day are converted separately to UTC,
so daylight-saving transitions are handled. SQLite compares normalized timestamp
values using a half-open interval `[start, next midnight)`, not UTC date strings.
Legacy naive timestamps are interpreted as UTC, matching existing stored data.
Changing the business timezone can change which date contains an old sale; prices
and shop identity are not recomputed.

`daily_close` retains its existing keys and adds `timezone`, `items` (all SKUs),
and `excluded_bill_count`. `sales_summary(start_date, end_date)` exposes period
aggregates plus `daily_totals`, including zero-sale days. Both daily and period
rankings sum **every snapshot line by SKU** before choosing the top five.
Identically named SKUs remain distinct; the latest encountered snapshot supplies
the display name. Ties are deterministic by SKU. Decks consume the period ranking,
never merge truncated daily top-five lists.

## Sales, purchases, and accounting limits

Only finalized `cash`, `upi`, `card`, and `bank_transfer` bills count as paid
sales. Unsupported legacy modes, including `credit`, are excluded and counted in
`excluded_bill_count`; the deck shows this count. New credit-sale finalization is
intentionally unsupported in this release. Standalone khata credits and repayments
remain a separate ledger and are **not sales** or sales payment-mode totals.

Sales revenue is recorded `grand_total` (tax-inclusive, before payment rounding).
It is not `payable`, cash received, or bank settlement. The tax figure is the
recorded component of those sales, not a certified GST liability calculation.

`purchase_summary` is restocking spend from recorded receipt quantity and unit
cost, not cost of goods sold. Its backwards-compatible `by_item` labels are current
catalog names, so a rename changes labels, not receipt cost.

`margin_report` retains `revenue`, `cost`, and `margin`, with an explicit `basis`:

> Snapshot gross spread: tax-inclusive sales minus recorded unit acquisition
> cost; not accounting net profit.

Cost is `sum(snapshot line qty * snapshot line cost_price)` for the included
sales. It is not period restocking spend, current catalog cost, FIFO, or weighted
average valuation. Missing, nonnumeric, nonfinite, or negative snapshot costs
raise `ValueError` rather than substituting current prices or zero. Empty periods
return zero revenue/cost/spread. Legacy sales remain usable in sales reports and
invoices without cost snapshots, but cannot support this margin calculation.

The release retains SQLite REAL money fields and existing rounding. This is not
a complete accounting ERP: there is no matched tax-exclusive COGS, inventory
valuation method, input-tax-credit reconciliation, operating expense ledger,
returns accounting, or certified net-profit calculation. Do not label the spread
as net profit or use it as an audited financial statement.

## PDF invoices

`generate_invoice_pdf(bill_id)` reads a finalized snapshot, including `shop_name`
and `shop_gstin`. It never fills missing historical identity from today's shop
preferences. Legacy missing names are explicitly marked. Missing GSTIN produces
**“GSTIN unavailable: not a compliant tax invoice.”** Even when a GSTIN is present,
the document is a sales record, not a certification of GST compliance (buyer
identity, place-of-supply and other statutory requirements are outside this API).

All untrusted text passed to ReportLab paragraphs is XML-escaped. A4 pages use
explicit margins, fixed column widths, wrapped cells, repeating headers, and
splittable long rows. Invoice timestamps display the configured business timezone.
The default PDF font is Helvetica and amounts use `Rs.` for glyph portability;
full Indic-script/Unicode font coverage and shaping are not provided in this
release. Deployments needing those scripts must add an appropriate embedded font
and validate its shaping rather than assume base-14 fonts cover it.

## Fresh presentations and portable output

Generated files are placed under **runtime** `abi_store.db.ROOT / 'generated'`:
`invoices/` and `presentations/`. The data-root configuration belongs to `db.py`
(`SUPERMARKET_DATA_DIR`, default `~/.local/share/supermarket-ops-bot`). Importing
`documents` creates no directories. Every call uses a UUID filename, so repeated
or concurrent generations do not overwrite each other. Files are retained until
the operator removes them; there is no automatic retention policy.

Each PPTX is built fresh from queried data, with a restrained ivory/graphite/teal
16:9 design, overview metrics, payment-mode totals, sales trend, full-period top
SKUs, and a current-stock reorder review. Empty periods say “No finalized paid
sales” instead of inventing a chart. Native charts embed their own workbooks in
the unique deck: there are no shared chart PNG filenames or template workbooks
containing stale data. Long trends use at most 31 contiguous time buckets and sum
all days, not sampled points. Long chart labels are shortened only for display.
Stock pages contain at most eight entries each and are explicitly labeled
**current at generation, not historical period-end stock**. Stock is queried
separately from sales and is not an atomic historical inventory snapshot.

### Layout patterns retained from the read-only analytics scripts

Reviewed `create_fresh_store_performance_ppt.py` and `refined_sales_ppt.py` in the
existing generated-scripts directory without executing either script. Retained:

- fresh `Presentation()` construction and widescreen geometry;
- a restrained graphite/ivory/teal palette and consistent title/subtitle/footer;
- three clearly labeled overview metric cards;
- concise native charts with embedded real-data series;
- explicit wrapped text and fixed layout bounds rather than free-form placement.

Not retained: store-specific branding, hardcoded machine paths, live data,
static totals, shared chart filenames, dense transaction-list slides, emoji,
or unqualified profit/historical-stock claims. Public generators do not import,
execute, or depend on those scripts.

## Verification workflow

Run `.venv/bin/python -m pytest tests/test_reports_documents.py -q` in an isolated
checkout. Tests create temporary SQLite databases; they do not open a live store.
Coverage includes strict date rejection, UTC/local midnight crossing, DST,
full-period ranking, payment exclusions, khata repayment separation, snapshot
cost and missing-cost refusal, runtime paths, import side effects, PDF text/A4
geometry, PPTX content/ZIP integrity/native chart values, empty periods, unique
generations, and long-period chart aggregation.

For visual review, render a generated PDF using PDFium or Poppler and inspect
long escaped names and numeric columns. For slides, use LibreOffice/PowerPoint
rendering when available; ZIP/content/chart-value checks validate structure and
data but are not a substitute for a slide-render review. LibreOffice and Poppler
were unavailable in the implementation environment; the invoice was rendered
with optional `pypdfium2` and visually checked. `pypdfium2` is a review-only tool,
not a runtime dependency of the generators.
