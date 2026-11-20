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
                                "recent": {"n": 342, "right": 247, "close": 42, "wrong": 53, "from": "2025-10-23", "to": "2026-10-22", "base": {"cls": "down", "right": 164}}}},
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
        self.assertIn("will petrol go up or down next week?</h1>", f)
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
        self.assertIn("Unleaded 91 is 213.6c/L in Sydney today (17 Nov)", head)
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
            self.assertIn("<h1>NSW fuel prices today</h1>", hub); self.assertIn('href="../fuel-prices/newcastle/"', hub)
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
