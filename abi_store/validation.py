"""Boundary validation and Decimal rounding; SQLite storage remains legacy REAL."""
import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a nonblank string')
    return value


def number(value, field, *, positive=False, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f'{field} must be a finite number')
    try:
        d = Decimal(str(value))
        valid = d.is_finite() and math.isfinite(float(d))
        if not valid or d < 0 or (positive and d <= 0) or (maximum is not None and d > maximum):
            raise ValueError(f'{field} is outside the allowed range')
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError(f'{field} must be a finite number') from exc
    return d


def money(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
