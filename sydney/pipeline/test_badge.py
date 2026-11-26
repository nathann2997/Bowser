"""Tests for the embeddable cycle-stage badge (seo_pages.badge_svg / write_badge) and its /badge/ page, on made-up data."""
import copy, html, os, re, sys, tempfile, unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo_pages as sp
from test_seo_pages import sample

NS = "{http://www.w3.org/2000/svg}"


def texts(svg):
    root = ET.fromstring(svg)   # well-formed XML, or this raises
    return root, " ".join("".join(t.itertext()) for t in root.iter(f"{NS}text"))


class Badge(unittest.TestCase):
    def setUp(self):
        _, self.fc, *_ = sample()

    def test_stage_and_day(self):
        root, t = texts(sp.badge_svg(self.fc))
        st = sp.cycle_stage(self.fc["stats"], self.fc["asof"], {r["fuel"]: r for r in self.fc["live"]})
        self.assertIn(st[2], t)
        self.assertIn(f"Day {st[0]} since the last jump · {sp.short_date(self.fc['asof'])}", t)
        self.assertIn("Data: NSW FuelCheck", t)
        self.assertEqual(root.get("width"), str(sp.BADGE_W))
        self.assertTrue(root.find(f"{NS}title").text.startswith("Sydney petrol price cycle"))
        self.assertNotIn("<script", sp.badge_svg(self.fc)); self.assertNotIn("href", sp.badge_svg(self.fc))

    def test_jump_likely_matches_the_cycle_page(self):
        fc = copy.deepcopy(self.fc)
        next(r for r in fc["live"] if r["fuel"] == "U91")["p_jump7"] = sp.JUMP_LIKELY
        self.assertIn("A jump looks likely soon", texts(sp.badge_svg(fc))[1])

    def test_without_a_stage_the_u91_call_and_it_is_escaped(self):
        fc = copy.deepcopy(self.fc); fc["stats"] = {}
        u = next(r for r in fc["live"] if r["fuel"] == "U91")
        u["verdict"] = {"cls": "up", "head": '<script>alert(1)</script> & "Fill"'}
        svg = sp.badge_svg(fc)
        self.assertNotIn("<script>", svg)
        self.assertIn("Bowser’s call for Unleaded 91", texts(svg)[1])
        self.assertIn('<script>alert(1)</script> & "Fill"'[:40], texts(svg)[1])

    def test_jump_day_and_a_long_call(self):
        fc = copy.deepcopy(self.fc); fc["stats"]["last_restore"] = fc["asof"]
        self.assertIn("A jump began today", texts(sp.badge_svg(fc))[1])
        fc["stats"] = {}
        next(r for r in fc["live"] if r["fuel"] == "U91")["verdict"] = {"cls": "flat", "head": "No rush to fill up today and no rush tomorrow either"}
        self.assertIn("No rush to fill up today and no rush…", texts(sp.badge_svg(fc))[1])

    def test_fallbacks(self):
        self.assertEqual(sp.badge_svg({"live": [], "stats": {}}), sp.BADGE_FALLBACK)
        texts(sp.BADGE_FALLBACK)
        with tempfile.TemporaryDirectory() as o:
            self.assertFalse(sp.write_badge(o, None))          # broken input: the plain badge, still written
            with open(os.path.join(o, sp.BADGE_PATH), encoding="utf-8") as fh: self.assertEqual(fh.read(), sp.BADGE_FALLBACK)
            self.assertTrue(sp.write_badge(o, self.fc))

    def test_a_long_head_is_narrowed_to_fit(self):
        root, _ = texts(sp._badge("W" * 40, "x", "act", "t"))
        head = [t for t in root.iter(f"{NS}text")][1]
        self.assertEqual(head.get("textLength"), str(sp.BADGE_W - 78))


class Page(unittest.TestCase):
    def test_page_snippet_sitemap_and_links(self):
        with tempfile.TemporaryDirectory() as o:
            sp.build(o, *sample())
            with open(os.path.join(o, "badge", "index.html"), encoding="utf-8") as fh: p = fh.read()
            code = html.unescape(re.search(r"<pre><code>(.*?)</code></pre>", p, re.S).group(1))
            self.assertIn('<img src="https://checkbowser.app/badge/sydney.svg"', code)
            self.assertIn('href="https://checkbowser.app/petrol-price-cycle/"', code)
            self.assertNotIn("<img src=\"https://checkbowser.app/badge", p.split("<pre>")[1].split("</pre>")[0])   # shown as text
            self.assertNotIn("style=", p)                                                  # the CSP allows no inline style
            with open(os.path.join(o, "sitemap-pages.xml")) as fh: self.assertIn("/badge/</loc>", fh.read())
            with open(os.path.join(o, "llms.txt")) as fh: self.assertIn("/badge/", fh.read())
            with open(os.path.join(o, "petrol-price-cycle", "index.html"), encoding="utf-8") as fh: self.assertIn('href="../badge/"', fh.read())
            # export_api writes the image after the pages; a later clear() removes the page (and the image with it)
            sp.write_badge(o, sample()[1]); self.assertTrue(os.path.exists(os.path.join(o, sp.BADGE_PATH)))
            sp.clear(o); self.assertFalse(os.path.exists(os.path.join(o, "badge")))


if __name__ == "__main__":
    unittest.main()
