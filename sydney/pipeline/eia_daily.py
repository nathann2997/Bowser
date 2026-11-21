"""Parser for EIA's "Today in Energy" daily prices page (fetch.py pull_eia_daily): the previous US close for Brent and
NY Harbor diesel, each US weekday morning except federal holidays. EIA's history files (fetch.py pull_macro) only gain
a week's rows each Wednesday (US), so live Brent was 2-8 days old (5.4 on average) while the model assumed 1. Same
series, same publisher as the history files (checked value for value, docs/MODEL_INPUTS_2026-11.md), so those stay the
record and this only fills the days after them. No network or pandas here, so test_eia_daily.py runs on a saved snippet.
"""
import datetime as dt, html, re

_text = lambda cell: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", cell))).strip()


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
