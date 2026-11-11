"""Tests for station_feats.py (the shadow forecast's inputs) and shadow_score.py.
Run: python3 -m unittest sydney/pipeline/test_station_feats.py"""
import os, sys, unittest

import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import station_feats as SF
import shadow_score as SS

NAN = float("nan")


class DayFeatures(unittest.TestCase):
    def setUp(self):
        # 20 stations at 200.0, the first 10 are majors; today 4 majors and 1 other have gone to 220.0
        self.major = np.array([True] * 10 + [False] * 10)
        self.before = np.full(20, 200.0)
        self.today = self.before.copy(); self.today[[0, 1, 2, 3, 10]] = 220.0

    def test_hike_shares_and_the_top_of_the_market(self):
        f = SF.day_features(self.today, {1: self.before, 3: self.before}, self.major)
        self.assertAlmostEqual(f["up5_1d"], 5 / 20); self.assertAlmostEqual(f["up_1d"], 5 / 20)
        self.assertAlmostEqual(f["maj_up5_1d"], 4 / 10); self.assertAlmostEqual(f["maj_up5_3d"], 4 / 10)
        self.assertAlmostEqual(f["ind_up5_3d"], 1 / 10)
        self.assertAlmostEqual(f["hi8"], 5 / 20); self.assertAlmostEqual(f["maj_hi8"], 4 / 10)
        self.assertAlmostEqual(f["p95_spread"], 20.0); self.assertAlmostEqual(f["maj_gap"], 0.0)
        self.assertTrue(np.isnan(f["up5_7d"]))                      # no snapshot from 7 days ago
        self.assertEqual(sorted(f), sorted(SF.COLS))

    def test_thresholds_sit_exactly_where_the_docstring_says(self):
        p = np.full(20, 200.0); p[:10] = [205.0, 204.9, 200.5, 200.4, 208.0, 207.9, 200, 200, 200, 200]   # majors
        f = SF.day_features(p, {1: np.full(20, 200.0)}, self.major)
        self.assertAlmostEqual(f["up5_1d"], 3 / 20)        # +5.0, +7.9 and +8.0 count; +4.9 doesn't
        self.assertAlmostEqual(f["up_1d"], 5 / 20)         # 0.5 counts, 0.4 doesn't
        self.assertAlmostEqual(f["hi8"], 1 / 20)           # the median is 200.0: only 208.0 is 8c+ over it
        self.assertAlmostEqual(f["maj_gap"], 0.45)         # majors' median (200.4 + 200.5) / 2 against 200.0
        q = np.arange(200.0, 220.0)                        # 200..219: the 95th percentile is 218.05, the median 209.5
        self.assertAlmostEqual(SF.day_features(q, {}, self.major)["p95_spread"], 8.55)

    def test_the_majors_are_the_brands_that_lead(self):
        self.assertTrue({"BP", "7-Eleven", "Ampol", "EG Ampol", "Shell", "Reddy Express"} <= SF.MAJORS)
        self.assertFalse({"Metro Fuel", "Speedway", "Budget", "Independent", "United"} & SF.MAJORS)

    def test_only_stations_priced_on_both_days_count(self):
        prev = self.before.copy(); prev[[0, 1]] = NAN                # two of the hikers had no price yesterday
        f = SF.day_features(self.today, {1: prev}, self.major)
        self.assertAlmostEqual(f["up5_1d"], 3 / 18)
        self.assertTrue(np.isnan(f["maj_up5_1d"]))                   # 8 majors left: under MIN_STATIONS, so blank

    def test_too_few_stations_is_blank_not_zero(self):
        f = SF.day_features(self.today[:9], {1: self.before[:9]}, self.major[:9])
        self.assertTrue(all(np.isnan(v) for v in f.values()))

    def test_history_and_snapshot_paths_agree(self):
        P = np.vstack([self.before, self.before, self.before, self.today])
        hist = SF.from_matrix(P, self.major)[-1]
        tab = lambda p: pd.DataFrame({"code": [str(i) for i in range(20)], "price": p, "brand": ["BP"] * 10 + ["Metro Fuel"] * 10})
        snap = SF.from_snapshots(tab(self.today), {1: tab(self.before), 3: tab(self.before), 7: None})
        for c in SF.COLS:
            self.assertTrue((np.isnan(hist[c]) and np.isnan(snap[c])) or abs(hist[c] - snap[c]) < 1e-12, c)

    def test_snapshot_stations_are_matched_by_code(self):
        tab = lambda codes, p: pd.DataFrame({"code": codes, "price": p, "brand": "BP"})
        codes = [str(i) for i in range(12)]
        f = SF.from_snapshots(tab(codes, [210.0] * 12), {1: tab(codes[::-1] + ["99"], [200.0] * 6 + [210.0] * 6 + [100.0])})
        self.assertAlmostEqual(f["up5_1d"], 6 / 12)                  # codes 6-11 were 200.0; station 99 is gone today


