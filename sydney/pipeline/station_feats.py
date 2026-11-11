"""Station-level features of one day's Sydney prices: how many stations have just hiked and how the top of the market
sits against the median. On trial only (the shadow forecast in model.py); the published forecast doesn't use them.

Why: the model sees a price restoration through the 90th percentile, which doesn't move until a tenth of stations have
hiked. These see the first few per cent, and the big brands, which lead (on 29 Oct 2026, 25% of them had hiked 5c+
by the end of the day against 3% of the others). Walk-forward 2021-26 they cut the 7-day petrol error from 5.21 to
4.87 c/L and Wait calls made before a 5c+ jump from 129 to 106 (docs/MODEL_INPUTS_2026-11.md).

One definition for both sources, so the fitted and the live values mean the same:
  history   build_history.py: each station's last price of the day from the published price-change history
  live      update.py: today's snapshot against the archived snapshots of 1, 3 and 7 days ago
Only features that a snapshot reproduces are here (checked on the 17 days both sources cover: correlation 0.94 or higher).
The 98th percentile, the share 15c over the median and the share cutting did not reproduce, so they are left out.
"""
import numpy as np

# The brands that lead Sydney's restorations, by the names NSW FuelCheck gives them
MAJORS = {"BP", "7-Eleven", "Ampol", "Ampol Foodary", "EG Ampol", "Caltex", "Caltex Woolworths", "Shell", "Reddy Express",
          "Coles Express"}
COLS = ["p95_spread", "hi8", "maj_hi8", "maj_gap", "up5_1d", "up5_3d", "up5_7d", "up_1d", "maj_up5_1d", "maj_up5_3d", "ind_up5_3d"]
MIN_STATIONS = 10     # a share over fewer stations than this is left blank


def _share(hit, among):
    n = int(among.sum())
    return float(hit[among].mean()) if n >= MIN_STATIONS else np.nan


def day_features(p, prev, major):
    """One fuel, one day. `p`: each station's price today (NaN = none); `prev`: {1: prices a day earlier, 3: .., 7: ..}
    in the same station order (a missing key or NaN = unknown); `major`: True for the leading brands. Prices in c/L.
      p95_spread             95th percentile minus the median
      hi8, maj_hi8           share of stations (of majors) priced 8c+ over the median: already restored
      maj_gap                the majors' median minus the median
      up5_1d, _3d, _7d       share whose price is 5c+ higher than 1, 3, 7 days earlier
      up_1d                  share whose price is up at all (0.5c+) on yesterday
      maj_up5_1d, _3d        the same 5c+ shares among the majors;  ind_up5_3d: among the rest
    """
    p = np.asarray(p, dtype=float); major = np.asarray(major, dtype=bool); ok = ~np.isnan(p)
    out = dict.fromkeys(COLS, np.nan)
    if ok.sum() < MIN_STATIONS: return out
    med = float(np.median(p[ok]))
    out["p95_spread"] = float(np.percentile(p[ok], 95)) - med
    out["hi8"] = _share(p >= med + 8, ok); out["maj_hi8"] = _share(p >= med + 8, ok & major)
    if (ok & major).sum() >= MIN_STATIONS: out["maj_gap"] = float(np.median(p[ok & major])) - med
    for k in (1, 3, 7):
        q = prev.get(k)
        if q is None: continue
        d = p - np.asarray(q, dtype=float); both = ~np.isnan(d)
        out[f"up5_{k}d"] = _share(d >= 5, both)
        if k == 1: out["up_1d"] = _share(d >= 0.5, both); out["maj_up5_1d"] = _share(d >= 5, both & major)
        if k == 3: out["maj_up5_3d"] = _share(d >= 5, both & major); out["ind_up5_3d"] = _share(d >= 5, both & ~major)
    return out


def from_matrix(P, major):
    """Rows of day_features for a (days x stations) matrix of each station's last price of the day (build_history.py)."""
    return [day_features(P[i], {k: P[i - k] for k in (1, 3, 7) if i >= k}, major) for i in range(len(P))]


def from_snapshots(now, earlier):
    """day_features from snapshot price tables. `now`: a DataFrame with columns code, price, brand for one fuel;
    `earlier`: {1: the same for the snapshot a day before, 3: .., 7: ..} (a missing day is simply left out)."""
    now = now.drop_duplicates("code").set_index("code")
    prev = {k: e.drop_duplicates("code").set_index("code").price.reindex(now.index).values for k, e in earlier.items() if e is not None}
    return day_features(now.price.values, prev, now.brand.isin(MAJORS).values)
