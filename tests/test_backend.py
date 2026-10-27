"""Backend tests. Run from the project root:  python -m unittest discover -s tests -v"""
import itertools
import math
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import combinatorics as cb          # noqa: E402
import entropy as en                # noqa: E402
import guessing_time as gt          # noqa: E402
import password_analyzer as pa      # noqa: E402
from app import app                 # noqa: E402


def cfg(L, lo=False, up=False, di=False, sy=False, **kw):
    return cb.Config(length=L, lower=lo, upper=up, digits=di, symbols=sy, **kw)


class MathCore(unittest.TestCase):
    def test_26_pow_8(self):
        self.assertEqual(cb.search_space(26, 8), 208827064576)

    def test_entropy_lowercase_8(self):
        self.assertAlmostEqual(en.entropy_bits(8, 26), 37.6035, places=3)

    def test_larger_pool_more_entropy(self):
        self.assertGreater(en.entropy_bits(10, 62), en.entropy_bits(10, 26))

    def test_extra_position_adds_log2_R(self):
        self.assertAlmostEqual(en.entropy_bits(9, 62) - en.entropy_bits(8, 62), math.log2(62), places=12)

    def test_pool_sizes_and_overlap(self):
        self.assertEqual(cb.build_pool(cfg(8, 1, 1, 1, 1)).size, 94)
        p = cb.build_pool(cfg(8, lo=True, sy=True, symbol_set="abc!"))
        self.assertEqual((p.size, p.naive_sum), (27, 30))        # 'a','b','c' counted once

    def test_at_least_one_formula(self):
        c = cfg(6, lo=True, di=True, required=["digit"])
        n = cb.constrained_count(c, cb.build_pool(c))["count"]
        self.assertEqual(n, 36**6 - 26**6)
        self.assertEqual(n, 1867866560)

    def test_constrained_never_exceeds_unrestricted(self):
        for req in (["digit"], ["digit", "symbol"], ["lower", "upper", "digit", "symbol"]):
            c = cfg(8, 1, 1, 1, 1, required=req)
            self.assertLessEqual(cb.constrained_count(c, cb.build_pool(c))["count"], cb.search_space(94, 8))

    def test_inclusion_exclusion_matches_brute_force(self):
        pool = "ab1!"
        for req, sets in ((["lower", "digit"], ["ab", "1"]), (["lower", "digit", "symbol"], ["ab", "1", "!"]), (["symbol"], ["!"])):
            c = cb.Config(length=4, use_custom=True, custom_pool=pool, required=req)
            brute = sum(1 for w in itertools.product(pool, repeat=4) if all(set(x) & set(w) for x in sets))
            self.assertEqual(cb.constrained_count(c, cb.build_pool(c))["count"], brute)

    def test_overlapping_requirement_sets(self):
        # symbol set contains letters, so 'lower' and 'symbol' share characters; union must not double count
        c = cfg(3, lo=True, sy=True, symbol_set="ab!", required=["lower", "symbol"])
        p = cb.build_pool(c)
        brute = sum(1 for w in itertools.product(sorted(p.chars), repeat=3)
                    if set(w) & cb.LOWER and set(w) & set("ab!"))
        self.assertEqual(cb.constrained_count(c, p)["count"], brute)

    def test_validation(self):
        bad = {"length 0": cfg(0, lo=True), "negative": cfg(-3, lo=True), "huge": cfg(5000, lo=True), "no sets": cfg(8),
               "empty custom": cb.Config(use_custom=True), "non-ascii custom": cb.Config(use_custom=True, custom_pool="ab\u00e9"),
               "control char symbols": cfg(8, sy=True, symbol_set="\x01"), "unknown req": cfg(8, lo=True, required=["emoji"]),
               "impossible": cfg(8, lo=True, required=["symbol"])}
        for name, c in bad.items():
            self.assertTrue(cb.validate_config(c), name)
        self.assertIn("Impossible", cb.validate_config(bad["impossible"])[0])

    def test_huge_search_space(self):
        self.assertEqual(len(str(cb.search_space(94, 1000))), 1974)
        self.assertTrue(math.isfinite(en.log10_space(1000, 94)))
        r = pa.analyze_config({"length": 1024, "lower": True, "upper": True, "digits": True, "symbols": True, "required": ["digit", "symbol"]})
        self.assertTrue(r["ok"] and r["constrained"]["entropyBits"] <= r["entropyBits"])

    def test_guessing_time(self):
        self.assertAlmostEqual(gt.estimate_time(6, 1e3, False)["log10Seconds"], 3.0)
        self.assertAlmostEqual(gt.estimate_time(6, 1e3, True)["log10Seconds"], math.log10(500))
        self.assertEqual(gt.estimate_time(6, 1e3, False)["human"], "16.7 minutes")
        for g in (0, -1, float("nan"), float("inf"), True, "5"):
            self.assertFalse(gt.valid_rate(g))
        self.assertIn("age of the universe", gt.estimate_time(60, 1e9, False)["human"])

    def test_formatting(self):
        self.assertEqual(en.sci_from_digits("208827064576"), "2.08e+11")
        self.assertEqual(en.group_thousands("208827064576"), "208,827,064,576")
        self.assertEqual(en.sci_from_log10(3.0), "1.00e+3")