class ShadowScore(unittest.TestCase):
    def test_gain_and_error_per_run_and_model(self):
        med = {"U91": {f"2026-11-{d:02d}": v for d, v in zip(range(1, 10), [200, 210, 210, 210, 210, 210, 210, 210, 210])}}
        row = dict(date="2026-11-01", fuel="U91", run="first", time="05:20", now="200", d1="0", d3="-2", d7="-4", d14="0", pj="0.0",
                   s_d1="0", s_d3="2", s_d7="6", s_d14="0", s_pj="0.6")
        res = SS.score([row, dict(row, date="2026-11-08")], med, "2026-11-09")   # the second call's week isn't over
        live, sh = res[("first", "live")], res[("first", "shadow")]
        self.assertEqual((live["n"], sh["n"]), (1, 1))
        self.assertAlmostEqual(live["gain"], -10.0); self.assertAlmostEqual(sh["gain"], 10.0)   # wait vs fill before +10c
        self.assertEqual((live["wait_bj"], sh["wait_bj"]), (1, 0))
        self.assertAlmostEqual(live["err7"], 14.0); self.assertAlmostEqual(sh["err7"], 4.0)

    def test_a_damaged_row_is_skipped(self):
        med = {"U91": {f"2026-11-{d:02d}": 200.0 for d in range(1, 10)}}
        good = dict(date="2026-11-01", fuel="U91", run="last", time="21:20", now="200", d3="0", d7="0", pj="0", s_d3="0", s_d7="0", s_pj="0")
        self.assertEqual(SS.score([good], med, "2026-11-09")[("last", "live")]["n"], 1)
        for bad in [dict(good, now="x"), dict(good, now="nan"), dict(good, s_pj="nan"), dict(good, date="2026-13-40"), dict(good, date=""),
                    {k: v for k, v in good.items() if k != "run"}, dict(good, run="middle"), {k: v for k, v in good.items() if k != "d7"}]:
            self.assertEqual(SS.score([bad], med, "2026-11-09"), {}, bad)

    def test_a_first_row_logged_after_the_morning_is_left_out(self):
        med = {"U91": {f"2026-11-{d:02d}": 200.0 for d in range(1, 10)}}
        row = dict(date="2026-11-01", fuel="U91", run="first", time="05:20", now="200", d3="0", d7="0", pj="0", s_d3="0", s_d7="0", s_pj="0")
        self.assertEqual(SS.score([row, dict(row, time="11:59")], med, "2026-11-09")[("first", "live")]["n"], 2)
        for t in ["12:00", "17:01", "", None]:
            self.assertEqual(SS.score([dict(row, time=t)], med, "2026-11-09"), {}, t)

    def test_the_verdict_rule_is_export_api_s(self):
        v = SS.verdict
        self.assertEqual([v(1.5, 0, 0), v(1.4, 2, 0), v(1.4, 1.9, 0.35), v(1.4, 1.9, 0.34)], ["up", "up", "up", "flat"])
        self.assertEqual([v(-1.5, 0, 0), v(-1.4, -3, 0), v(-1.4, -2.9, 0), v(0, 0, 0.5)], ["down", "down", "flat", "up"])


if __name__ == "__main__":
    unittest.main()
