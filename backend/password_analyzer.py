"""Turns a JSON configuration into a JSON report. Same request/response shapes as the original C++ API."""
import math
from typing import Any, Dict, List, Tuple

import combinatorics as cb
from entropy import entropy_bits, group_thousands, log10_space, sci_from_digits, sci_from_log10
from guessing_time import estimate_time, valid_rate


def error_json(errors: List[str]) -> dict:
    return {"ok": False, "errors": errors}


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def parse_config(j: Any) -> Tuple[cb.Config, List[str]]:
    c, errors = cb.Config(), []
    if not isinstance(j, dict):
        return c, ["Configuration must be a JSON object."]

    def get_bool(key: str, attr: str):
        if key in j:
            if isinstance(j[key], bool):
                setattr(c, attr, j[key])
            else:
                errors.append(f"'{key}' must be true or false.")

    def get_str(key: str, attr: str):
        if key in j:
            if isinstance(j[key], str):
                setattr(c, attr, j[key])
            else:
                errors.append(f"'{key}' must be a string.")

    if "length" in j:
        if not _is_int(j["length"]):
            errors.append("'length' must be an integer.")
        else:
            c.length = max(-1, min(j["length"], 100000))
    for key, attr in (("lower", "lower"), ("upper", "upper"), ("digits", "digits"), ("symbols", "symbols"), ("useCustom", "use_custom")):
        get_bool(key, attr)
    get_str("symbolSet", "symbol_set")
    get_str("customPool", "custom_pool")
    if "required" in j:
        if not isinstance(j["required"], list):
            errors.append("'required' must be an array.")
        else:
            for r in j["required"]:
                if isinstance(r, str):
                    c.required.append(r)
                else:
                    errors.append("'required' entries must be strings.")
    if not errors:
        errors.extend(cb.validate_config(c))
    return c, errors


def parse_rate(j: Any, errors: List[str]) -> float:
    if not isinstance(j, dict) or "guessesPerSecond" not in j:
        return 1e9
    g = j["guessesPerSecond"]
    if isinstance(g, bool) or not isinstance(g, (int, float)):
        errors.append("'guessesPerSecond' must be a number.")
        return 1e9
    if not valid_rate(g):
        errors.append("Guesses per second must be a positive number no larger than 1e30.")
    return float(g)


def _time_json(t: dict) -> dict:
    return {"seconds": t["sci"], "log10Seconds": t["log10Seconds"], "human": t["human"]}


def _report(c: cb.Config, rate: float) -> dict:
    p = cb.build_pool(c)
    R, L = p.size, c.length
    digits = str(cb.search_space(R, L))
    H, l10 = entropy_bits(L, R), log10_space(L, R)
    exact = group_thousands(digits) if len(digits) <= 40 else None
    sym_count = None
    if c.use_custom:
        pool_formula = "R = number of distinct characters in the pool"
    else:
        sym = c.symbol_set or cb.DEFAULT_SYMBOLS
        parts = [n for on, n in ((c.lower, 26), (c.upper, 26), (c.digits, 10), (c.symbols, len(set(sym)))) if on]
        pool_formula = "R = " + " + ".join(map(str, parts)) + (f" - {p.naive_sum - R} duplicate(s)" if p.naive_sum != R else "")
    j = {
        "ok": True, "length": L,
        "pool": {"size": R, "lower": p.lower_n, "upper": p.upper_n, "digits": p.digit_n, "symbols": p.symbol_n,
                 "overlapRemoved": p.naive_sum - R},
        "searchSpace": {"scientific": sci_from_digits(digits), "exact": exact, "digits": len(digits), "log10": l10},
        "entropyBits": H,
        "guessing": {"rate": rate, "worst": _time_json(estimate_time(l10, rate, False)),
                     "average": _time_json(estimate_time(l10, rate, True))},
        "steps": [
            f"{pool_formula} = {R}",
            f"N = R^L = {R}^{L} = {exact if exact else sci_from_digits(digits)}",
            f"H = log2(N) = L x log2(R) = {L} x {math.log2(R) if R > 0 else 0:.4f} = {H:.2f} bits",
            f"Worst case T = N / G; average T = N / (2G), with G = {sci_from_log10(math.log10(rate))} guesses/s",
        ],
        "assumptions": [
            "Every password is drawn uniformly at random from the pool, independently at each position.",
            "Results describe a random-generation model, not how predictable a human-chosen password is.",
            "Guessing times assume exhaustive search at a constant rate; real attacks use dictionaries, patterns and hashing costs.",
        ],
        "constrained": None,
    }
    if c.required:
        k = cb.constrained_count(c, p)
        count = k["count"]
        kd = str(count)
        l10v = math.log10(count)            # exact for arbitrarily large ints
        j["constrained"] = {
            "requirements": c.required,
            "count": group_thousands(kd) if len(kd) <= 40 else sci_from_digits(kd),
            "scientific": sci_from_digits(kd), "log10": l10v, "entropyBits": math.log2(count),
            "fractionOfAll": 10 ** (l10v - l10), "terms": k["terms"],
            "formula": "N_valid = sum over subsets S of the requirements of (-1)^|S| (R - |union of S|)^L",
            "assumption": "Each requirement means 'at least one character from that set'. Sets may overlap; each union is counted once.",
        }
    return j


