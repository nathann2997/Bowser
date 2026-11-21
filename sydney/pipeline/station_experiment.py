"""Station forecasts and mean reversion: does a station's gap from its usual premium close by itself? Runs on GitHub
Actions (station-experiment.yml) on a read-only copy of the `data` branch; it changes nothing that is published.

usage: python station_experiment.py BASE   -> markdown on stdout

Today a Sydney station's forecast (station_api.py `fc`) is the Sydney median's forecast move, damped and shifted for
the station: ds_h = w * d(h - s), with w = its share of price jumps against the median station's (capped at 1) and s
its lag in days (station_profile.py `part`, `lag`). A station 10c above its usual premium (`typ`) is forecast to stay
10c above it. Here, for every Sydney station, fuel and day t:
  x0   = (price - Sydney median) - typ, typ = the station's median premium over the 365 days before t (60+ days seen),
         as station_profile.py computes it
  y_h  = station move over h days - w * (Sydney median move over h - s days): what today's forecast misses, given the
         actual Sydney move
Only station-days whose price was updated within 10 days, at t and at t + h, count (build.py's "Check price" cut): a
closed or silent station's carried-forward price would look like no reversion. |x0| and |x(t+h)| over 40c are price
slips, not behaviour. Training: days before the split (rows whose window crosses it are dropped); test: after.
  zero     y_h = 0 (today's forecast)
  binned   y_h = the training MEDIAN of y_h for x0's bin (the median, because it is scored on absolute error)
  linear   y_h = (b_h - 1) * x0, least squares on the training days (shown for scale, not used to decide)

Decision rule, fixed before any result was seen (2026-11-21, revised after the QA review, still before any result):
station forecasts get the binned reversion term only if, on the test days, it lowers the MAE by at least 0.1 c/L at
both 7 and 14 days, for x0 >= 8 (build.py's "Skip for now" / "likely to ease") and for x0 <= -6 ("Fill now"), and the
overall MAE at 7 and 14 days gets no worse (by more than 0.02 c/L).
Second rule (2026-11-21, fixed before this breakdown was run, after the first pipeline-ci run showed steady pricers
moved by up to 15c a week): steady pricers (n >= 5 and part < 0.25, as advise() tests) keep the term in production
only if, on the test days, binned is no worse than zero for them at 7 and at 14 days (MAE); otherwise they're excluded.
Caveats: w and s come from today's station_profile.json (the last 365 days of history), so they overlap the test days a
little; and y uses the actual Sydney move, so the test isolates the station's own part, without the error of the Sydney
forecast it would be added to in production.
"""
import glob, json, os, re, sys
import numpy as np, pandas as pd

BASE = sys.argv[1]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuels import FUELS
EV = f"{BASE}/store/events"
H = [1, 3, 7, 14]
BINS = [-np.inf, -10, -6, -3, -1, 1, 3, 6, 8, 12, np.inf]
FRESH, SLIP = 10, 40
norm = lambda s: re.sub(r"\s+", " ", str(s).upper().replace(",", " ")).strip()

# the same event reading as station_profile.py
st = pd.read_csv(f"{EV}/syd_stations.csv", dtype=str)
sid2key = dict(zip(st.sid.astype(int), st.key.map(norm)))
parts = []
for f in sorted(glob.glob(f"{EV}/syd_events_*.csv")):
    if int(re.search(r"_(\d{4})", f).group(1)) < 2024: continue
    e = pd.read_csv(f, dtype={"hhmm": str})
    e["key"] = e.sid.astype(int).map(sid2key) if "sid" in e.columns else e.key.map(norm)
    parts.append(e[["key", "fuel", "ymd", "hhmm", "price"]])
ev = pd.concat(parts, ignore_index=True)
ev = ev[ev.fuel.isin(FUELS) & ev.key.notna() & ev.price.between(50, 600)]
ev["ts"] = pd.to_datetime(ev.ymd.astype(str) + ev.hhmm.str.zfill(4), format="%Y%m%d%H%M")
ev = ev.sort_values("ts", kind="stable"); ev["date"] = ev.ts.dt.normalize()
D = pd.read_csv(f"{BASE}/store/daily.csv", parse_dates=["date"]); D = D[D.source == "history"]

# today's damping and shift, exactly as station_api.py computes them
PF = json.load(open(f"{BASE}/store/station_profile.json"))
lag_med = PF.get("lag_median", 48)
pts = [p["part"] for p in PF["stations"].values() if p.get("part") is not None and p.get("n", 0) >= 5]
part_med = float(np.median(pts)) if pts else 1.0
def w_s(key):
    p = PF["stations"].get(key, {})
    w = 1.0 if p.get("n", 0) < 5 or p.get("part") is None else float(np.clip(p["part"] / part_med, 0, 1))
    s = 0 if p.get("lag") is None else int(np.clip(round((p["lag"] - lag_med) / 24), -1, 2))
    return w, s