class Api(unittest.TestCase):
    def setUp(self):
        self.c = app.test_client()

    def post(self, path, body):
        r = self.c.post(path, json=body)
        return r.status_code, r.get_json()

    def test_analyze_ok(self):
        s, d = self.post("/api/analyze-config", {"length": 8, "lower": True})
        self.assertEqual(s, 200)
        self.assertEqual(d["searchSpace"]["exact"], "208,827,064,576")
        self.assertAlmostEqual(d["entropyBits"], 37.6035, places=3)
        self.assertEqual(d["pool"]["size"], 26)
        self.assertEqual(len(d["steps"]), 4)

    def test_analyze_constrained(self):
        s, d = self.post("/api/analyze-config", {"length": 6, "lower": True, "digits": True, "required": ["digit"]})
        self.assertEqual((s, d["constrained"]["count"]), (200, "1,867,866,560"))
        self.assertEqual(len(d["constrained"]["terms"]), 2)

    def test_analyze_errors(self):
        cases = [{"lower": False}, {"length": 0, "lower": True}, {"length": "x", "lower": True}, {"length": None, "lower": True}, {"length": 8.5, "lower": True},
                 {"length": True, "lower": True}, {"length": 8, "lower": "yes"}, {"length": 8, "lower": True, "required": ["symbol"]},
                 {"length": 8, "lower": True, "guessesPerSecond": -1}, {"length": 8, "lower": True, "guessesPerSecond": "fast"},
                 {"length": 2, "lower": True, "upper": True, "digits": True, "required": ["lower", "upper", "digit"]},
                 {"length": 8, "useCustom": True, "customPool": ""}, {"length": 10**9, "lower": True}, {"length": 8, "required": "digit", "lower": True}]
        for body in cases:
            s, d = self.post("/api/analyze-config", body)
            self.assertEqual(s, 400, body)
            self.assertFalse(d["ok"]); self.assertTrue(d["errors"])

    def test_empty_object_uses_defaults(self):
        s, d = self.post("/api/analyze-config", {})      # documented defaults: length 8, lowercase only
        self.assertEqual((s, d["pool"]["size"], d["length"]), (200, 26, 8))

    def test_bad_bodies(self):
        self.assertEqual(self.c.post("/api/analyze-config", data="oops", content_type="application/json").status_code, 400)
        self.assertEqual(self.c.post("/api/analyze-config", json=[1, 2]).status_code, 400)
        self.assertEqual(self.c.post("/api/analyze-config", data="x" * 70000).status_code, 413)
        self.assertEqual(self.c.get("/api/analyze-config").status_code, 405)
        self.assertEqual(self.c.get("/api/nope").status_code, 404)

    def test_compare(self):
        s, d = self.post("/api/compare", {"a": {"length": 8, "lower": True}, "b": {"length": 12, "lower": True}})
        self.assertEqual(s, 200)
        cmpn = d["comparison"]
        self.assertAlmostEqual(cmpn["deltaBits"], 4 * math.log2(26), places=9)
        self.assertAlmostEqual(cmpn["fromPoolBits"], 0.0)
        self.assertIn("length", cmpn["verdict"])
        s, d = self.post("/api/compare", {"a": {"length": 8, "lower": True}})
        self.assertEqual(s, 400)
        s, d = self.post("/api/compare", {"a": {"length": 0, "lower": True}, "b": {"length": 8, "lower": True}})
        self.assertEqual(s, 400); self.assertTrue(d["errors"][0].startswith("Configuration A"))

    def test_sweep(self):
        s, d = self.post("/api/sweep", {"maxLength": 4, "configs": [{"length": 5, "lower": True, "label": "x"}, {"length": 5, "lower": True, "upper": True}]})
        self.assertEqual(s, 200)
        self.assertEqual(d["series"][0]["lengths"], [1, 2, 3, 4])
        self.assertAlmostEqual(d["series"][1]["entropyBits"][3], 4 * math.log2(52))
        for bad in ({"configs": []}, {"configs": [{"lower": True}] * 9}, {"maxLength": 0, "configs": [{"lower": True}]}, {"maxLength": "a", "configs": [{"lower": True}]},
                    {"configs": [{"length": 5, "lower": False}]}, {}):
            self.assertEqual(self.post("/api/sweep", bad)[0], 400, bad)

    def test_health_and_static(self):
        self.assertEqual(self.c.get("/api/health").get_json(), {"ok": True})
        r = self.c.get("/")
        self.assertEqual(r.status_code, 200); self.assertIn(b"PasswordLab", r.data)
        for f in ("/styles.css", "/app.js", "/vendor/chart.umd.js"):
            self.assertEqual(self.c.get(f).status_code, 200, f)
        self.assertEqual(self.c.get("/../backend/app.py").status_code, 404)


