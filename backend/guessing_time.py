"""Theoretical exhaustive-search times. Worst case T = N/G; average T ~ N/(2G)."""
import math

from entropy import sci_from_log10

YEAR = 365.25 * 86400


def valid_rate(g) -> bool:
    return isinstance(g, (int, float)) and not isinstance(g, bool) and math.isfinite(g) and 0 < g <= 1e30


def _humanize(l10s: float) -> str:
    if l10s < -3:
        return "under a millisecond"
    s = 10 ** min(l10s, 300)
    if s < 1:
        return f"{s * 1000:.1f} ms"
    if s < 60:
        return f"{s:.1f} seconds"
    if s < 3600:
        return f"{s / 60:.1f} minutes"
    if s < 86400:
        return f"{s / 3600:.1f} hours"
    if s < YEAR:
        return f"{s / 86400:.1f} days"
    l10y = l10s - math.log10(YEAR)
    if l10y < 6:
        return f"{s / YEAR:.0f} years"
    r = sci_from_log10(l10y) + " years"
    if l10y > 10.14:
        r += " (longer than the age of the universe, ~1.4e+10 years)"
    return r


def estimate_time(log10_n: float, guesses_per_second: float, average: bool) -> dict:
    """Works from log10(N), so huge N never overflows."""
    l = log10_n - math.log10(guesses_per_second) - (math.log10(2) if average else 0.0)
    return {"log10Seconds": l, "sci": sci_from_log10(l) + " s", "human": _humanize(l)}