def _impossible_by_length(c: cb.Config) -> List[str]:
    """Policies can be satisfiable by character sets yet impossible for a short length (count = 0)."""
    if not c.required:
        return []
    if cb.constrained_count(c, cb.build_pool(c))["count"] == 0:
        return [f"Impossible requirement: no string of length {c.length} can satisfy all of: {', '.join(sorted(set(c.required)))}."]
    return []


def analyze_config(req: Any) -> dict:
    c, err = parse_config(req)
    rate = parse_rate(req, err)
    if not err:
        err = _impossible_by_length(c)
    return error_json(err) if err else _report(c, rate)


def compare_configs(req: Any) -> dict:
    if not isinstance(req, dict) or "a" not in req or "b" not in req:
        return error_json(["Request needs configurations 'a' and 'b'."])
    a, ea = parse_config(req["a"])
    b, eb = parse_config(req["b"])
    err = [f"Configuration A: {x}" for x in ea] + [f"Configuration B: {x}" for x in eb]
    rate = parse_rate(req, err)
    if not err:
        err = [f"Configuration A: {x}" for x in _impossible_by_length(a)] + [f"Configuration B: {x}" for x in _impossible_by_length(b)]
    if err:
        return error_json(err)
    Ra, Rb = cb.build_pool(a).size, cb.build_pool(b).size
    # H_B - H_A = (L_B - L_A) log2 R_A  +  L_B (log2 R_B - log2 R_A)
    from_len = (b.length - a.length) * math.log2(Ra)
    from_pool = b.length * (math.log2(Rb) - math.log2(Ra))
    if abs(from_len) > abs(from_pool) + 1e-9:
        verdict = "Changing the length contributes more to the entropy difference."
    elif abs(from_pool) > abs(from_len) + 1e-9:
        verdict = "Changing the character pool contributes more to the entropy difference."
    else:
        verdict = "Length and pool changes contribute equally (or neither changed)."
    return {"ok": True, "a": _report(a, rate), "b": _report(b, rate),
            "comparison": {"deltaBits": from_len + from_pool, "fromLengthBits": from_len, "fromPoolBits": from_pool,
                           "orderOfMagnitudeDifference": log10_space(b.length, Rb) - log10_space(a.length, Ra),
                           "verdict": verdict}}


def sweep_configs(req: Any) -> dict:
    cfgs = req.get("configs") if isinstance(req, dict) else None
    if not isinstance(cfgs, list) or not 1 <= len(cfgs) <= 8:
        return error_json(["'configs' must be an array of 1 to 8 configurations."])
    max_l = req.get("maxLength", 32)
    if not _is_int(max_l) or not 1 <= max_l <= 128:
        return error_json(["'maxLength' must be between 1 and 128."])
    series, err = [], []
    for cj in cfgs:
        c, e = parse_config(cj)
        if e:
            err.extend(e)
            continue
        R = cb.build_pool(c).size
        lens = list(range(1, max_l + 1))
        label = cj.get("label", "config")
        series.append({"label": label if isinstance(label, str) else "config", "poolSize": R, "lengths": lens,
                       "log10N": [log10_space(n, R) for n in lens], "entropyBits": [entropy_bits(n, R) for n in lens]})
    return error_json(err) if err else {"ok": True, "series": series}