class FrontendContract(unittest.TestCase):
    """Checks that the frontend's requests and the response fields it reads match the backend."""
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "frontend", "app.js"), encoding="utf-8") as f:
            cls.js = f.read()
        cls.c = app.test_client()

    def test_every_endpoint_used_by_the_frontend_exists(self):
        used = set(re.findall(r"api\('(/api/[a-z-]+)'", self.js))
        self.assertEqual(used, {"/api/analyze-config", "/api/compare", "/api/sweep"})
        for u in used:
            self.assertNotEqual(self.c.post(u, json={}).status_code, 404, u)

    def test_response_fields_read_by_frontend(self):
        d = self.c.post("/api/analyze-config", json={"length": 8, "lower": True, "digits": True, "required": ["digit"], "guessesPerSecond": 1e10}).get_json()
        for path in ("pool.size pool.lower pool.upper pool.digits pool.symbols pool.overlapRemoved searchSpace.exact searchSpace.scientific searchSpace.digits "
                     "entropyBits guessing.average.human guessing.average.seconds guessing.worst.human guessing.worst.seconds steps assumptions length "
                     "constrained.count constrained.scientific constrained.entropyBits constrained.fractionOfAll constrained.terms constrained.formula constrained.assumption").split():
            node = d
            for k in path.split("."):
                self.assertIn(k, node, path); node = node[k]
        t = d["constrained"]["terms"][0]
        for k in ("subset", "unionSize", "sign", "value"):
            self.assertIn(k, t)
        cmp_ = self.c.post("/api/compare", json={"a": {"length": 8, "lower": True}, "b": {"length": 9, "lower": True}}).get_json()
        for k in ("deltaBits", "fromLengthBits", "fromPoolBits", "orderOfMagnitudeDifference", "verdict"):
            self.assertIn(k, cmp_["comparison"])
        sw = self.c.post("/api/sweep", json={"maxLength": 3, "configs": [{"length": 3, "lower": True, "label": "a"}]}).get_json()
        for k in ("label", "poolSize", "lengths", "log10N", "entropyBits"):
            self.assertIn(k, sw["series"][0])
        e = self.c.post("/api/analyze-config", json={"length": 0, "lower": True}).get_json()
        self.assertEqual((e["ok"], isinstance(e["errors"], list)), (False, True))

    def test_frontend_has_no_quiz_or_cpp_references(self):
        with open(os.path.join(ROOT, "frontend", "index.html"), encoding="utf-8") as f:
            html = (f.read() + self.js).lower()
        self.assertNotIn("quiz", html)
        self.assertNotIn("c++", html)


if __name__ == "__main__":
    unittest.main()
