"""Station mean reversion: how much of a station's gap from its usual premium closes by itself, h days on.

Used by station_profile.py (builds the table into station_profile.json `revert`) and station_api.py (adds it to a
Sydney station's forecast). Tested in station_experiment.py (run 44900730135, 2026-11-21): against today's station
forecast it cut the 14-day error for stations 8c+ above their usual premium from 16.0 to 8.9c, and overall 7.65 -> 6.42.

  x0   = (station price - Sydney median) - typ, typ = the station's median premium (station_profile.py)
  y_h  = station move over h days - w * (Sydney median move over max(h - s, 0) days): the part of the station's move
         that the Sydney path, damped by w and shifted by s days (w_s below), doesn't explain
The table holds, per horizon h and x0 bin, the median y_h (median: the forecast is judged on absolute error). Only
station-days updated within FRESH days at both t and t + h count, |x| over SLIP c at either end is a price slip, and a
bin with under MIN_ROWS rows gets 0. Fuels are pooled.
"""
import numpy as np, pandas as pd

EDGES = [-10, -6, -3, -1, 1, 3, 6, 8, 12]   # bins (-inf, -10], (-10, -6], ..., (8, 12], (12, inf): right-inclusive, as pd.cut
HZ = [1, 3, 7, 14]
FRESH, SLIP, MIN_ROWS = 10, 40, 200


def w_s(p, part_med, lag_med):
    """A station's damping w (its share of price-jump waves against the median station's, capped at 1; 1 without a
    reliable profile) and shift s in days (from its lag, clipped to -1..2), as station_api.py and advise() use them."""
    p = p or {}
    w = 1.0 if p.get("n", 0) < 5 or p.get("part") is None else float(np.clip(p["part"] / part_med, 0, 1))
    s = 0 if p.get("lag") is None else int(np.clip(round((p["lag"] - lag_med) / 24), -1, 2))
    return w, s


def bin_of(x0, edges=EDGES):
    """Index of x0's bin: i such that edges[i-1] < x0 <= edges[i] (so 8.0 is in (6, 8], like pd.cut)."""
    return int(np.searchsorted(edges, x0, side="left"))


def rows(raw, med, typ, ws, since=None):
    """Training rows (x0, y, h) for one fuel.
    raw   end-of-day price per day (index, daily and complete) x station key, NaN where the station had no change/price
    med   Sydney median per day (same index); typ: Series key -> usual premium; ws: dict key -> (w, s)
    since rows from this day on (t, the forecast day)"""
    days = raw.index
    keys = [k for k in raw.columns if k in typ.index and pd.notna(typ[k]) and k in ws]
    raw = raw[keys]
    M = raw.ffill(limit=30)
    seen = pd.DataFrame(np.where(raw.notna(), days.values[:, None], np.datetime64("NaT", "ns")), index=days, columns=keys).ffill()
    age = (np.asarray(days.values)[:, None] - seen.values) / np.timedelta64(1, "D")
    fresh = pd.DataFrame(age <= FRESH, index=days, columns=keys)        # NaT compares False
    x = M.sub(med, axis=0).sub(typ[keys], axis=1).where(fresh)
    x = x.where(x.abs() <= SLIP)
    out = []
    for h in HZ:
        y = pd.DataFrame(np.nan, index=days, columns=keys)
        for s in (-1, 0, 1, 2):
            ks = [k for k in keys if ws[k][1] == s]
            if not ks: continue
            w = np.array([ws[k][0] for k in ks])
            dmed = med.shift(-max(h - s, 0)) - med
            y[ks] = (M[ks].shift(-h) - M[ks]).values - np.outer(dmed.values, w)
        y = y.where(x.notna() & x.shift(-h).notna())
        r = pd.DataFrame({"x0": x.stack(), "y": y.stack()}).dropna()
        r["date"] = r.index.get_level_values(0)
        if since is not None: r = r[r.date >= since]
        out.append(r.reset_index(drop=True).assign(h=h)[["x0", "y", "h"]])
    return pd.concat(out, ignore_index=True)


def table(R):
    """{edges, n: {h: rows per bin}, med: {h: median y per bin (0 under MIN_ROWS rows)}} from rows() output."""
    b = np.searchsorted(EDGES, R.x0.values, side="left")
    med, n = {}, {}
    for h in HZ:
        g = R.y[R.h.values == h].groupby(b[R.h.values == h])
        cnt = g.size().reindex(range(len(EDGES) + 1), fill_value=0)
        m = g.median().reindex(range(len(EDGES) + 1))
        med[str(h)] = [round(float(m[i]), 2) if cnt[i] >= MIN_ROWS and pd.notna(m[i]) else 0.0 for i in cnt.index]
        n[str(h)] = [int(c) for c in cnt]
    return {"edges": EDGES, "n": n, "med": med}


def term(x0, tab, hs):
    """The reversion to add to a station's forecast change at days hs (0..14), for gap x0; zeros without a table."""
    if not tab or x0 is None or x0 != x0: return np.zeros(len(hs))
    i = bin_of(x0, tab["edges"])
    return np.interp(hs, [0] + HZ, [0.0] + [tab["med"][str(h)][i] for h in HZ])
