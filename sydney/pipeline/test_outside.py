"""Tests for stations outside Sydney in station_api.py: their chart history comes from the archived snapshots alone, and
they carry no forecast. Run: python3 -m unittest sydney/pipeline/test_outside.py"""
import gzip, json, os, sys, tempfile, unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import station_api as A


def snap(d, day, prices):
    """An archived snapshot for `day` (YYYYMMDD): prices = [(code, fuel, price, 'dd/mm/yyyy hh:mm:ss')]"""
    with gzip.open(f"{d}/nsw_snapshot_{day}.json.gz", "wt") as fh:
        json.dump({"stations": [{"code": c, "address": f"{c} Some St, TOWN NSW 2500"} for c in sorted({p[0] for p in prices})],
                   "prices": [{"stationcode": c, "fueltype": f, "price": p, "lastupdated": t} for c, f, p, t in prices]}, fh)


class SnapshotEvents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); d = self.tmp.name
        # "1" is a Sydney station (the monthly history covers it to 31 Oct); "2" is outside Sydney (snapshots only)
        snap(d, "20261030", [("1", "U91", 200.0, "30/10/2026 08:00:00"), ("2", "U91", 180.0, "20/10/2026 09:00:00")])
        snap(d, "20261031", [("1", "U91", 201.0, "31/10/2026 08:00:00"), ("2", "U91", 181.0, "31/10/2026 09:00:00")])
        snap(d, "20261101", [("1", "U91", 202.0, "01/11/2026 08:00:00"), ("2", "U91", 182.0, "01/11/2026 09:00:00")])
        self.after, self.asof = pd.Timestamp("2026-10-31"), pd.Timestamp("2026-11-01")

    def tearDown(self):
        self.tmp.cleanup()

    def days(self, ev, code):
        return sorted({str(t.date()) for t in ev[ev.code == code].ts})

    def test_sydney_station_only_gets_days_after_the_history(self):
        ev, addr = A._snapshot_events(self.tmp.name, self.after, self.asof, {"1", "2"}, extra={"2"}, since=pd.Timestamp("2026-01-01"))
        self.assertEqual(self.days(ev, "1"), ["2026-11-01"])
        self.assertEqual(set(addr), {"1", "2"})

    def test_station_outside_sydney_gets_every_snapshot_day(self):
        ev, _ = A._snapshot_events(self.tmp.name, self.after, self.asof, {"1", "2"}, extra={"2"}, since=pd.Timestamp("2026-01-01"))
        # the change on 20 Oct (its `lastupdated`), then each snapshot day
        self.assertEqual(self.days(ev, "2"), ["2026-10-20", "2026-10-30", "2026-10-31", "2026-11-01"])
        last = ev[ev.code == "2"].sort_values("ts").groupby(ev.ts.dt.normalize()).price.last()
        self.assertEqual(list(last), [180.0, 180.0, 181.0, 182.0])

    def test_since_limits_how_far_back_it_reads(self):
        ev, _ = A._snapshot_events(self.tmp.name, self.after, self.asof, {"1", "2"}, extra={"2"}, since=pd.Timestamp("2026-10-31"))
        self.assertEqual(self.days(ev, "2"), ["2026-10-31", "2026-11-01"])

    def test_without_extra_it_is_as_before(self):
        ev, _ = A._snapshot_events(self.tmp.name, self.after, self.asof, {"1", "2"})
        self.assertEqual(self.days(ev, "1"), ["2026-11-01"])
        self.assertEqual(self.days(ev, "2"), ["2026-11-01"])


class Check(unittest.TestCase):
    HIST = [None] * (A.DAYS - 1) + [180.0]

    def test_a_station_outside_sydney_must_not_have_a_forecast(self):
        s = {"id": "2", "out": 1, "p": {"U91": [180.0, 0, "na", "Price only", "Outside Sydney"]}}
        self.assertEqual(A.check({"2": {"fc": {}, "hist": {"U91": self.HIST}}}, [s]), [])
        errs = A.check({"2": {"fc": {"U91": {"now": 180.0}}, "hist": {"U91": self.HIST}}}, [s])
        self.assertEqual(len(errs), 1); self.assertIn("outside Sydney", errs[0])

    def test_a_sydney_station_still_needs_one(self):
        s = {"id": "1", "p": {"U91": [180.0, 0, "ok", "No rush", "x"]}}
        self.assertTrue(A.check({"1": {"fc": {}, "hist": {"U91": self.HIST}}}, [s]))


if __name__ == "__main__":
    unittest.main()
