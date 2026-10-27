"""Entropy and number-formatting helpers. Python ints are arbitrary precision, so nothing overflows."""
import math
import sys

if hasattr(sys, "set_int_max_str_digits"):   # Python 3.11+ limits int->str length by default
    sys.set_int_max_str_digits(0)


def entropy_bits(length: int, pool_size: int) -> float:
    """H = L * log2(R); 0 for an empty/one-character pool."""
    if pool_size <= 1 or length <= 0:
        return 0.0
    return length * math.log2(pool_size)


def log10_space(length: int, pool_size: int) -> float:
    """log10(N) = L * log10(R), computed without forming N."""
    if pool_size <= 0 or length <= 0:
        return 0.0
    return length * math.log10(pool_size)


def sci_from_log10(l10: float) -> str:
    e = math.floor(l10)
    m = 10 ** (l10 - e)
    if m >= 9.995:
        m, e = 1.0, e + 1
    return f"{m:.2f}e{int(e):+d}"


def sci_from_digits(digits: str) -> str:
    """Exact digit string -> 'd.dde+X' (mantissa from the first three digits, truncated)."""
    if len(digits) == 1:
        return digits + ".00e+0"
    m = int(digits[0]) + int(digits[1]) / 10 + (int(digits[2]) / 100 if len(digits) > 2 else 0)
    return f"{m:.2f}e+{len(digits) - 1}"


def group_thousands(digits: str) -> str:
    return f"{int(digits):,}"
