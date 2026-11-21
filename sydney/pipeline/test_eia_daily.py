"""Tests for pages.py: the AIP terminal gate price page and the EIA daily prices page, on snippets cut from the real
pages (2026-11-11). Run: python3 -m unittest sydney/pipeline/test_pages.py"""
import datetime as dt, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eia_daily as P

AIP = """
<div>Petrol (ULP, cents per litre, inclusive of GST)</div>
<table><tr><th>Location</th><th>Thursday, 5th November 2026</th><th>Friday, 6th November 2026</th>
<th>Monday, 9th November 2026</th><th>Tuesday, 10th November 2026</th><th>Wednesday, 11th November 2026</th></tr>
<tr><td>Sydney</td><td>217.8</td><td>212.8</td><td>206.7</td><td>204.3</td><td>202.5</td></tr>
<tr><td>Melbourne</td><td>216.9</td><td>211.7</td><td>205.8</td><td>203.2</td><td>201.1</td></tr></table>
<div>Diesel (cents per litre, inclusive of GST)</div>
<table><tr><th>Location</th><th>Thursday, 5th November 2026</th><th>Friday, 6th November 2026</th>
<th>Monday, 9th November 2026</th><th>Tuesday, 10th November 2026</th><th>Wednesday, 11th November 2026</th></tr>
<tr><td>Sydney</td><td>260.9</td><td>259.2</td><td>256.6</td><td>255.5</td><td>255.0</td></tr>
<tr><td>Melbourne</td><td>260.2</td><td>258.3</td><td>255.4</td><td>254.3</td><td>254.0</td></tr></table>
"""

EIA = """
<tr class="prices_table_title"><td colspan="4"><b>Wholesale Spot Petroleum Prices, 11/09/26 Close</b></td></tr>
<tr class="prices_table_title"><th class="h2">Product</th><th class="h2">Area</th><th class="h4">Price</th><th class="h4">Percent<br>Change*</th></tr>
<tr valign="top"><td class="s1" rowspan="3">Crude Oil<br> ($/barrel)</td>
  <td class="s2">WTI</td><td class="d1">90.40</td><td class="dn">-4.2</td></tr>
<tr><td class="s2">Brent</td><td class="d1">91.03</td><td class="dn">-7.0</td></tr>
<tr><td class="s2">Louisiana Light</td><td class="d1">92.40</td><td class="dn">-3.6</td></tr>
<tr><td class="s1" rowspan="3">Gasoline (RBOB)<br /> ($/gallon)</td>
  <td class="s2">NY Harbor</td><td class="d1">2.76</td><td class="dn">-4.4</td></tr>
<tr><td class="s1" rowspan="2">Heating Oil<br /> ($/gallon)</td>
  <td class="s2">NY Harbor</td><td class="d1">4.11</td><td class="dn">-3.3</td></tr>
<tr><td class="s1" rowspan="3">Low-Sulfur Diesel<br /> ($/gallon)</td>
  <td class="s2">NY Harbor</td><td class="d1">4.25</td><td class="dn">-4.9</td></tr>
<tr><td class="s2">Gulf Coast</td><td class="d1">4.15</td><td class="dn">-3.6</td></tr>
</table>
<table><tr class="prices_table_title"><td><b>Retail Petroleum Prices</b></td></tr>
<tr><td class="s1">Crude Oil</td><td class="s2">Brent</td><td class="d1">1.00</td></tr></table>
"""


class EiaPage(unittest.TestCase):
    def test_brent_and_ny_harbor_diesel_for_the_close_date(self):
        day, v = P.parse_eia_daily(EIA)
        self.assertEqual(day, dt.date(2026, 11, 9))
        self.assertEqual(v, {"DCOILBRENTEU": 91.03, "ULSD_NYH": 4.25})   # not WTI, heating oil, Gulf Coast or the retail table

    def test_na_diesel_is_left_out_but_brent_is_required(self):
        self.assertEqual(P.parse_eia_daily(EIA.replace(">4.25<", ">NA<"))[1], {"DCOILBRENTEU": 91.03})
        with self.assertRaises(ValueError): P.parse_eia_daily(EIA.replace(">91.03<", ">NA<"))

    def test_a_changed_page_is_an_error(self):
        with self.assertRaises(ValueError): P.parse_eia_daily(EIA.replace("Wholesale Spot Petroleum Prices", "Spot Prices"))
        with self.assertRaises(ValueError): P.parse_eia_daily(EIA.replace(">91.03<", ">910.3<"))


if __name__ == "__main__":
    unittest.main()
