"""Tests for the search pages (seo_pages.py), on small made-up data: no network, no pandas.

  python -m unittest discover -s sydney/pipeline -p "test_*.py"
"""
import base64, datetime as dt, hashlib, html, json, os, re, sys, tempfile, unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo_pages as sp

ASOF = "2026-11-17"


def adv(code="wait", label="Wait", why="Sydney U91 expected about 8c lower by Tue 24 Nov"):
    return [code, label, why]


def station(i, name, brand, sub, pc, la, lo, prices, **extra):
    return dict(id=str(i), n=name, b=brand, s=sub, pc=pc, la=la, lo=lo, m=0,
                p={f: [p, age] + adv() + [round(p - 5, 1)] for f, (p, age) in prices.items()}, **extra)


def live(f, now):
    return dict(fuel=f, now=now, p10=now - 12, p90=now + 8, d1=-1.4, lo1=-3, hi1=1, d3=-5.0, lo3=-9, hi3=0, d7=-8.1, lo7=-20.4, hi7=4.2,
                d14=-15.5, lo14=-39, hi14=8, p_jump7=0.02, verdict={"cls": "down", "head": "Wait if you can"})


def sample():
    st = [
        station(1, "7-Eleven Parramatta", "7-Eleven", "Parramatta", 2150, -33.815, 151.003, {"U91": (216.9, 0), "E10": (214.9, 0), "P98": (242.9, 0)}),
        station(2, "SPEEDWAY PARRAMATTA", "Speedway", "Parramatta", 2150, -33.817, 151.005, {"U91": (205.5, 1), "DL": (257.5, 1)}),
        station(3, "7-Eleven Granville", "7-Eleven", "Granville", 2142, -33.833, 151.011, {"U91": (199.9, 0), "E10": (197.9, 0)}),
        station(4, "7-Eleven Harris Park", "7-Eleven", "12 Station Street Harris Park", 2150, -33.823, 151.008, {"U91": (209.9, 12)}),
        station(5, "Costco Auburn (Members only)", "Costco", "Auburn", 2144, -33.85, 151.03, {"P98": (215.9, 0), "DL": (240.9, 0)}, ),
        station(6, 'Joe\'s <script>alert(1)</script> & "Sons"', "Independent", "Harris Park", 2150, -33.824, 151.009, {"DL": (262.0, 0)}),
        station(7, "Ampol Dubbo", "Ampol", "Dubbo", 2830, -32.25, 148.6, {"U91": (229.9, 0)}, out=1),
        station(8, "No Suburb Servo", "Independent", "Postcode 2143", 2143, -33.86, 151.02, {"U91": (211.0, 0)}),
        station("x9", "Bad Id", "BP", "Parramatta", 2150, -33.8, 151.0, {"U91": (1.0, 0)}),
    ]
    st[4]["m"] = 1
    st[6]["p"]["U91"] = [229.9, 0, "na", "Price only", "Outside Sydney, where Bowser has no forecast"]
    stations = {"asof": ASOF, "stations": st}
    forecast = {"asof": ASOF, "live": [live("U91", 213.6), live("E10", 211.8), live("P95", 232.9), live("P98", 239.9), live("DL", 264.9)],
                "stats": {"cycles_by_year": [{"year": 2025, "n": 10, "gap": 35.5, "amp": 41.5}, {"year": 2026, "n": 7, "gap": 39.0, "amp": 21.0}],
                          "cycle_gap_calm": 37.0, "cycle_amp_calm": 37.0, "last_restore": "2026-09-15", "dow": [0.2, 0.3, 0.1, -0.2, -0.3, -0.1, -0.1],
                          "shop_around": 13.4, "p98_prem": 24.4, "p95_prem": 18.6, "e10_disc": 1.0, "low_2019": 89.9, "high_all": 259.9, "high_date": "2026-03-29",
                          "recent_jumps": [{"date": "2025-12-10", "amp": 45.0, "gap": 42}, {"date": "2026-01-21", "amp": 37.0, "gap": 36},
                                           {"date": "2026-08-04", "amp": 14.8, "gap": 42}, {"date": "2026-09-15", "amp": 30.0, "gap": None}, "junk"]},
                "bt": {"prod": "+cycle memory", "summary": {f"{f}|{h}": {"naive": 2.0 * h, "+cycle memory": 1.0 * h, "dir": 0.9} for f in sp.FUELS for h in (1, 3, 7, 14)},
                       "yearly_u91_h7": {"2025": {"naive": 13.8, "model": 4.8}, "2026": {"naive": 10.5, "model": 7.9}}}}
    # four Christmases (2022-23 to 2025-26), each with a 20c jump on 20 December except 2023's
    n = (dt.date.fromisoformat(ASOF) - dt.date(2022, 11, 1)).days + 1
    jump = lambda i: 20 if any(dt.date(y, 12, 20) <= dt.date(2022, 11, 1) + dt.timedelta(days=i) <= dt.date(y, 12, 28) for y in (2022, 2024, 2025)) else 0
    med = [200 + (i % 30) * 0.1 + jump(i) for i in range(n)]
    history = {"start": "2022-11-01", "hist": {f: {"med": list(med), "p10": [v - 10 for v in med], "p90": [v + 10 for v in med]} for f in sp.FUELS}}
    # station 1: 400 days ending ASOF, with a month stuck at a slip price (151.9) that the chart must leave out
    h = [205.0 + (i % 30) * 0.5 for i in range(400)]
    for i in range(330, 360): h[i] = 151.9
    h[-1] = 216.9
    details = {"1": {"start": "2025-10-14", "addr": "81 Victoria Road, Parramatta NSW 2150", "hist": {"U91": h},
                     "profile": {"typ": {"U91": 1.5}, "lag": 30, "part": 0.8, "n": 24},
                     "fc": {"U91": {"now": 216.9, "d7": -9.2, "lo7": -23.1, "hi7": 4.8, "rise": None}}}}
    track = {"replay": {"U91": {"n": 2098, "right": 1736, "close": 211, "wrong": 151, "from": "2021-01-01", "to": "2026-10-22",
                                "by": {"up": {"n": 711, "right": 478, "close": 137, "wrong": 96}, "down": {"n": 1186, "right": 1113, "close": 41, "wrong": 32},
                                       "flat": {"n": 201, "right": 145, "close": 33, "wrong": 23}}, "base": {"cls": "down", "right": 1314},
                                "recent": {"n": 342, "right": 247, "close": 42, "wrong": 53, "from": "2025-10-23", "to": "2026-10-22", "save": 2.35, "base": {"cls": "down", "right": 164}}}},
             "live": {"U91": {"n": 19, "right": 11, "close": 8, "wrong": 0, "since": "2026-10-22"}}}
    return stations, forecast, history, details, track


