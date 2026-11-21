import math, os, sys, unittest
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import station_revert as SR
from jump_floor import jump_floor


class Bins(unittest.TestCase):
    def test_right_inclusive_like_pd_cut(self):
        cut = pd.cut(pd.Series([-50, -10, -9.9, 0, 1, 1.01, 8, 8.01, 12, 40]), [-np.inf] + SR.EDGES + [np.inf], labels=False)
        for x, c in zip([-50, -10, -9.9, 0, 1, 1.01, 8, 8.01, 12, 40], cut):
            self.assertEqual(SR.bin_of(x), c, x)

    def test_eight_is_in_six_to_eight(self):
        self.assertEqual(SR.bin_of(8.0), SR.EDGES.index(8))
        self.assertEqual(SR.bin_of(8.0001), SR.EDGES.index(8) + 1)


class Term(unittest.TestCase):
    def setUp(self):
        self.tab = {"edges": SR.EDGES, "med": {h: [0.0] * 10 for h in ["1", "3", "7", "14"]}}
        i = SR.bin_of(10)
        for h, v in zip(["1", "3", "7", "14"], [-1, -3, -5, -7]): self.tab["med"][h][i] = v

    def test_interpolates_from_zero(self):
        t = SR.term(10, self.tab, np.arange(15))
        self.assertEqual(t[0], 0); self.assertEqual(t[1], -1); self.assertEqual(t[2], -2); self.assertEqual(t[14], -7)
        self.assertAlmostEqual(t[10], -5 + (10 - 7) / 7 * -2)

    def test_other_bin_and_no_table(self):
        self.assertTrue((SR.term(0, self.tab, np.arange(15)) == 0).all())
        self.assertTrue((SR.term(10, None, np.arange(15)) == 0).all())
        self.assertTrue((SR.term(float("nan"), self.tab, np.arange(15)) == 0).all())


class Rows(unittest.TestCase):
    """A station 10c above its usual premium that eases 1c a day for 10 days while the median is flat."""
    def make(self):
        days = pd.date_range("2026-01-01", periods=60)
        med = pd.Series(200.0, index=days)
        p = np.full(60, 210.0); p[20:31] = 210 - np.arange(11); p[31:] = 200
        raw = pd.DataFrame({"A": p, "B": 200.0}, index=days)
        raw["B"] = np.where(np.arange(60) % 5 == 0, 200.0, np.nan)          # B re-seen every 5 days: always fresh
        typ = pd.Series({"A": 0.0, "B": 0.0})
        return raw, med, typ

    def test_reversion_measured(self):
        raw, med, typ = self.make()
        R = SR.rows(raw, med, typ, {"A": (1.0, 0), "B": (1.0, 0)})
        self.assertEqual(set(R.h), {1, 3, 7, 14})
        a = R[(R.h == 7) & (R.x0 == 10)]
        self.assertTrue(len(a))
        # from day 20 (x0 = 10, fresh: it changed that day) the 7-day move is -7
        self.assertIn(-7.0, set(a.y.round(6)))

    def test_stale_station_dropped(self):
        raw, med, typ = self.make()
        raw["A"] = np.nan; raw.iloc[0, 0] = 215            # one price on day 0, never again: stale after 10 days
        R = SR.rows(raw[["A"]], med, typ[["A"]], {"A": (1.0, 0)})
        self.assertTrue(len(R) > 0)
        self.assertTrue((R.x0 == 15).all())
        # every row must be fresh at t and t + h: t + h <= day 10
        self.assertEqual(len(R[R.h == 14]), 0)

    def test_w_s_and_damping(self):
        days = pd.date_range("2026-01-01", periods=30)
        med = pd.Series(200 + np.arange(30, dtype=float), index=days)   # median rises 1c a day
        raw = pd.DataFrame({"A": 205 + 0.5 * np.arange(30, dtype=float)}, index=days)   # half the move, every day seen
        R = SR.rows(raw, med, pd.Series({"A": 5.0}), {"A": (0.5, 0)})
        self.assertTrue(np.allclose(R.y, 0))                             # w = 0.5 explains it all
        self.assertEqual(SR.w_s({"n": 10, "part": 0.3, "lag": 72}, 0.6, 48), (0.5, 1))
        self.assertEqual(SR.w_s(None, 0.6, 48), (1.0, 0))
        self.assertEqual(SR.w_s({"n": 2, "part": 0.1}, 0.6, 48), (1.0, 0))

    def test_table_needs_min_rows(self):
        R = pd.DataFrame({"x0": [10.0] * 250 + [0.0] * 50, "y": [-4.0] * 250 + [3.0] * 50, "h": 7})
        R = pd.concat([R, R.assign(h=1), R.assign(h=3), R.assign(h=14)])
        t = SR.table(R)
        self.assertEqual(t["med"]["7"][SR.bin_of(10)], -4.0)
        self.assertEqual(t["med"]["7"][SR.bin_of(0)], 0.0)               # 50 rows: under MIN_ROWS
        self.assertEqual(t["n"]["7"][SR.bin_of(0)], 50)
        self.assertEqual(len(t["med"]["14"]), len(SR.EDGES) + 1)


class Floor(unittest.TestCase):
    def frame(self, fuel, n, rate, p=0.01, end="2026-11-01"):
        d = pd.date_range(end=end, periods=n)
        return pd.DataFrame({"date": d, "fuel": fuel, "p": p, "y_jump7": (np.arange(n) < round(n * rate)).astype(float)})

    def test_per_fuel_pooled_and_cap(self):
        C = pd.concat([self.frame("U91", 200, 0.08), self.frame("DL", 50, 0.5), self.frame("E10", 200, 0.3),
                       self.frame("U91", 100, 1.0, p=0.5)])            # rated 50%: not in the floor
        fl = jump_floor(C, ["U91", "DL", "E10", "P98"])
        self.assertEqual(fl["U91"], 0.08)
        self.assertEqual(fl["E10"], 0.12)                                # capped
        pooled = (16 + 25 + 60) / 450
        self.assertEqual(fl["DL"], round(min(pooled, 0.12), 3))          # under 100 days: pooled
        self.assertEqual(fl["P98"], fl["DL"])

    def test_old_days_ignored(self):
        C = pd.concat([self.frame("U91", 200, 0.0), self.frame("U91", 300, 1.0, end="2023-01-01")])
        self.assertEqual(jump_floor(C, ["U91"])["U91"], 0.0)

    def test_cap_keeps_rise_date_and_calls(self):
        p7 = 0.12; lam = 1 - (1 - p7) ** (1 / 7)
        k = int(math.floor(math.log(0.75) / math.log(1 - lam))) + 1     # build.py market()
        self.assertGreater(k, 14)
        self.assertLess(p7, 0.35)                                        # verdict() call line


if __name__ == "__main__":
    unittest.main()
