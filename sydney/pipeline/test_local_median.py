"""local_median: which region a station outside Sydney belongs to and the median it is compared with."""
import unittest

import local_median as lm


def st(i, la=-35.24, lo=149.06, p=None, out=1, m=0):
    return {"id": str(i), "la": la, "lo": lo, "out": out, "m": m, "p": p or {}}


class LocalMedian(unittest.TestCase):
    def test_canberra_region_and_median(self):
        pool = [st(i, p={"U91": [200.0 + i, 1, "na"]}) for i in range(9)]
        regs = lm.add(pool, ["U91", "E10"])
        self.assertEqual(regs["Canberra and Queanbeyan"]["name"], "Canberra")
        self.assertEqual(regs["Canberra and Queanbeyan"]["f"], {"U91": [204.0, 9]})   # E10: no prices, left out
        self.assertTrue(all(s["rg"] == "Canberra and Queanbeyan" for s in pool))

    def test_too_few_old_and_members_prices_dont_count(self):
        pool = [st(i, p={"U91": [200.0, 1, "na"]}) for i in range(7)]
        pool += [st(7, p={"U91": [150.0, 30, "chk"]}), st(8, p={"U91": [150.0, 1, "na"]}, m=1)]   # 30 days old; members only
        regs = lm.add(pool, ["U91"])
        self.assertEqual(regs, {})                                  # 7 current public prices: under MIN_N
        self.assertFalse(any("rg" in s for s in pool))               # no region figure, so no `rg` either

    def test_sydney_and_remote_stations_get_none(self):
        syd = st(1, la=-33.87, lo=151.2, out=None, p={"U91": [190.0, 1, "w"]})
        remote = st(2, la=-29.0, lo=145.0, p={"U91": [230.0, 1, "na"]})
        self.assertIsNone(lm.region_of(syd))
        self.assertIsNone(lm.region_of(remote))
        self.assertEqual(lm.add([syd, remote], ["U91"]), {})

    def test_non_numeric_age_still_counts(self):
        self.assertTrue(lm.current([210.0, None, "na"]))
        self.assertFalse(lm.current([None, 1, "na"]))
        self.assertFalse(lm.current(None))


if __name__ == "__main__":
    unittest.main()