class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.out = cls.tmp.name
        cls.report = sp.build(cls.out, *sample())
        cls.pages = {}
        for d, _, fs in os.walk(cls.out):
            for f in fs:
                if f.endswith(".html"):
                    p = os.path.join(d, f)
                    with open(p, encoding="utf-8") as fh: cls.pages[os.path.relpath(p, cls.out)] = fh.read()

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def page(self, path): return self.pages[os.path.join(path, "index.html")]

    def test_pages_written(self):
        self.assertEqual(self.report["stations"], 8)             # the non-numeric id is dropped
        self.assertEqual(self.report["suburbs"], 5)              # Parramatta, Granville, Harris Park, Auburn, Dubbo
        self.assertEqual(self.report["brands"], 1)               # 7-Eleven is the only brand with three stations
        for p in ["fuel-prices", "fuel-prices/unleaded-91", "fuel-prices/diesel", "fuel-prices/parramatta-2150", "fuel-prices/harris-park-2150",
                  "station", "station/7-eleven-parramatta-1", "brands", "brands/7-eleven", "fuel-price-forecast", "petrol-price-cycle",
                  "nsw-fuelcheck", "about", "privacy", "fuel-price-forecast/accuracy", "best-day-to-buy-petrol", "petrol-prices-christmas"]:
            self.assertIn(os.path.join(p, "index.html"), self.pages, p)
        self.assertIn("404.html", self.pages)
        self.assertNotIn(os.path.join("fuel-prices", "postcode-2143-2143", "index.html"), self.pages)
        self.assertEqual(self.report["pages"], len(self.pages) - 1)   # every page but the 404 is in the sitemap

    def test_suburb_from_an_address(self):
        # "12 Station Street Harris Park" is filed under Harris Park, with the station that is really there
        self.assertIn("7-Eleven Harris Park", self.page("fuel-prices/harris-park-2150"))

    def test_every_page_has_one_title_description_canonical_h1(self):
        seen_titles = {}
        for path, t in self.pages.items():
            self.assertTrue(t.startswith("<!doctype html>\n<html lang=\"en-AU\""), path)
            self.assertEqual(t.count("<title>"), 1, path); self.assertEqual(t.count("<h1>"), 1, path)
            self.assertEqual(len(re.findall(r'<meta name="description" content="[^"]{50,}">', t)), 1, path) if path != "404.html" else None
            if path == "404.html" or 'content="noindex"' in t:
                self.assertIn('<meta name="robots" content="noindex">', t); self.assertNotIn('rel="canonical"', t); continue
            want = "https://checkbowser.app/" + path[:-len("index.html")].replace(os.sep, "/")
            self.assertIn(f'<link rel="canonical" href="{want}">', t, path)
            title = re.search(r"<title>(.*?)</title>", t).group(1)
            self.assertNotIn(title, seen_titles, f"{path} shares its title with {seen_titles.get(title)}"); seen_titles[title] = path
            self.assertLessEqual(len(html.unescape(title)), 70, title)

    def test_csp_hashes_match_the_page(self):
        h = lambda s: base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()
        for path, t in self.pages.items():
            scripts = re.findall(r"<script>(.*?)</script>", t, re.S | re.I); styles = re.findall(r"<style>(.*?)</style>", t, re.S)
            self.assertEqual((len(scripts), len(styles)), (1, 1), path)
            csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', t).group(1)
            self.assertIn(f"script-src 'sha256-{h(scripts[0])}'", csp); self.assertIn(f"style-src 'sha256-{h(styles[0])}'", csp)
            # nothing the policy would block: no inline handlers or style attributes, and every other script is JSON-LD
            self.assertIsNone(re.search(r"\son\w+\s*=|\sstyle\s*=", t), path)
            for tag in re.findall(r"<script[^>]+>", t, re.I): self.assertEqual(tag, '<script type="application/ld+json">', path)

    def test_names_from_the_feed_are_escaped(self):
        for path, t in self.pages.items():
            self.assertNotIn("<script>alert(1)", t, path)
            for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S): json.loads(block)   # valid JSON
        self.assertIn("Joe&#x27;s &lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;Sons&quot;", self.page("fuel-prices/harris-park-2150"))

    def test_every_internal_link_leads_to_a_page(self):
        for path, t in self.pages.items():
            if path == "404.html": continue                       # its links are root-relative (it is served at any depth)
            here = os.path.dirname(path)
            for href in re.findall(r'href="([^"]+)"', t):
                if re.match(r"https?:|mailto:|#", href): continue
                target = os.path.normpath(os.path.join(here, href.split("#")[0]))
                if target in (".", ""): continue                  # the dashboard, written by export_api.py
                if target in ("favicon.svg", "apple-touch-icon.png"): continue   # copied from static/ by export_api.py
                self.assertFalse(target.startswith(".."), f"{path}: {href} leaves the site")
                self.assertIn(os.path.join(target, "index.html"), self.pages, f"{path}: {href}")

    def test_sitemap_and_robots(self):
        root = ET.parse(os.path.join(self.out, "sitemap.xml")).getroot()
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [u.find("s:loc", ns).text for u in root.findall("s:url", ns)]
        self.assertEqual(locs[0], "https://checkbowser.app/")
        self.assertEqual(len(locs), len(set(locs))); self.assertEqual(len(locs), self.report["pages"] + 1)
        for loc in locs[1:]:
            self.assertIn(os.path.join(loc[len("https://checkbowser.app/"):].replace("/", os.sep), "index.html"), self.pages, loc)
        self.assertTrue(all(u.find("s:lastmod", ns).text == ASOF for u in root.findall("s:url", ns)))   # all Sydney here
        with open(os.path.join(self.out, "robots.txt")) as fh: robots = fh.read()
        self.assertIn("Sitemap: https://checkbowser.app/sitemap.xml", robots); self.assertNotIn("Disallow: /\n", robots)

    def test_station_page(self):
        t = self.page("station/7-eleven-parramatta-1")
        self.assertIn("<b>216.9c/L</b>", t); self.assertIn('<span class="dear">3.3c over</span> the Sydney median', t)
        self.assertIn("81 Victoria Road, Parramatta NSW 2150", t)
        self.assertIn("In a week Bowser expects about 207.7c here", t)
        self.assertIn("Sydney Unleaded 91 expected about 8c lower", t)      # the fuel code spelled out
        self.assertIn('"@type":"GasStation"', t); self.assertIn('"streetAddress":"81 Victoria Road"', t)
        self.assertIn("<svg class=\"chart\"", t)
        self.assertNotIn("151.9", t)                                        # the stuck price is left out of the range
        self.assertIn("Speedway Parramatta", t)                             # nearby, its ALL-CAPS name in title case

    def test_stale_and_members_prices_dont_win(self):
        # Harris Park's 209.9 is 12 days old: shown greyed with its age, and never called the cheapest
        t = self.page("fuel-prices/harris-park-2150")
        self.assertIn("12 days old", t); self.assertNotIn("The cheapest Unleaded 91", t)
        self.assertNotIn("209.9", re.search(r"<title>(.*?)</title>", t).group(1))
        fuel98 = self.page("fuel-prices/premium-98")
        self.assertNotIn("Costco Auburn", fuel98)
        self.assertIn("members only", self.page("brands").lower() + self.page("station/costco-auburn-5").lower())

    def test_outside_sydney_has_prices_but_no_forecast(self):
        s, t = self.page("station/ampol-dubbo-7"), self.page("fuel-prices/dubbo-2830")
        for x in (s, t):
            self.assertIn("229.9", x); self.assertNotIn("the Sydney median</span>", x); self.assertNotIn('class="verdict', x)
        self.assertIn("outside Sydney", s); self.assertIn("prices only", t)
        self.assertNotIn("Ampol Dubbo", self.page("fuel-prices/unleaded-91"))   # the Sydney ranking is Sydney's

    def test_no_wholesale_figures(self):
        # AIP's terminal gate prices are all rights reserved (DATA-LICENSE.md): the search pages never print them
        for path, t in self.pages.items():
            self.assertIsNone(re.search(r"terminal gate|\bTGP\b", t), path)

    def test_guides_use_todays_numbers(self):
        f = self.page("fuel-price-forecast")
        self.assertIn("fall by about 8.1c a litre", f); self.assertIn("<b>83%</b>", f); self.assertIn("11 of 19 scored calls", f)
        c = self.page("petrol-price-cycle")
        self.assertIn("63 days ago", c); self.assertIn("2026 (so far)", c); self.assertIn("<b>0.6c a litre</b>", c)
        self.assertIn("isn’t affiliated with or endorsed by the NSW Government", self.page("nsw-fuelcheck"))


    def test_forecast_page_answers_questions(self):
        f = self.page("fuel-price-forecast")
        self.assertIn("will petrol go up or down this week?</h1>", f)
        self.assertIn('"@type":"FAQPage"', f); self.assertIn('"@type":"Dataset"', f); self.assertIn('"temporalCoverage":"2026-11-17/2026-12-01"', f)
        self.assertIn("<h3>Will petrol go up tomorrow in Sydney?</h3>", f); self.assertIn("about 212.2c a litre tomorrow", f)
        self.assertIn("<td>50 litres</td><td class=\"n\">$4.05</td>", f)                 # 8.1c on 50 L
        self.assertEqual(f.count('<svg class="chart"'), 1)                                  # the 60 days and the 14-day forecast
        self.assertIn('href="../fuel-price-forecast/accuracy/"', f)
        self.assertIn("4 price jumps, typically 34c a litre, against about 37c and 10 a year in normal years, so the cycle has been weaker than usual: fewer jumps. Today is day 63", f)
        self.assertEqual(len(re.findall(r"<p[ >]", f)), f.count("</p>"))

    def test_accuracy_page(self):
        a = self.page("fuel-price-forecast/accuracy")
        self.assertIn("right <b>83%</b> of the time", a); self.assertIn("always saying “wait”, was right on 63%", a)
        self.assertIn("off by <b>7.0c</b> a litre on average, against 14.0c", a)
        self.assertIn("<td>Wait</td><td class=\"n\">1,186</td><td class=\"n\">94%</td>", a)
        self.assertIn("The hardest year was 2026", a); self.assertIn("the going was harder", a)

    def test_cycle_best_day_and_christmas(self):
        c = self.page("petrol-price-cycle")
        self.assertIn("<b>Running long</b>", c); self.assertIn("63 so far", c); self.assertIn("Day 63 since the last price jump", c)
        b = self.page("best-day-to-buy-petrol")
        self.assertIn("Friday is the cheapest day to buy petrol in Sydney and Tuesday the dearest", b)
        self.assertIn("No. In Sydney, Tuesday averages 0.3c over", b); self.assertIn('"@type":"FAQPage"', b)
        x = self.page("petrol-prices-christmas")
        self.assertIn("In 3 of the last 4 Christmas holidays (2022 to 2025)", x)
        self.assertIn("<td>2023–24</td>", x); self.assertIn("No jump", x); self.assertIn("20 Dec", x)
        self.assertIn("Christmas 2026: what Bowser expects", x)                          # 17 Nov is in the run-up
        for p in ("fuel-price-forecast/accuracy/", "best-day-to-buy-petrol/", "petrol-prices-christmas/"):
            self.assertIn(p, self.page("about"))                                           # in every page's footer
        with open(os.path.join(self.out, "llms.txt"), encoding="utf-8") as fh: self.assertIn("/best-day-to-buy-petrol/", fh.read())


    def test_tested_record_beside_every_call(self):
        line = ("Bowser’s Sydney Unleaded 91 call, tested on the year to 22 Oct: on average, following it would have saved about $1.18 a 50 L tank "
                "against filling up the day you check, and it was right on 72% of days (always “wait”: 48%).")
        for p in ("fuel-prices", "fuel-prices/unleaded-91", "fuel-prices/parramatta-2150", "fuel-price-forecast"):
            self.assertIn(html.escape(line), self.page(p), p)
        self.assertIn('href="../../fuel-price-forecast/accuracy/">How it’s scored</a>', self.page("fuel-prices/parramatta-2150"))
        self.assertNotIn("call, tested on", self.page("station/7-eleven-parramatta-1"))   # its advice is a different, untested rule
        self.assertNotIn("tested on the year", self.page("station/ampol-dubbo-7"))     # outside Sydney: no call, no record
        self.assertNotIn("Diesel call, tested", self.page("fuel-prices/diesel"))         # no replay for diesel in the sample
        a = self.page("fuel-price-forecast/accuracy")
        self.assertIn("Why accuracy figures differ between sites", a)


