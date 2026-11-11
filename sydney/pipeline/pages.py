"""Parsers for the two daily web pages that keep wholesale and oil prices fresh between the weekly files (fetch.py).

  AIP terminal gate prices page   the last five business days of TGP ("collated each weekday morning", so today's
                                  appears during the morning);
                                  the AIP workbook only gains a week's rows each Friday
  EIA Today in Energy daily prices   the previous US close for Brent and NY Harbor diesel, each US weekday morning
                                  except federal holidays;
                                  EIA's history files only gain a week's rows each Wednesday (US)
Both are the same series, from the same publishers, as the weekly files (checked value for value on the days they
share, docs/MODEL_INPUTS_2026-11.md), so the weekly files stay the record and these only fill the days after them.
No network or pandas here, so the tests (test_pages.py) run on saved snippets.
"""
import datetime as dt, html, re

MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                           "september", "october", "november", "december"])}
_text = lambda cell: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", cell))).strip()


def parse_aip_tgp(page, city="Sydney"):
    """{date: {"tgp_ulp": c/L, "tgp_dl": c/L}} from the AIP page: the first table is petrol, the second diesel."""
    found = list(re.finditer(r"<table.*?</table>", page, flags=re.S | re.I))
    if len(found) < 2: raise ValueError(f"AIP page: expected a petrol and a diesel table, found {len(found)}")
    out, prev_end = {}, 0
    for (col, word), m in zip([("tgp_ulp", "petrol"), ("tgp_dl", "diesel")], found[:2]):
        tb = m.group(0)
        # the heading sits just before its table ("Petrol (ULP, cents per litre...)"): a reordered page must not swap the fuels
        if word not in _text(page[prev_end:m.start()])[-200:].lower(): raise ValueError(f"AIP page: no '{word}' heading before its table")
        prev_end = m.end()
        rows = [[_text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, flags=re.S | re.I)]
                for r in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, flags=re.S | re.I)]
        head = next((r for r in rows if r and r[0].lower().startswith("location")), None)
        vals = next((r for r in rows if r and r[0].lower() == city.lower()), None)
        if not head or not vals or len(head) != len(vals): raise ValueError(f"AIP page: no dated {city} row in the {col} table")
        for h, v in zip(head[1:], vals[1:]):
            m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})", h)
            if not m or m.group(2).lower() not in MONTHS: raise ValueError(f"AIP page: unreadable date {h!r}")
            day = dt.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
            try: price = float(v)
            except ValueError: continue          # a blank cell: that day isn't collated yet
            if not 50 < price < 600: raise ValueError(f"AIP page: implausible {col} {price} on {day}")
            out.setdefault(day, {})[col] = price
    if not out: raise ValueError("AIP page: no prices")
    return out


EIA_ROWS = {("crude oil", "brent"): "DCOILBRENTEU", ("low-sulfur diesel", "ny harbor"): "ULSD_NYH"}   # store/fred.csv columns
EIA_RANGE = {"DCOILBRENTEU": (20, 400), "ULSD_NYH": (0.5, 15)}      # USD/bbl, USD/gal: the bounds pull_macro uses


def parse_eia_daily(page):
    """(close date, {"DCOILBRENTEU": USD/bbl, "ULSD_NYH": USD/gal}) from the 'Wholesale Spot Petroleum Prices' table.
    A product missing from the page is left out; Brent missing is an error (it is the reason for the pull)."""
    m = re.search(r"Wholesale Spot Petroleum Prices,\s*(\d{1,2})/(\d{1,2})/(\d{2})\s*Close", page)
    if not m: raise ValueError("EIA page: no 'Wholesale Spot Petroleum Prices, m/d/yy Close' heading")
    day = dt.date(2000 + int(m.group(3)), int(m.group(1)), int(m.group(2)))
    body = page[m.end():]
    end = body.find("</table>")
    if end > 0: body = body[:end]
    out, group = {}, None
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.S | re.I):
        cells = [(c, _text(x)) for c, x in re.findall(r'<td class="(\w+)"[^>]*>(.*?)</td>', r, flags=re.S | re.I)]
        for c, x in cells:
            if c == "s1": group = x.split("(")[0].strip().lower()      # "Crude Oil ($/barrel)" spans the rows below it
        area = next((x for c, x in cells if c == "s2"), None); val = next((x for c, x in cells if c == "d1"), None)
        col = EIA_ROWS.get((group, (area or "").lower()))
        if not col or val is None: continue
        try: v = float(val)
        except ValueError: continue              # "NA": not available when EIA built the page
        lo, hi = EIA_RANGE[col]
        if not lo < v < hi: raise ValueError(f"EIA page: implausible {col} {v}")
        out[col] = v
    if "DCOILBRENTEU" not in out: raise ValueError("EIA page: no Brent price")
    return day, out
