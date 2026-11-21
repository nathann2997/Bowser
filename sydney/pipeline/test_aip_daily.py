"""aip_daily.py: the Sydney rows of AIP's daily TGP page, and filling the days after the workbook's last."""
import datetime as dt, unittest

import pandas as pd

import aip_daily

ROW = '<tr><td><a href="https://aip.com.au/pricing/terminal-gate-prices/{c}{f}">{city}</a></td>{tds}</tr>'
HEAD = ("<tr><th>Location</th><th>Monday, 16th November 2026</th><th>Tuesday, 17th November 2026</th>"
        "<th>Wednesday, 18th November 2026</th></tr>")


def page(ulp=("197.7", "197.3", "196.6"), dl=("248.4", "247.6", "246.8"), sydney=True):
    def table(word, f, vals):
        rows = [ROW.format(c="melbourne", f=f, city="Melbourne", tds="".join(f"<td>{v}</td>" for v in ("195.4", "195.0", "194.6")))]
        if sydney: rows.insert(0, ROW.format(c="sydney", f=f, city="Sydney", tds="".join(f"<td>{v}</td>" for v in vals)))
        return f'<h2>{word} (cents per litre, inclusive of GST)</h2><div class="tgptable table-wrap"><table border="1" class="tgptable">{HEAD}{"".join(rows)}</table></div>'
    return "<html><body>" + table("Petrol", "ULP", ulp) + table("Diesel", "diesel", dl) + "</body></html>"


TODAY = dt.date(2026, 11, 21)
P = lambda html, today=TODAY: aip_daily.parse(html, today)


class Parse(unittest.TestCase):
    def test_sydney_rows(self):
        d = P(page())
        self.assertEqual(list(d.index.strftime("%Y-%m-%d")), ["2026-11-16", "2026-11-17", "2026-11-18"])
        self.assertEqual(d.loc["2026-11-18"].tolist(), [196.6, 246.8])

    def test_unpublished_day_is_left_out(self):
        d = P(page(ulp=("197.7", "197.3", ""), dl=("248.4", "247.6", "-")))
        self.assertEqual(len(d), 2)

    def test_changed_page_fails_loudly(self):
        with self.assertRaises(ValueError): P(page(sydney=False))
        with self.assertRaises(ValueError): P(page(ulp=("19.7", "197.3", "196.6")))
        with self.assertRaises(ValueError): P("<html>no tables</html>")

    def test_holes_found_in_qa(self):
        # a Sydney cell left out: the prices would shift onto the wrong days
        with self.assertRaises(ValueError): P(page().replace("<td>197.3</td>", "", 1))
        # no petrol table: the diesel table must not be read as petrol
        no_petrol = page().split('<h2>Diesel')[1]
        with self.assertRaises(ValueError): P('<h2>Petrol (ULP)</h2><p>Not available</p><h2>Diesel' + no_petrol)
        # a price with a stray mark fails instead of being skipped
        with self.assertRaises(ValueError): P(page(ulp=("197.7c", "197.3", "196.6")))
        # header dates in the future, or weeks old, are misprints
        with self.assertRaises(ValueError): P(page(), today=dt.date(2026, 11, 15))
        with self.assertRaises(ValueError): P(page(), today=dt.date(2027, 1, 15))
        # one fuel missing on a day: the day waits for both
        self.assertEqual(len(P(page(ulp=("197.7", "197.3", "")))), 2)


class Merge(unittest.TestCase):
    def test_only_days_after_the_workbook(self):
        idx = pd.to_datetime(["2026-11-13", "2026-11-16"])
        wb = pd.DataFrame({"tgp_ulp": [197.5, 197.7], "tgp_dl": [249.4, 248.4]}, index=idx)
        daily = P(page(ulp=("999", "197.3", "196.6")).replace("999", "198.0"))   # a page value differing on the 16th
        out = aip_daily.merge(wb, daily)
        self.assertEqual(out.loc["2026-11-16", "tgp_ulp"], 197.7)               # the workbook wins on its own days
        self.assertEqual(out.index.max(), pd.Timestamp("2026-11-18"))
        self.assertEqual(len(out), 4)

    def test_nothing_new(self):
        wb = pd.DataFrame({"tgp_ulp": [196.6], "tgp_dl": [246.8]}, index=pd.to_datetime(["2026-11-18"]))
        self.assertIs(aip_daily.merge(wb, P(page())), wb)


if __name__ == "__main__":
    unittest.main()
