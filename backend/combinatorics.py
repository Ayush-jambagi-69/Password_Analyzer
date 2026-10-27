"""Character pools (set union), exact search space R^L, and policy-constrained counting."""
from dataclasses import dataclass, field
from typing import List, Set

from entropy import group_thousands, sci_from_digits

MAX_LENGTH, MAX_POOL = 1024, 256
LOWER = set("abcdefghijklmnopqrstuvwxyz")
UPPER = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
DIGITS = set("0123456789")
DEFAULT_SYMBOLS = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
REQUIREMENTS = ("lower", "upper", "digit", "symbol")


@dataclass
class Config:
    length: int = 8
    lower: bool = True
    upper: bool = False
    digits: bool = False
    symbols: bool = False
    symbol_set: str = ""            # empty => default 32 ASCII symbols
    use_custom: bool = False
    custom_pool: str = ""
    required: List[str] = field(default_factory=list)


@dataclass
class Pool:
    chars: Set[str]
    lower_n: int
    upper_n: int
    digit_n: int
    symbol_n: int
    naive_sum: int                  # sum of set sizes before removing overlaps

    @property
    def size(self) -> int:
        return len(self.chars)


def _symbols_of(c: Config) -> str:
    return c.symbol_set or DEFAULT_SYMBOLS


def _printable(s: str) -> bool:
    return all(32 <= ord(ch) <= 126 for ch in s)


def requirement_set(name: str, c: Config, chars: Set[str]) -> Set[str]:
    """Pool characters that satisfy the requirement 'at least one <name>'."""
    if name == "lower":
        return chars & LOWER
    if name == "upper":
        return chars & UPPER
    if name == "digit":
        return chars & DIGITS
    if c.use_custom:                                  # custom pool: symbol = non-alphanumeric
        return chars - LOWER - UPPER - DIGITS
    return chars & set(_symbols_of(c))


def build_pool(c: Config) -> Pool:
    chars: Set[str] = set()
    naive = 0
    if c.use_custom:
        chars = set(c.custom_pool)
        naive = len(c.custom_pool)
    else:
        for on, s in ((c.lower, LOWER), (c.upper, UPPER), (c.digits, DIGITS), (c.symbols, set(_symbols_of(c)))):
            if on:
                chars |= s
                naive += len(s)
    return Pool(chars, len(chars & LOWER), len(chars & UPPER), len(chars & DIGITS),
                len(requirement_set("symbol", c, chars)), naive)


def validate_config(c: Config) -> List[str]:
    """Returns a list of error messages; empty means valid."""
    e: List[str] = []
    if c.length < 1:
        e.append("Password length must be at least 1.")
    if c.length > MAX_LENGTH:
        e.append(f"Password length must be at most {MAX_LENGTH}.")
    if c.use_custom:
        if not c.custom_pool:
            e.append("Custom pool is empty: at least one character is required.")
        if not _printable(c.custom_pool):
            e.append("Custom pool contains unsupported characters (printable ASCII only).")
    else:
        if not _printable(c.symbol_set):
            e.append("Symbol set contains unsupported characters (printable ASCII only).")
        if not (c.lower or c.upper or c.digits or c.symbols):
            e.append("No character category is selected: the pool has 0 characters.")
    for r in c.required:
        if r not in REQUIREMENTS:
            e.append(f"Unknown requirement: {r}")
    if e:
        return e
    p = build_pool(c)
    if p.size == 0:
        e.append("The character pool is empty (0 characters).")
    if p.size > MAX_POOL:
        e.append("Pool is too large.")
    if e:
        return e
    for r in c.required:
        if not requirement_set(r, c, p.chars):
            e.append(f"Impossible requirement: '{r}' is required but the pool contains no such character.")
    return e


def search_space(R: int, L: int) -> int:
    """N = R^L as an exact Python integer."""
    return max(R, 0) ** max(L, 0)


def constrained_count(c: Config, p: Pool) -> dict:
    """Inclusion-exclusion: N_valid = sum over subsets S of (-1)^|S| (R - |union of sets in S|)^L.
    Overlapping sets are handled by taking the set union, so nothing is double-counted."""
    req = sorted(set(c.required))
    k, R = len(req), p.size
    sets = [requirement_set(r, c, p.chars) for r in req]
    total, terms = 0, []
    for mask in range(1 << k):
        union: Set[str] = set()
        names = []
        for i in range(k):
            if mask >> i & 1:
                union |= sets[i]
                names.append(req[i])
        sign = -1 if len(names) % 2 else 1
        term = search_space(R - len(union), c.length)
        ts = str(term)
        label = ("violates all of: " + "+".join(names)) if names else "none (all strings)"
        terms.append({"subset": label, "unionSize": len(union), "sign": sign,
                      "value": group_thousands(ts) if len(ts) <= 15 else sci_from_digits(ts)})
        total += sign * term
    return {"count": total, "terms": terms, "feasible": total > 0}
