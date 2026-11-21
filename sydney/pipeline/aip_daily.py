"""Sydney terminal gate prices from AIP's daily TGP page (fetch.py saves it as inbox/aip_tgp_page.html).

AIP's historical workbook, the TGP source since the start, only comes out weekly, so the live forecast ran on TGP up to
6 days old (0-6, about 3 on average, 2026-10-26 to 11-20), while the model was trained and tested on TGP a day old
(docs/RULE_ANALYSIS_2026-10.md, 2026-11-21: seeing TGP 7 days late cost 0.15-0.27 c/L a call in 2026). The daily page
lists this week's prices, Monday to Friday, with the same Sydney figures as the workbook (checked for 16-20 Nov 2026).
update.py keeps them in store/tgp_daily.csv and adds the days after the workbook's last to store/tgp.csv.
"""
import datetime as dt, html, re
from zoneinfo import ZoneInfo

import pandas as pd

SECTIONS = {"tgp_ulp": ("Petrol", "sydneyulp"), "tgp_dl": ("Diesel", "sydneydiesel")}   # heading, Sydney link's end
MAX_AGE = 14   # days: a header date older than this, or after today, is a misprint, not a price to store


def _cells(row, tag):
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", c))).strip()
            for c in re.findall(rf"<{tag}[^>]*>(.*?)</{tag}>", row, re.S | re.I)]


def _date(text):
    """'Monday, 16th November 2026' -> date"""
    t = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", text.split(",", 1)[-1].strip())
    return dt.datetime.strptime(t, "%d %B %Y").date()


def parse(page, today=None):
    """DataFrame indexed by date with tgp_ulp and tgp_dl (c/L, Sydney). Raises if a section or the Sydney row is
    missing or a price is implausible, so a changed page fails loudly instead of feeding the model a wrong number."""
    cols = {}
    today = today or dt.datetime.now(ZoneInfo("Australia/Sydney")).date()
    for col, (word, link) in SECTIONS.items():
        # the table between this section's heading and the next heading, so a missing table can't borrow the next one
        m = re.search(rf"<h2[^>]*>\s*{word}\b.*?</h2>((?:(?!<h2).)*?<table.*?</table>)", page, re.S | re.I)
        if not m: raise ValueError(f"no {word} table")
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S | re.I)
        dates = [_date(h) for h in _cells(rows[0], "th")[1:]] if rows else []
        if not dates: raise ValueError(f"no dates in the {word} table header")
        row = next((r for r in rows[1:] if re.search(rf'href="[^"]*/{link}"', r, re.I)), None)
        syd = _cells(row, "td") if row else None
        if not syd or syd[0].lower() != "sydney": raise ValueError(f"no Sydney row in the {word} table")
        if len(syd) - 1 != len(dates): raise ValueError(f"{word}: {len(syd) - 1} Sydney prices for {len(dates)} dates")
        vals = {}
        for d, v in zip(dates, syd[1:]):
            if v in ("", "-", "–"): continue    # not published yet
            x = float(v)                          # anything else that isn't a number fails loudly
            if not 50 < x < 500: raise ValueError(f"{word} {d}: implausible {x}")
            if not 0 <= (today - d).days <= MAX_AGE: raise ValueError(f"{word}: date {d} is not within {MAX_AGE} days of {today}")
            vals[pd.Timestamp(d)] = x
        cols[col] = pd.Series(vals, dtype=float)
    if len(cols["tgp_ulp"]) and cols["tgp_ulp"].equals(cols["tgp_dl"]): raise ValueError("petrol and diesel rows are identical")
    out = pd.DataFrame(cols).sort_index()
    out.index.name = "date"
    return out.dropna()   # a day goes in with both fuels or not at all, so a later read can still complete it


def merge(tgp, daily):
    """`tgp` (the workbook's series) with the days of `daily` after its last date added. The workbook always wins on
    a day it has, so a day is only ever filled in early, never revised away from AIP's own history."""
    last = tgp.dropna(how="all").index.max()
    extra = daily[daily.index > last] if pd.notna(last) else daily
    return pd.concat([tgp, extra[tgp.columns.intersection(extra.columns)]]).sort_index() if len(extra) else tgp
