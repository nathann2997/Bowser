"""Tests for track_api.py: the scoring window, the tallies and what they're measured against.
Run: python3 -m unittest sydney/pipeline/test_track.py"""
import datetime as dt, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import track_api as T


def med(start, values, fuel="U91"):
    d0 = dt.date.fromisoformat(start)
    return {fuel: {(d0 + dt.timedelta(i)).isoformat(): v for i, v in enumerate(values)}}


def row(cls, move, date="2026-01-01", fuel="U91"):
    return {"date": date, "fuel": fuel, "cls": cls, "move": move, "status": T.score(cls, move)}


class Window(unittest.TestCase):
    def test_today_is_a_partial_day_and_never_counts(self):
        m = med("2026-11-04", [234.9, 231.9, 229.9, 229.4, 227.9, 226.9, 224.7, 221.9])   # 4 Nov .. 11 Nov (today)
        avg, n, done = T.window(m, "U91", "2026-11-04", "2026-11-11")
        self.assertEqual((n, done), (6, False))                    # 5-10 Nov; the 11th is today
        self.assertAlmostEqual(avg, (231.9 + 229.9 + 229.4 + 227.9 + 226.9 + 224.7) / 6)
        self.assertEqual(T.window(m, "U91", "2026-11-10", "2026-11-11")[:2], (None, 0))

    def test_complete_once_the_last_day_is_over(self):
        m = med("2026-11-03", [235.9] + [230.0] * 8)               # 3 Nov .. 11 Nov
        self.assertEqual(T.window(m, "U91", "2026-11-03", "2026-11-11"), (230.0, 7, True))
        self.assertEqual(T.window(m, "U91", "2026-11-03", "2026-11-10")[1:], (6, False))

    def test_needs_min_days_of_a_gappy_week(self):
        m = med("2026-11-01", [200.0, 201.0, 202.0, 203.0, 204.0])  # 4 days after the 1st, then nothing
        self.assertEqual(T.window(m, "U91", "2026-11-01", "2026-12-01")[1:], (4, False))


class Tally(unittest.TestCase):
    def test_score(self):
        self.assertEqual([T.score("up", 1), T.score("up", 0.9), T.score("up", -1)], ["right", "close", "wrong"])
        self.assertEqual([T.score("down", -1), T.score("down", 0.4), T.score("down", 1)], ["right", "close", "wrong"])
        self.assertEqual([T.score("flat", 2.9), T.score("flat", -4), T.score("flat", 5)], ["right", "close", "wrong"])
        self.assertEqual(T.score("up", None), "pending")

    def test_gain_is_the_value_of_following_the_call(self):
        self.assertEqual([T.value("up", 3), T.value("down", -4), T.value("down", 2), T.value("flat", -9)], [3, 4, -2, 0.0])
        t = T.one([row("up", 3), row("down", -4), row("down", 2), row("flat", -9)])
        self.assertEqual(t["gain"], 1.25)                          # (3 + 4 - 2 + 0) / 4
        self.assertEqual({k: v["n"] for k, v in t["by"].items()}, {"up": 1, "down": 2, "flat": 1})
        self.assertEqual(t["by"]["down"], {"n": 2, "right": 1, "close": 0, "wrong": 1})
        self.assertNotIn("base", t)
        self.assertIsNone(T.one([])["gain"])

    def test_base_is_the_best_rule_that_ignores_the_forecast(self):
        # prices barely move: "always no rush" is right every day, whatever was called
        quiet = [row("down", -0.5), row("up", 0.5), row("flat", 0.2), row("down", -1.5)]
        self.assertEqual(T.one(quiet, base=True)["base"], {"cls": "flat", "right": 4})
        falling = [row("down", -6), row("down", -4), row("up", 5)]
        self.assertEqual(T.one(falling, base=True)["base"], {"cls": "down", "right": 2})

    def test_pending_rows_are_not_tallied(self):
        rows = [row("down", -6), {"date": "2026-01-02", "fuel": "U91", "cls": "down", "move": None, "status": "pending"}]
        self.assertEqual(T.tally(rows)["U91"]["n"], 1)

    def test_check_catches_counts_that_do_not_add_up(self):
        t = {"calls": [], "live": T.tally([row("down", -6), row("up", 5)]), "replay": None}
        self.assertEqual(T.check(t), [])
        t["live"]["U91"]["by"]["down"]["right"] = 5
        self.assertTrue(T.check(t))

    def test_check_passes_a_replay_with_base_and_recent_and_fuels_with_no_rows(self):
        replay = T.tally([row("down", -6), row("up", 5)], base=True)       # only U91 has rows
        replay["U91"]["recent"] = T.one([row("down", -6)], base=True)
        self.assertEqual(T.check({"calls": [], "live": T.tally([]), "replay": replay}), [])
        replay["U91"]["recent"]["wrong"] = 3
        self.assertTrue(T.check({"calls": [], "live": T.tally([]), "replay": replay}))


if __name__ == "__main__":
    unittest.main()
