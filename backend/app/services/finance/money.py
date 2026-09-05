"""Decimal helpers. Money never touches float anywhere in this codebase."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

CENTS = Decimal("0.01")
RATE = Decimal("0.0001")
ZERO = Decimal("0.00")


def D(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value) -> Decimal:
    return D(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def rate(value) -> Decimal:
    return D(value).quantize(RATE, rounding=ROUND_HALF_UP)


def total(values: Iterable) -> Decimal:
    return money(sum((D(v) for v in values), ZERO))


def safe_div(numerator, denominator, default=ZERO) -> Decimal:
    n, d = D(numerator), D(denominator)
    if d == 0:
        return D(default)
    return n / d


def pct(numerator, denominator, default=ZERO) -> Decimal:
    """Percentage 0-100 (not a 0-1 fraction), rounded to 2dp."""
    if D(denominator) == 0:
        return D(default)
    return money(safe_div(numerator, denominator) * 100)


def clamp(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    return max(low, min(high, value))


def as_float(value) -> float:
    """Only for JSON serialisation at the API boundary."""
    return float(D(value))