class Pieces(unittest.TestCase):
    def test_station_name(self):
        self.assertEqual(sp.station_name("APEX PETROLEUM (WEST RYDE)"), "Apex Petroleum (West Ryde)")
        self.assertEqual(sp.station_name("BP NORTH MANLY"), "BP North Manly")
        self.assertEqual(sp.station_name("Shell Reddy  Express Wattle Grove"), "Shell Reddy Express Wattle Grove")
        self.assertEqual(sp.station_name("Costco Auburn (Members only)"), "Costco Auburn")
        self.assertEqual(sp.station_name("YOGI'S PLACE SERVICE STATION"), "Yogi's Place Service Station")
        self.assertEqual(sp.station_name("O'CONNELL FUEL D'ARCY ST"), "O'Connell Fuel D'Arcy ST")
        self.assertEqual(sp.station_name("Yogi's Place"), "Yogi's Place")

    def test_slug(self):
        self.assertEqual(sp.slug("St Mary's & King’s Cross"), "st-marys-and-kings-cross")
        self.assertEqual(sp.slug("../../etc"), "etc")

    def test_home_head_and_links(self):
        stations, forecast, *_ = sample()
        head = sp.home_head(stations, forecast)
        self.assertEqual(head.count("<title>"), 1); self.assertTrue(head.startswith("<title>"))
        self.assertIn('<link rel="canonical" href="https://checkbowser.app/">', head)
        self.assertIn("Unleaded 91 is 213.6c/L (17 Nov)", head)
        self.assertIn("<title>Should you fill up today? Sydney fuel prices | Bowser</title>", head)
        self.assertIn("Should you fill up today? Bowser’s call for Sydney: wait if you can.", head)
        self.assertEqual(len(re.findall(r"<script\b", head, re.I)), 1); self.assertIn('<script type="application/ld+json">', head)
        links = sp.home_links(stations, forecast)
        self.assertIn('href="fuel-prices/parramatta-2150/"', links); self.assertNotIn("<script", links)

    def test_odd_feed_rows_dont_stop_the_build(self):
        stations, forecast, *_ = sample()
        st = stations["stations"]
        st.append(dict(st[0], id="20", n="7-Eleven Parramatta", s="PARRAMATTA", b="7-ELEVEN"))      # a second spelling, a shared name
        st.append(dict(st[0], id="21", n="A" * 300, s=None, b=None, pc=None))                         # a name too long for a folder
        st.append(dict(st[0], id="22", n=None, p={"U91": [200.0, None, None, None, None]}))           # no name, no advice
        st.append({"n": "No id", "p": {}}); st.append(dict(st[0], id="23", p={}))                     # dropped
        with tempfile.TemporaryDirectory() as out:
            r = sp.build(out, stations, forecast)
            self.assertEqual((r["stations"], r["suburbs"]), (11, 5))                                  # PARRAMATTA joined Parramatta
            titles = {}
            for d, _, fs in os.walk(out):
                for f in fs:
                    if f == "index.html":
                        with open(os.path.join(d, f), encoding="utf-8") as fh: t = re.search(r"<title>(.*?)</title>", fh.read()).group(1)
                        self.assertNotIn(t, titles, f"{d} shares a title with {titles.get(t)}"); titles[t] = d
            self.assertTrue(all(len(n) < 120 for n in os.listdir(f"{out}/station")))
            for href in re.findall(r'href="([^"]+)"', sp.home_links(stations, forecast)):
                self.assertTrue(os.path.exists(os.path.join(out, href, "index.html")), href)

    def test_country_station_without_a_region(self):
        # Nana Glen: outside every region, nothing within 4 or 10 km with three prices, a few days of history
        stations, forecast, history, details, track = sample()
        st = stations["stations"]
        for i, n, la, lo, p in [(400, "Nana Glen General Store", -30.13, 153.01, 210.0), (401, "Servo Glenreagh", -30.05, 153.00, 205.0),
                                (402, "Servo Orara", -30.20, 153.05, 208.0), (403, "Servo Far", -30.25, 153.10, 215.0)]:
            s = station(i, n, "Independent", "Nana Glen", 2450, la, lo, {"U91": (p, 0)}, out=1)
            s["p"]["U91"] = s["p"]["U91"][:2] + ["na", "Price only", "Outside Sydney, where Bowser has no forecast"]
            st.append(s)
        n = (sp.dt.date.fromisoformat(ASOF) - sp.dt.date(2025, 10, 15)).days + 1
        details["400"] = {"start": "2025-10-15", "hist": {"U91": [None] * (n - 5) + [209.0, 210.0, 211.0, 210.0, 210.0]}}
        with tempfile.TemporaryDirectory() as out:
            sp.build(out, stations, forecast, history, details, track)
            with open(os.path.join(out, "station/nana-glen-general-store-400/index.html"), encoding="utf-8") as fh: t = fh.read()
        self.assertIn("last reported its Unleaded 91 price to NSW FuelCheck today", t)
        self.assertIn("2.0c over the median of the 3 stations within 25 km (208.0c)", t)
        self.assertIn("The cheapest Unleaded 91 within 25 km", t)
        self.assertIn('Servo Orara</a>, 8.7 km away, at 208.0c (2.0c less, $1.00 on a 50 L fill)', t)
        self.assertIn("Since 13 Nov, Unleaded 91 at Nana Glen General Store has ranged from <b>209.0c</b> to <b>211.0c</b> a litre; it last changed on 16 Nov, to 210.0c.", t)
        self.assertNotIn('<svg class="chart"', t)

    def test_deals_page(self):
        stations, forecast, history, details, track = sample()
        for i, p in enumerate((210.0, 212.0, 214.0)):
            stations["stations"].append(station(500 + i, f"Reddy Express Auburn {i}", "Reddy Express", "Auburn", 2144, -33.85 + i * 0.002, 151.03, {"U91": (p, 0)}))
        with tempfile.TemporaryDirectory() as out:
            sp.build(out, stations, forecast, history, details, track)
            with open(os.path.join(out, "petrol-deals-sydney/index.html"), encoding="utf-8") as fh: t = fh.read()
            with open(os.path.join(out, "llms.txt"), encoding="utf-8") as fh: self.assertIn("/petrol-deals-sydney/", fh.read())
        self.assertIn("<title>Fuel discounts in Sydney: dockets, codes, live prices | Bowser</title>", t)
        self.assertIn('<a href="../coles-fuel-docket/">Coles docket (Flybuys)</a>', t)
        self.assertIn("CommBank Yello at BP", t)                       # runs to 31 Dec 2026; the sample's day is 17 Nov
        # Coles docket row: average 212.0, 1.6c under the 213.6 median, 208.0 after 4c; the in-store offer 202.0 after 10c
        self.assertRegex(t, r"Coles docket \(Flybuys\)</a></td><td>Reddy Express</td><td class=\"n\">4c/L</td><td class=\"n\">212\.0</td>"
                            r"<td class=\"n\"><span class=\"cheap\">−1\.6</span></td><td class=\"n\">208\.0</td>")
        self.assertIn('<td class="n">202.0</td>', t)
        self.assertIn('"@type":"FAQPage"', t); self.assertIn("a 4c docket saves <b>$2.00</b>", t)

    def test_discount_pages(self):
        stations, forecast, history, details, track = sample()
        for i, p in enumerate((210.0, 212.0, 214.0)):
            stations["stations"].append(station(500 + i, f"Reddy Express Auburn {i}", "Reddy Express", "Auburn", 2144, -33.85 + i * 0.002, 151.03, {"U91": (p, 0)}))
        with tempfile.TemporaryDirectory() as out:
            sp.build(out, stations, forecast, history, details, track)
            rd = lambda p: open(os.path.join(out, p, "index.html"), encoding="utf-8").read()
            lock, coles, wow = rd("7-eleven-fuel-price-lock"), rd("coles-fuel-docket"), rd("woolworths-fuel-discount")
        # the sample's U91 forecast falls 8.1c in a week: no rush to lock
        self.assertIn("<b>No rush to lock</b>", lock); self.assertIn("ease about 8.1c", lock); self.assertIn('"@type":"FAQPage"', lock)
        self.assertIn("7-Eleven Granville", lock)                         # the cheapest Sydney 7-Eleven
        # Coles: 212.0 average, 208.0 after 4c, 198.0 with the 10c in-store offer too
        self.assertIn("<b>212.0c</b>", coles); self.assertIn("<b>208.0c</b> after the docket, or 198.0c with the 10c in-store offer", coles)
        self.assertIn("<title>Woolworths fuel discount: today’s prices at Ampol | Bowser</title>", wow)
        # an offer past its end date disappears
        stations, forecast, history, details, track = sample()
        stations["asof"] = "2027-01-01"
        with tempfile.TemporaryDirectory() as out:
            sp.build(out, stations, forecast, history, details, track)
            with open(os.path.join(out, "petrol-deals-sydney/index.html"), encoding="utf-8") as fh: self.assertNotIn("Yello", fh.read())

    def test_lock_call(self):
        s = sp.Site(None, *sample()[:2])
        self.assertEqual(s.lock_call()[0], "No rush to lock")
        s.live["U91"]["d7"] = 6.0; self.assertEqual(s.lock_call()[0], "Lock today")
        s.live["U91"]["d7"] = 0.2; s.live["U91"]["p_jump7"] = 0.02; s.live["U91"]["verdict"]["cls"] = "flat"
        self.assertEqual(s.lock_call()[0], "Lock when you’re ready to fill")
        s.live["U91"]["p_jump7"] = 0.4; self.assertEqual(s.lock_call()[0], "Lock today")
        s.live["U91"]["d7"] = -3.0; c = s.lock_call()                     # a jump is likely though the median eases: never "rise"
        self.assertEqual(c[0], "Lock today"); self.assertNotIn("rise", c[2]); self.assertIn("about 40%", c[2])

    def test_hub_title_and_indexnow(self):
        with tempfile.TemporaryDirectory() as out:
            report = sp.build(out, *sample())
            rd = lambda p: open(os.path.join(out, p), encoding="utf-8").read()
            self.assertIn("<title>Check NSW and ACT fuel prices: cheapest petrol by suburb | Bowser</title>", rd("fuel-prices/index.html"))
            self.assertEqual(rd(f"{sp.INDEXNOW_KEY}.txt"), sp.INDEXNOW_KEY)
            with open(os.path.join(out, "sitemap.xml"), "rb") as fh: sitemap = fh.read()
        import indexnow
        old = {"https://checkbowser.app/": "2026-11-16", "https://checkbowser.app/a/": "2026-11-17", "https://checkbowser.app/gone/": "2026-11-10"}
        new = {"https://checkbowser.app/": "2026-11-17", "https://checkbowser.app/a/": "2026-11-17", "https://checkbowser.app/b/": "2026-11-17",
               "https://elsewhere.example/": "2026-11-17"}
        self.assertEqual(indexnow.changed(old, new), ["https://checkbowser.app/", "https://checkbowser.app/b/", "https://checkbowser.app/gone/"])
        b = indexnow.body(["https://checkbowser.app/"])
        self.assertEqual((b["host"], b["keyLocation"]), ("checkbowser.app", f"https://checkbowser.app/{sp.INDEXNOW_KEY}.txt"))
        parsed = indexnow.parse(sitemap)
        self.assertEqual(parsed["https://checkbowser.app/"], ASOF); self.assertEqual(len(parsed), report["pages"] + 1)

    def test_act_and_outside_sydney_wording_and_freshness(self):
        stations, forecast, *_ = sample()
        st = stations["stations"]
        na = ["na", "Price only", "Outside Sydney: prices only, no forecast"]
        # Hume ACT 2620: the postcode is NSW by range (Queanbeyan), so the state comes from `st`
        for i, (age, sid) in enumerate([(0, 501), (12, 502)]):
            s = station(sid, f"Servo Hume {i}", "Ampol", "Hume", 2620, -35.39 + i * 0.002, 149.166, {"U91": (201.0 - 2 * i, age)}, out=1, st="ACT")
            s["p"]["U91"] = s["p"]["U91"][:2] + na; st.append(s)
        old = station(503, "Servo Hume Old", "Ampol", "Hume", 2620, -35.394, 149.166, {"U91": (190.0, 21)}, out=1, st="ACT")
        old["p"]["U91"] = old["p"]["U91"][:2] + ["chk", "Check price", "Not updated for 21 days"]; st.append(old)
        details = {"502": {"start": ASOF, "addr": "94-96 Sheppard St, Hume ACT 2620", "hist": {}}}
        with tempfile.TemporaryDirectory() as out:
            sp.build(out, stations, forecast, details=details)
            rd = lambda p: open(os.path.join(out, p), encoding="utf-8").read()
            sub = rd("fuel-prices/hume-2620/index.html")
            self.assertIn("Petrol prices in Hume, Canberra ACT 2620", sub); self.assertIn("Service stations in Hume ACT 2620", sub)
            self.assertNotIn("must report", sub); self.assertNotIn("adds a forecast", sub); self.assertNotIn('class="verdict', sub)
            self.assertIn("ACT service stations that report to it", sub)
            # 12 days old outside Sydney: current, shown as unchanged since its day; 21 days: old, and out of the cheapest
            self.assertIn("unchanged since 5 Nov", sub); self.assertIn("21 days old", sub)
            self.assertRegex(sub, r"The cheapest Unleaded 91 in Hume today is <b>199.0c/L</b> at <a [^>]+>Servo Hume 1</a> \(unchanged since 5 Nov\)\.")
            page = rd("station/servo-hume-1-502/index.html")
            self.assertIn('"addressRegion":"ACT"', page); self.assertIn('"streetAddress":"94-96 Sheppard St"', page)
            self.assertIn("Unchanged since 5 Nov", page); self.assertNotIn("check it before you drive", page)
            self.assertIn("check it before you drive", rd("station/servo-hume-old-503/index.html"))
            dubbo = rd("fuel-prices/dubbo-2830/index.html")
            self.assertIn("Petrol prices in Dubbo NSW 2830", dubbo); self.assertNotIn("adds a forecast", dubbo)
            self.assertIn("covers Sydney only", dubbo)
            hub = rd("fuel-prices/index.html")
            self.assertIn("across NSW and the ACT", hub); self.assertNotIn("every service station in the state", hub)
            self.assertIn("All NSW and ACT service stations", rd("station/index.html"))
        self.assertEqual((sp.state_of(2620), sp.state_of(2620, "ACT"), sp.state_of(2600), sp.state_of(2150, None)), ("NSW", "ACT", "ACT", "NSW"))
        s20 = {"out": 1, "p": {"U91": [200.0, 20]}}; s21 = {"out": 1, "p": {"U91": [200.0, 21]}}; syd8 = {"p": {"U91": [200.0, 8]}}
        self.assertEqual((sp.Site.fresh(s20, "U91"), sp.Site.fresh(s21, "U91"), sp.Site.fresh(syd8, "U91")), (True, False, False))

    def test_canberra_page_hub_and_act_station_links(self):
        stations, forecast, *_ = sample()
        st = stations["stations"]
        na = ["na", "Price only", "Outside Sydney: prices only, no forecast"]
        # (id, name, suburb, postcode, U91, lat, lon, st): ACT stations in three districts, and Queanbeyan (NSW) over the border
        rows = [(601, "Ampol Belconnen", "Belconnen", 2617, 221.9, -35.238, 149.066, "ACT"), (602, "Shell Belconnen", "Belconnen", 2617, 223.9, -35.239, 149.067, "ACT"),
                (603, "BP Kambah", "Kambah", 2902, 219.9, -35.381, 149.058, "ACT"), (604, "7-Eleven Greenway", "Greenway", 2900, 218.9, -35.418, 149.066, "ACT"),
                (605, "Costco Canberra Airport", "Majura", 2609, 205.9, -35.305, 149.192, "ACT"), (606, "Servo Hume", "Hume", 2620, 214.9, -35.390, 149.166, "ACT"),
                (607, "Metro Queanbeyan", "Queanbeyan", 2620, 209.9, -35.353, 149.232, None), (608, "Ampol Queanbeyan", "Queanbeyan", 2620, 211.9, -35.354, 149.233, None),
                (609, "BP Queanbeyan East", "Queanbeyan East", 2620, 212.9, -35.349, 149.240, None)]
        for i, n, sub, pc, u, la, lo, state in rows:
            s = station(i, n, "Costco" if i == 605 else "Ampol", sub, pc, la, lo, {"U91": (u, 0)}, out=1, **({"st": state} if state else {}))
            s["p"]["U91"] = s["p"]["U91"][:2] + na; st.append(s)
        st.append(station(610, "Costco Casula (Members only)", "Costco", "Casula", 2170, -33.95, 150.9, {"P98": (219.9, 0), "E10": (199.9, 0)})); st[-1]["m"] = 1
        with tempfile.TemporaryDirectory() as out:
            sp.build(out, stations, forecast)
            rd = lambda p: open(os.path.join(out, p), encoding="utf-8").read()
            cbr = rd("fuel-prices/canberra-and-queanbeyan/index.html")
            title = re.search(r"<title>(.*?)</title>", cbr).group(1)
            desc = html.unescape(re.search(r'<meta name="description" content="(.*?)">', cbr).group(1))
            self.assertEqual(title, "Canberra fuel prices today: U91 from 205.9c | Bowser"); self.assertLessEqual(len(title), 65)
            self.assertTrue(desc.startswith("Canberra petrol prices for 17 Nov: U91 from 205.9c at Costco Canberra Airport, median 214.9c (1.3c over Sydney)"), desc)   # the short fuel name makes room for the station
            self.assertIn("over Sydney)", desc); self.assertIn("9 ACT and Queanbeyan stations compared", desc); self.assertLessEqual(len(desc), 155)
            self.assertIn("<h1>Canberra and Queanbeyan fuel prices today</h1>", cbr)
            # districts (Hume ACT 2620 joins Fyshwick; Queanbeyan is the NSW side), the ACT vs Queanbeyan medians, the honest FAQ
            for d in ("belconnen", "tuggeranong", "fyshwick-hume-and-the-airport", "queanbeyan-and-surrounds-nsw"): self.assertIn(f'id="{d}"', cbr)
            fy = cbr[cbr.index('id="fyshwick-hume-and-the-airport"'):cbr.index('id="queanbeyan-and-surrounds-nsw"')]
            self.assertIn("Servo Hume", fy); self.assertNotIn("Queanbeyan</a>", fy)
            self.assertIn("ACT stations’ median Unleaded 91 today is 219.4c; across the border in Queanbeyan and surrounds (NSW) it is 211.9c, 7.5c less", cbr)
            self.assertIn("Does Bowser forecast Canberra prices?", cbr); self.assertIn("covers Sydney only", cbr)
            self.assertIn('"@type":"FAQPage"', cbr); self.assertIn('"@type":"ItemList"', cbr)
            self.assertNotIn('class="verdict', cbr); self.assertNotIn("Fill up today", cbr)
            self.assertIn("<loc>https://checkbowser.app/fuel-prices/canberra-and-queanbeyan/</loc><lastmod>2026-11-17</lastmod><priority>0.9</priority>", rd("sitemap.xml"))
            self.assertFalse(os.path.exists(os.path.join(out, "fuel-prices", "canberra"))); self.assertFalse(os.path.exists(os.path.join(out, "fuel-prices", "act")))
            # hub: both states served, the Canberra block and its link, no Canberra forecast
            hub = rd("fuel-prices/index.html")
            ds = next(b for b in (json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', hub)) if b.get("@type") == "Dataset")
            self.assertEqual([a["name"] for a in ds["creator"]["areaServed"]], ["New South Wales", "Australian Capital Territory"])
            self.assertIn("Australian Capital Territory", ds["spatialCoverage"])
            self.assertIn('<h2 id="canberra">', hub); self.assertIn('href="../fuel-prices/canberra-and-queanbeyan/"', hub)
            self.assertIn("<h2>Fuel prices outside Sydney (NSW and ACT)</h2>", hub); self.assertIn("Does Bowser forecast Canberra prices?", hub)
            hub_desc = html.unescape(re.search(r'<meta name="description" content="(.*?)">', hub).group(1))
            self.assertTrue(hub_desc.startswith("NSW and ACT petrol prices for 17 Nov: Sydney Unleaded 91 median 213.6c/L"), hub_desc); self.assertLessEqual(len(hub_desc), 155)
            # ACT and Queanbeyan stations: "cheapest" goes to the Canberra page, never Sydney's; a Sydney station keeps Sydney's
            for p in ("station/ampol-belconnen-601/index.html", "station/metro-queanbeyan-607/index.html"):
                page = rd(p)
                self.assertIn('<a href="../../fuel-prices/canberra-and-queanbeyan/">Cheapest Unleaded 91 in Canberra today</a>', page)
                self.assertNotIn("in Sydney today</a>", page); self.assertIn('"name":"Canberra","item":"https://checkbowser.app/fuel-prices/canberra-and-queanbeyan/"', page)
            self.assertIn("Cheapest Unleaded 91 in Sydney today</a>", rd("station/7-eleven-granville-3/index.html"))
            self.assertIn('href="../../fuel-prices/unleaded-91/">Cheapest', rd("station/ampol-dubbo-7/index.html"))
            # llms.txt and the footer: coverage wording, forecast for Sydney only, an ACT example from the data
            llms = rd("llms.txt")
            self.assertIn("New South Wales and the Australian Capital Territory, Australia", llms); self.assertIn("(including 6 ACT stations that report to NSW FuelCheck)", llms)
            self.assertIn("a forecast for Sydney only", llms); self.assertIn("## Regions outside Sydney (NSW and ACT; prices only, no forecast)", llms)
            self.assertIn("or in the ACT https://checkbowser.app/fuel-prices/belconnen-2617/", llms)
            self.assertIn(">NSW and ACT fuel prices</a>", cbr)
            # ACT suburb pages: "Canberra" in the description when it fits, and a link to their district's section
            bel = rd("fuel-prices/belconnen-2617/index.html")
            self.assertIn("Petrol prices in Belconnen, Canberra ACT 2617 for 17 Nov", bel)
            self.assertIn('href="../../fuel-prices/canberra-and-queanbeyan/#belconnen">Belconnen on the Canberra page</a>', bel)
            self.assertNotIn("#queanbeyan", rd("fuel-prices/queanbeyan-2620/index.html"))
            # the Canberra Costco's U91, from the data, on the Costco brand page
            self.assertIn('Costco Canberra Airport</a> in the ACT also sells Unleaded 91: 205.9c/L today', rd("brands/costco/index.html"))
        head = sp.home_head(stations, forecast)
        self.assertIn('"areaServed":[{"@type":"State","name":"New South Wales"},{"@type":"State","name":"Australian Capital Territory"}]', head)
        hd = html.unescape(re.search(r'<meta name="description" content="(.*?)">', head).group(1))
        self.assertIn("with today’s prices at 18 NSW and ACT stations.", hd); self.assertLessEqual(len(hd), 155)
        self.assertIn("<title>Should you fill up today? Sydney fuel prices | Bowser</title>", head)
        # every call the pipeline can make (export_api.py), with a 4-digit station count: the descriptions stay within 155
        many = {"asof": ASOF, "stations": [dict(st[0], id=str(5000 + i)) for i in range(2381)] + [next(x for x in st if x.get("out"))]}
        for v in ("Fill up today", "Fill up this week", "Wait if you can", "No rush either way"):
            fc = json.loads(json.dumps(forecast)); fc["live"][0]["verdict"]["head"] = v
            hd = html.unescape(re.search(r'<meta name="description" content="(.*?)">', sp.home_head(many, fc)).group(1))
            self.assertLessEqual(len(hd), 155, hd); self.assertIn("2,382 NSW and ACT stations", hd)

    def test_dashboard_rows_compare_with_their_own_market(self):
        # template.html: the list row and the map card compare with the station's own market (marketFor): the Sydney
        # median only for Sydney stations, the region's (local_median.py) outside Sydney, else nothing (2026-11-24)
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html"), encoding="utf-8") as fh: t = fh.read()
        mk = t[t.index("function marketFor("):t.index("function stationItem(")]
        item = t[t.index("function stationItem("):t.index("function brandOptions(")]
        pop = t[t.index("function openPop("):t.index("function openNoFuel(")]
        self.assertIn('if (!s.out) return med != null ? {med, name: "Sydney"} : null;', mk)   # Sydney's median: Sydney stations only
        self.assertIn("D.regions[s.rg]", mk)
        self.assertIn("gap = mk ? s.price - mk.med : null", item); self.assertIn("gap = mk ? r.price - mk.med : null", pop)
        for part in (item, pop): self.assertIn('${gap == null ? "" :', part)

    def test_regions_dead_pages_and_ai_files(self):
        stations, forecast, *_ = sample()
        st = stations["stations"]
        for i in range(6):                                        # six stations around Newcastle, outside Sydney
            s = station(100 + i, f"Servo Newcastle {i}", "Lowes", "Hamilton", 2303, -32.92 + i * 0.01, 151.75, {"U91": (220.0 + i, 0), "DL": (260.0 + i, 0)}, out=1)
            for f in s["p"]: s["p"][f] = s["p"][f][:2] + ["na", "Price only", "Outside Sydney, where Bowser has no forecast"]
            st.append(s)
        st.append(station(300, "Ampol Newcastle West", "Ampol", "Newcastle", 2302, -32.925, 151.76, {"U91": (225.0, 3)}, out=1))   # a suburb named like a region
        st.append(station(200, "Closed Servo", "Independent", "Tibooburra", 2880, -29.43, 142.01, {"U91": (250.0, 45)}, out=1))   # nothing for 45 days
        with tempfile.TemporaryDirectory() as out:
            r = sp.build(out, stations, forecast)
            self.assertEqual(r["regions"], 1)
            rd = lambda p: open(os.path.join(out, p), encoding="utf-8").read()
            sub = rd("fuel-prices/newcastle-2302/index.html")
            self.assertIn("<h1>Newcastle 2302 fuel prices today</h1>", sub); self.assertIn('href="../../fuel-prices/newcastle/"', sub)
            titles = {}
            for d, _, fs in os.walk(out):
                if "index.html" in fs:
                    with open(os.path.join(d, "index.html"), encoding="utf-8") as fh: ti = re.search(r"<title>(.*?)</title>", fh.read()).group(1)
                    self.assertNotIn(ti, titles, f"{d} and {titles.get(ti)}"); titles[ti] = d
            reg = rd("fuel-prices/newcastle/index.html")
            self.assertIn("<h1>Newcastle fuel prices today</h1>", reg); self.assertIn("<b>220.0c/L</b>", reg)
            self.assertIn("median across 7 stations with a current price is 223.0c", reg); self.assertNotIn('class="verdict', reg)
            self.assertIn('href="../../fuel-prices/hamilton-2303/"', reg)
            hub = rd("fuel-prices/index.html")
            self.assertIn("<h1>NSW and ACT fuel prices today</h1>", hub); self.assertIn('href="../fuel-prices/newcastle/"', hub)
            self.assertIn('"@type":"FAQPage"', hub); self.assertIn("What is the cheapest petrol in Sydney today?", hub)
            self.assertIn("the Newcastle median of 223.0c", rd("station/servo-newcastle-0-100/index.html"))
            self.assertIn('href="../../fuel-prices/newcastle/"', rd("fuel-prices/unleaded-91/index.html"))
            # a station silent for over a month keeps its page, but out of search and out of the sitemap
            dead, sm = rd("station/closed-servo-200/index.html"), rd("sitemap.xml")
            self.assertIn('<meta name="robots" content="noindex">', dead); self.assertNotIn('rel="canonical"', dead)
            self.assertNotIn("closed-servo-200", sm); self.assertNotIn("tibooburra-2880", sm); self.assertIn("fuel-prices/newcastle/", sm)
            # outside Sydney a page's lastmod is the day its newest price was reported; region and Sydney pages change daily
            lm = lambda path: re.search(re.escape(path) + r"</loc><lastmod>([\d-]+)<", sm).group(1)
            three = (sp.dt.date.fromisoformat(ASOF) - sp.dt.timedelta(days=3)).isoformat()
            self.assertEqual(lm("station/ampol-newcastle-west-300/"), three); self.assertEqual(lm("fuel-prices/newcastle-2302/"), three)
            self.assertEqual(lm("station/servo-newcastle-0-100/"), ASOF); self.assertEqual(lm("fuel-prices/newcastle/"), ASOF)
            robots = rd("robots.txt")
            for bot in ("GPTBot", "OAI-SearchBot", "ClaudeBot", "PerplexityBot", "Google-Extended"): self.assertIn(f"User-agent: {bot}\n", robots)
            self.assertEqual(robots.count("Disallow:"), 2); self.assertNotIn("Disallow: /\n", robots)
            llms = rd("llms.txt")
            self.assertTrue(llms.startswith("# Bowser\n")); self.assertIn("Sydney Unleaded 91: median 213.6 cents per litre", llms)
            self.assertIn("(https://checkbowser.app/fuel-prices/newcastle/)", llms); self.assertNotIn("<", llms)
            sp.clear(out); self.assertEqual(os.listdir(out), [])

    def test_home_links_carry_todays_numbers_as_text(self):
        stations, forecast, *_ = sample()
        links = sp.home_links(stations, forecast)
        self.assertIn("Sydney fuel prices on Tuesday 17 November 2026", links); self.assertIn("Unleaded 91 213.6c/L (cheapest 199.9c at 7-Eleven Granville)", links)
        self.assertIn("Wait if you can", links)

    def test_bad_input_raises_and_clear_removes(self):
        stations, forecast, *_ = sample()
        with tempfile.TemporaryDirectory() as out:
            sp.build(out, stations, forecast)                     # works without history, station files or a track record
            self.assertTrue(os.path.exists(f"{out}/sitemap.xml"))
            with self.assertRaises(Exception): sp.build(out, {"asof": ASOF, "stations": []}, forecast)
            sp.clear(out)
            self.assertEqual(os.listdir(out), [])


if __name__ == "__main__":
    unittest.main()
