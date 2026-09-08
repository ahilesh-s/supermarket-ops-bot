"""Business-date aggregates from immutable finalized-bill snapshots.

Sales prices and acquisition costs never come from today's product catalog.
"""

from datetime import date as Date, datetime, time, timedelta, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .db import get_connection
from .preferences import get_preference


def validate_date_range(start_date: str, end_date: str):
    """Strict inclusive business dates; validation precedes DB/path access."""
    dates = []
    for value in (start_date, end_date):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("Dates must be ISO YYYY-MM-DD")
        dates.append(Date.fromisoformat(value))
    if dates[0] > dates[1]:
        raise ValueError("start_date must be on or before end_date")
    if dates[1] == Date.max:
        raise ValueError("end_date must precede 9999-12-31")
    return tuple(dates)


def business_timezone():
    try:
        return ZoneInfo(get_preference("timezone", "Asia/Kolkata"))
    except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
        raise ValueError("Invalid business timezone preference") from exc


def _utc_bounds(start_date, end_date):
    start, end = validate_date_range(start_date, end_date)
    zone = business_timezone()
    return (datetime.combine(start, time.min, zone).astimezone(timezone.utc).isoformat(),
            datetime.combine(end + timedelta(days=1), time.min, zone).astimezone(timezone.utc).isoformat())



PAID_MODES = {"cash", "upi", "card", "bank_transfer"}


def _period_bills(start_date, end_date):
    import json
    start, end = _utc_bounds(start_date, end_date)
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM bills WHERE status='finalized' "
            "AND julianday(finalized_at) >= julianday(?) "
            "AND julianday(finalized_at) < julianday(?) ORDER BY finalized_at, id",
            (start, end),
        ).fetchall()
    finally:
        conn.close()
    bills = []
    excluded = 0
    for row in rows:
        if row["payment_mode"] not in PAID_MODES:
            excluded += 1
            continue
        if not row["totals_json"]:
            raise ValueError(f"Bill {row['id']} has no finalized snapshot")
        bill = json.loads(row["totals_json"])
        bill.update(bill_id=row["id"], finalized_at=row["finalized_at"], payment_mode=row["payment_mode"])
        bills.append(bill)
    return bills, excluded


def _aggregate_sales(bills):
    items, modes = {}, {}
    for bill in bills:
        mode = bill["payment_mode"]
        modes[mode] = modes.get(mode, 0) + bill["grand_total"]
        for line in bill["lines"]:
            sku = line["sku"]
            item = items.setdefault(sku, dict(sku=sku, name=line["name"], qty=0, revenue=0))
            item["name"] = line["name"]  # most recent snapshot label, not live catalog
            item["qty"] += line["qty"]
            item["revenue"] += line["line_total"]
    ranked = sorted(items.values(), key=lambda i: (-i["revenue"], i["sku"]))
    for item in ranked:
        item["revenue"] = round(item["revenue"], 2)
    return dict(bill_count=len(bills), total_sales=round(sum(b["grand_total"] for b in bills), 2),
                total_tax=round(sum(b["total_tax"] for b in bills), 2),
                by_payment_mode={k: round(v, 2) for k, v in sorted(modes.items())},
                items=ranked, top_items=ranked[:5])


def sales_summary(start_date: str, end_date: str) -> dict:
    """Full-period SKU ranking and daily series from one snapshot read."""
    bills, excluded = _period_bills(start_date, end_date)
    start, end = validate_date_range(start_date, end_date)
    zone = business_timezone()
    grouped = {}
    for bill in bills:
        at = datetime.fromisoformat(bill["finalized_at"])
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        grouped.setdefault(at.astimezone(zone).date(), []).append(bill)
    days = []
    day = start
    while day <= end:
        days.append(dict(date=day.isoformat(), **_aggregate_sales(grouped.get(day, []))))
        day += timedelta(days=1)
    return dict(start_date=start_date, end_date=end_date, timezone=str(zone),
                excluded_bill_count=excluded, daily_totals=days, **_aggregate_sales(bills))


def daily_close(date: str) -> dict:
    result = sales_summary(date, date)
    return dict(date=date, **{k: v for k, v in result.items()
                            if k not in {"start_date", "end_date", "daily_totals"}})


def purchase_summary(start_date: str, end_date: str) -> dict:
    """Total spent restocking in a date range, from stock_receipts — the
    other half of the picture daily_close alone can't give you."""
    start, end = _utc_bounds(start_date, end_date)
    conn = get_connection()
    rows = conn.execute(
        "SELECT sr.sku, p.name, sr.qty, sr.cost_price FROM stock_receipts sr "
        "JOIN products p ON p.sku = sr.sku "
        "WHERE julianday(sr.received_at) >= julianday(?) AND julianday(sr.received_at) < julianday(?)",
        (start, end),
    ).fetchall()
    conn.close()

    total_cost = 0.0
    by_item: dict[str, float] = {}
    for r in rows:
        cost = r["qty"] * r["cost_price"]
        total_cost += cost
        by_item[r["name"]] = by_item.get(r["name"], 0) + cost

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_cost": round(total_cost, 2),
        "by_item": {k: round(v, 2) for k, v in by_item.items()},
    }


def margin_report(start_date: str, end_date: str) -> dict:
    """Snapshot gross spread, deliberately not accounting net profit."""
    import math
    bills, excluded = _period_bills(start_date, end_date)
    cost = 0.0
    for bill in bills:
        for line in bill["lines"]:
            value = line.get("cost_price")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"Bill {bill['bill_id']} lacks a valid snapshot cost_price; margin unavailable")
            cost += line["qty"] * value
    revenue = sum(b["grand_total"] for b in bills)
    return dict(start_date=start_date, end_date=end_date, revenue=round(revenue, 2),
                cost=round(cost, 2), margin=round(revenue - cost, 2),
                excluded_bill_count=excluded,
                basis="Snapshot gross spread: tax-inclusive sales minus recorded unit acquisition cost; not accounting net profit")