STEADY = {k for k, p in PF["stations"].items() if p.get("n", 0) >= 5 and p.get("part", 1) < 0.25}
rows = []
for f in FUELS:
    e = ev[ev.fuel == f]
    if e.empty: continue
    days = pd.date_range(e.date.min(), e.date.max())
    raw = e.groupby(["date", "key"]).price.last().unstack().reindex(days)
    M = raw.ffill(limit=30)                                            # end-of-day price, as the profile
    seen = pd.DataFrame(np.where(raw.notna(), days.values[:, None], np.datetime64("NaT")), index=days, columns=raw.columns).ffill()
    fresh = seen.apply(lambda c: (days - pd.DatetimeIndex(c)).days <= FRESH)
    med = D[D.fuel == f].set_index("date")["median"].reindex(days)
    prem = M.sub(med, axis=0)
    typ = prem.rolling(365, min_periods=60).median().shift(1)          # trailing year, before t
    x = (prem - typ).where(fresh)
    x = x.where(x.abs() <= SLIP)
    ws = {k: w_s(k) for k in x.columns}
    for h in H:
        y = pd.DataFrame(index=days, columns=x.columns, dtype=float)
        for s in (-1, 0, 1, 2):
            ks = [k for k in x.columns if ws[k][1] == s]
            if not ks: continue
            w = np.array([ws[k][0] for k in ks])
            dmed = med.shift(-max(h - s, 0)) - med                     # the median's move over h - s days (0 if s >= h)
            y[ks] = (M[ks].shift(-h) - M[ks]).values - np.outer(dmed.values, w)
        y = y.where(x.notna() & x.shift(-h).notna())                   # fresh, plausible at both ends
        s_ = pd.DataFrame({"x0": x.stack(), "y": y.stack()}).dropna()
        s_["h"], s_["fuel"] = h, f
        s_["steady"] = s_.index.get_level_values(1).isin(STEADY)
        s_["date"] = s_.index.get_level_values(0)
        rows.append(s_.reset_index(drop=True))
S = pd.concat(rows, ignore_index=True)
split = S.date.quantile(0.5).normalize()                               # about half the rows each side
train = S[S.date + pd.to_timedelta(S.h, unit="D") < split]
test = S[S.date >= split]
assert len(train) > 1000 and len(test) > 1000, f"too few rows: train {len(train)}, test {len(test)}"

L = ["# Station forecasts: does the gap from a station's usual premium close?", "",
     f"Events {ev.date.min().date()} to {ev.date.max().date()}; trained before {split.date()}, tested after. "
     "MAE (c/L) of what today's station forecast misses given the actual Sydney move; stations updated within 10 days. "
     "`zero` is today's forecast; `binned` is the candidate. Decision rule: the script's docstring.", "",
     "| h | b (linear) | test rows | MAE zero | MAE binned | MAE linear | x0 ≥ 8: rows, zero → binned, median y | x0 ≤ −6: rows, zero → binned, median y |",
     "|---|---|---|---|---|---|---|---|"]
verdict = {}
for h in H:
    tr, te = train[train.h == h], test[test.h == h]
    b = 1 + float((tr.x0 * tr.y).sum() / (tr.x0 ** 2).sum())
    meds = tr.groupby(pd.cut(tr.x0, BINS), observed=False).y.median()
    te = te.assign(lin=(b - 1) * te.x0, binned=pd.cut(te.x0, BINS).map(meds).astype(float).fillna(0.0))
    mae = lambda g, c: float((g.y - (0 if c == "zero" else g[c])).abs().mean())
    hi, lo = te[te.x0 >= 8], te[te.x0 <= -6]
    verdict[h] = {"all": mae(te, "binned") - mae(te, "zero"), "hi": mae(hi, "binned") - mae(hi, "zero") if len(hi) else np.nan,
                  "lo": mae(lo, "binned") - mae(lo, "zero") if len(lo) else np.nan}
    part = lambda g: f"{len(g)}, {mae(g, 'zero'):.2f} → {mae(g, 'binned'):.2f}, {g.y.median():+.2f}" if len(g) else "–"
    L.append(f"| {h} | {b:.3f} | {len(te)} | {mae(te, 'zero'):.2f} | {mae(te, 'binned'):.2f} | {mae(te, 'lin'):.2f} | {part(hi)} | {part(lo)} |")
ok = all(verdict[h]["hi"] <= -0.1 and verdict[h]["lo"] <= -0.1 and verdict[h]["all"] <= 0.02 for h in (7, 14))
L += ["", f"**Decision rule: {'passes' if ok else 'does not pass'}** "
      f"(MAE change at 7 / 14 days: x0 ≥ 8 {verdict[7]['hi']:+.2f} / {verdict[14]['hi']:+.2f}, x0 ≤ −6 {verdict[7]['lo']:+.2f} / "
      f"{verdict[14]['lo']:+.2f}, overall {verdict[7]['all']:+.2f} / {verdict[14]['all']:+.2f}).", "",
      "Training medians of y (c/L) by x0 bin:", "", "| x0 bin | " + " | ".join(f"h={h}" for h in H) + " |", "|---|" + "---|" * len(H)]
tab = train.groupby([pd.cut(train.x0, BINS), "h"], observed=False).y.median().unstack()
for k, r in tab.iterrows():
    L.append(f"| {k} | " + " | ".join(f"{r[h]:+.2f}" for h in H) + " |")
L += ["", "Steady pricers vs the rest (test days; MAE zero → binned):", "", "| h | steady rows | steady | rest rows | rest |", "|---|---|---|---|---|"]
sv = {}
for h in H:
    tr, te = train[train.h == h], test[test.h == h]
    meds = tr.groupby(pd.cut(tr.x0, BINS), observed=False).y.median()
    te = te.assign(binned=pd.cut(te.x0, BINS).map(meds).astype(float).fillna(0.0))
    cell = []
    for flag in (True, False):
        g = te[te.steady == flag]
        z, b = float(g.y.abs().mean()), float((g.y - g.binned).abs().mean())
        if flag: sv[h] = b - z
        cell += [str(len(g)), f"{z:.2f} → {b:.2f}"]
    L.append(f"| {h} | " + " | ".join(cell) + " |")
keep = all(sv[h] <= 0 for h in (7, 14))
L += ["", f"**Steady pricers: {'keep the term' if keep else 'exclude them'}** (MAE change 7 / 14 days: {sv[7]:+.2f} / {sv[14]:+.2f})."]
print("\n".join(L))
