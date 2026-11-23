"""Tests for the weekly outlook archive (weekly.py) and its pages (seo_pages.py weekly_pages), on made-up data."""
import csv, json, os, re, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo_pages as sp
import weekly as W
from test_seo_pages import live, sample


def store(base, medians, calls=()):
    """daily.csv with U91 and E10 medians {date: v} (E10 = U91 - 2), calls.csv rows (date, fuel, cls, head, now)"""
    os.makedirs(f"{base}/store", exist_ok=True)
    with open(f"{base}/store/daily.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "fuel", "median"])
        for d, v in sorted(medians.items()): w.writerow([d, "U91", v]); w.writerow([d, "E10", v - 2])
    if calls:
        with open(f"{base}/store/calls.csv", "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(["date", "fuel", "cls", "head", "now", "d3", "d7", "p_jump7"])
            for c in calls: w.writerow(list(c) + [0, 0, 0])


def days(start, n, f):
    import datetime as dt
    d0 = dt.date.fromisoformat(start)
    return {(d0 + dt.timedelta(k)).isoformat(): f(k) for k in range(n)}


class Snapshots(unittest.TestCase):
    def test_week_key(self):
        self.assertEqual(W.week_of("2026-11-23"), "2026-11-23")   # Monday
        self.assertEqual(W.week_of("2026-11-29"), "2026-11-23")   # Sunday
        self.assertEqual(W.week_of("2026-11-30"), "2026-11-30")

    def test_saved_once_and_loaded(self):
        with tempfile.TemporaryDirectory() as b:
            s = W.pending(b, "2026-11-24", [live("U91", 220), {"fuel": "U91?", "now": 1}], "t1")
            self.assertEqual((s["week"], [r["fuel"] for r in s["live"]]), ("2026-11-23", ["U91"]))
            self.assertEqual(s["live"][0]["verdict"], {"cls": "down", "head": "Wait if you can"})
            self.assertTrue(W.save(b, s))
            self.assertIsNone(W.pending(b, "2026-11-26", [live("U91", 230)], "t2"))   # this week's is saved
            self.assertFalse(W.save(b, {**s, "saved": "t3"}))
            with open(f"{b}/store/weekly/2026-11-16.json", "w") as fh: fh.write("{not json")
            with open(f"{b}/store/weekly/2026-11-09.json", "w") as fh: json.dump({**s, "week": "2026-11-09"}, fh)   # asof in another week
            self.assertEqual([x["saved"] for x in W.load(b)], ["t1"])


class Scoring(unittest.TestCase):
    def test_pending_then_scored(self):
        snap = W.snapshot("2026-11-02", [live("U91", 220), live("E10", 218)], "t")   # d7 -8.1 (range -20.4..+4.2), d14 -15.5
        with tempfile.TemporaryDirectory() as b:
            # through 9 Nov: day 7 (9 Nov) is today, a partial day, so nothing is scored yet
            store(b, days("2026-10-25", 16, lambda k: 220.0))
            s = W.score(b, [snap])[0]
            self.assertIsNone(s["score"]["U91"]["h7"]); self.assertFalse(s["done"]); self.assertIsNone(s["scored"])
            self.assertEqual(s["score"]["U91"]["call"]["status"], "pending")
            # through 17 Nov: 7 days scored (210 on 9 Nov: -10c, in range -20.4..+4.2), 14 days (16 Nov) at 190: -30c, in range -39..+8
            med = days("2026-10-25", 24, lambda k: 220.0 if k < 15 else 210.0 if k < 22 else 190.0)
            store(b, med, calls=[("2026-11-02", "U91", "up", "Fill up today", 221.0)])
            s = W.score(b, [snap])[0]; u = s["score"]["U91"]
            self.assertEqual(u["h7"], {"day": "2026-11-09", "actual": 210.0, "change": -10.0, "err": -1.9, "inside": True})
            self.assertEqual((u["h14"]["change"], u["h14"]["inside"]), (-30.0, True))
            # the call is calls.csv's (fill, made at 221), scored as the track record: the 7-day average fell -> wrong
            self.assertEqual((u["call"]["cls"], u["call"]["head"], u["call"]["now"], u["call"]["status"]), ("up", "Fill up today", 221.0, "wrong"))
            # E10 has no saved call: the snapshot's own (wait), right
            self.assertEqual((s["score"]["E10"]["call"]["cls"], s["score"]["E10"]["call"]["status"]), ("down", "right"))
            self.assertTrue(s["done"]); self.assertEqual(s["scored"], "2026-11-16")

    def test_call_matches_the_track_record_at_the_1c_edge(self):
        # fill at 220.0; the 7 days after average 220.96 -> +0.96, which the track record rounds to +1.0: right
        snap = W.snapshot("2026-11-02", [live("U91", 220)], "t")
        with tempfile.TemporaryDirectory() as b:
            med = days("2026-10-25", 17, lambda k: 220.0)
            for k, d in enumerate(sorted(x for x in med if "2026-11-03" <= x <= "2026-11-09")): med[d] = 220.96
            store(b, med, calls=[("2026-11-02", "U91", "up", "Fill up today", 220.0)])
            c = W.score(b, [snap])[0]["score"]["U91"]["call"]
            self.assertEqual((c["move"], c["status"]), (1.0, "right"))

    def test_a_missing_day_never_leaves_a_week_unscored(self):
        snap = W.snapshot("2026-11-02", [live("U91", 220)], "t")
        with tempfile.TemporaryDirectory() as b:
            med = days("2026-10-25", 24, lambda k: 220.0 if k < 15 else 210.0 if k < 16 else 205.0)
            del med["2026-11-09"]                                    # day 7 missing: the day before (220) is used
            store(b, med)
            s = W.score(b, [snap])[0]
            self.assertEqual((s["score"]["U91"]["h7"]["actual"], s["done"]), (220.0, True))
            for d in ("2026-11-07", "2026-11-08", "2026-11-10", "2026-11-11"): med.pop(d, None)
            store(b, med)
            s = W.score(b, [snap])[0]
            self.assertEqual(s["score"]["U91"]["h7"], {"day": "2026-11-09", "missing": True}); self.assertTrue(s["done"])

    def test_outside_the_range(self):
        snap = W.snapshot("2026-11-02", [live("U91", 220)], "t")
        with tempfile.TemporaryDirectory() as b:
            store(b, days("2026-10-25", 17, lambda k: 220.0 if k < 15 else 230.0))   # +10c on day 7 (9 Nov, over by 10 Nov): over hi7 +4.2
            self.assertFalse(W.score(b, [snap])[0]["score"]["U91"]["h7"]["inside"])


def scored(week, asof, done):
    s = W.snapshot(asof, [live("U91", 220), live("E10", 218)], "t")
    h7 = {"day": "2026-11-09", "actual": 210.0, "change": -10.0, "err": -1.9, "inside": True} if done else None
    call = {"cls": "down", "head": "Wait if you can", "now": 220.0, "move": -6.0 if done else None, "status": "right" if done else "pending"}
    return {**s, "score": {f: {"call": call, "h7": h7, "h14": None} for f in ("U91", "E10")}, "scored": "2026-11-09" if done else None, "done": done}


class Pages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.out = cls.tmp.name
        cls.weeks = [scored("2026-11-02", "2026-11-02", True), scored("2026-11-09", "2026-11-10", False)]
        sp.build(cls.out, *sample(), weekly=cls.weeks)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def read(self, p):
        with open(os.path.join(self.out, p, "index.html"), encoding="utf-8") as fh: return fh.read()

    def test_pages_and_links(self):
        done, pend, arch = self.read("fuel-price-forecast/2026-11-02"), self.read("fuel-price-forecast/2026-11-09"), self.read("fuel-price-forecast/weekly")
        self.assertIn("<title>Sydney fuel outlook, week of 2 Nov 2026, scored | Bowser</title>", done)
        for t in (done, pend, arch): self.assertLessEqual(len(re.search(r"<title>(.*?)</title>", t).group(1)), 70)
        self.assertIn('href="../../fuel-price-forecast/2026-11-09/"', done)          # next
        self.assertIn('href="../../fuel-price-forecast/2026-11-02/"', pend)          # previous
        self.assertIn("inside the likely range", done)
        self.assertIn("due 17 Nov", pend)                                             # 7 days after its asof, 10 Nov
        self.assertIn('<meta name="robots" content="noindex">', pend)                 # pending: not in search yet
        self.assertNotIn("noindex", done); self.assertNotIn("noindex", arch)
        self.assertLess(arch.index("2026-11-09/"), arch.index("2026-11-02/"))         # newest first
        for t in (done, pend, arch):
            for href in re.findall(r'href="\.\./\.\./(fuel-price-forecast/[^"]*)"', t):
                self.assertTrue(os.path.exists(os.path.join(self.out, href, "index.html")), href)

    def test_sitemap_and_forecast_page(self):
        with open(os.path.join(self.out, "sitemap.xml")) as fh: sm = fh.read()
        self.assertIn("fuel-price-forecast/2026-11-02/</loc><lastmod>2026-11-09</lastmod>", sm)
        self.assertNotIn("2026-11-09/</loc>", sm)
        fc = self.read("fuel-price-forecast")
        self.assertIn("Last week’s outlook, scored", fc)
        self.assertIn("The call that morning, “Wait if you can”, was <b>right</b>.", fc)
        self.assertIn("By 9 Nov it had fallen 10c, to 210.0c: inside the likely range, 1.9c from the forecast.", fc)

    def test_without_weeks_or_scores(self):
        with tempfile.TemporaryDirectory() as o:
            sp.build(o, *sample())
            self.assertFalse(os.path.exists(os.path.join(o, "fuel-price-forecast", "weekly")))
            with open(os.path.join(o, "fuel-price-forecast", "index.html"), encoding="utf-8") as fh: self.assertNotIn("Last week", fh.read())
        with tempfile.TemporaryDirectory() as o:
            sp.build(o, *sample(), weekly=[scored("2026-11-16", "2026-11-16", False)])
            with open(os.path.join(o, "fuel-price-forecast", "index.html"), encoding="utf-8") as fh: fc = fh.read()
            self.assertNotIn("Last week’s outlook", fc); self.assertIn("weekly outlooks</a>", fc)
            with open(os.path.join(o, "fuel-price-forecast", "weekly", "index.html"), encoding="utf-8") as fh: self.assertIn("noindex", fh.read())


if __name__ == "__main__":
    unittest.main()
