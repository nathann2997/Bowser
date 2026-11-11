"""Compare the shadow forecast (the live model plus station features) with the live one, from store/shadow.csv.

usage: python shadow_score.py BASE          (BASE holds store/, e.g. a checkout of the `data` branch)

model.py logs both forecasts at the first and the latest run of each Sydney day. This scores them the way the app's
track record does (track_api.py): the verdict rule on each forecast, against the average median over the 7 days after
the call, measured from the median the call was made with.
  gain     c/L from following the call (fill +move, wait -move, no rush 0): the measure that decides
  err7     mean absolute error of the 7-day forecast against that move's end point (the median 7 days on)
  wait_bj  Wait calls that were followed by a 5c+ rise within the week
The first run is the one that matters: it is the call people act on, and the walk-forward test couldn't see it (it
scores end-of-day prices). Decide on `first`; `last` shows what the end-of-day test promised. A `first` row logged at
or after FIRST_BEFORE (an early run failed, so a later one wrote it) isn't a morning call and is left out.
Days are scored once their week is over. About one independent result a day, so a few weeks only show a large gap.
"""
import csv, datetime as dt, math, os, re, sys

import track_api as T
from fuels import FUELS


def verdict(d3, d7, pj):   # the rule in export_api.py verdict() and template.html; change all three together
    if d3 >= 1.5 or pj >= 0.5 or d7 >= 2 or pj >= 0.35: return "up"
    if d3 <= -1.5 or d7 <= -3: return "down"
    return "flat"


FIRST_BEFORE = "12:00"     # Sydney time; the scheduled morning runs are 05:13 and 10:13 and often start late


def score(rows, med, last):
    """{(run, model): tally} for shadow.csv rows; `med` and `last` from track_api.medians()."""
    out = {}
    for r in rows:
        try:                                                        # a damaged row is skipped, not fatal
            now = float(r["now"]); f = {k: float(r[k]) for k in ["d3", "d7", "pj", "s_d3", "s_d7", "s_pj"]}
            if not all(math.isfinite(v) for v in [now, *f.values()]) or r["run"] not in ("first", "last"): continue
            if r["run"] == "first" and not (re.fullmatch(r"\d\d:\d\d", str(r.get("time"))) and r["time"] < FIRST_BEFORE): continue
            avg, n, done = T.window(med, r["fuel"], r["date"], last)
        except (KeyError, TypeError, ValueError): continue
        if not done: continue
        move = avg - now
        days = [(dt.date.fromisoformat(r["date"]) + dt.timedelta(k)).isoformat() for k in range(1, 8)]
        seen = [med.get(r["fuel"], {}).get(d) for d in days]
        jump = max((v for v in seen if v is not None), default=now) - now >= 5
        end = seen[-1]
        for model, (d3, d7, pj) in {"live": (f["d3"], f["d7"], f["pj"]), "shadow": (f["s_d3"], f["s_d7"], f["s_pj"])}.items():
            t = out.setdefault((r["run"], model), {"n": 0, "gain": 0.0, "err7": 0.0, "n7": 0, "wait_bj": 0, "right": 0})
            cls = verdict(d3, d7, pj)
            t["n"] += 1; t["gain"] += move if cls == "up" else -move if cls == "down" else 0.0
            t["right"] += T.score(cls, move) == "right"; t["wait_bj"] += cls == "down" and jump
            if end is not None: t["err7"] += abs((end - now) - d7); t["n7"] += 1
    return out


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = f"{base}/store/shadow.csv"
    if not os.path.exists(path): sys.exit(f"{path} not found: the shadow forecast hasn't run yet")
    with open(path, newline="") as fh: rows = [r for r in csv.DictReader(fh) if r.get("fuel") in FUELS]
    med, last = T.medians(base)
    res = score(rows, med, last)
    days = sorted({r["date"] for r in rows})
    print(f"shadow.csv: {len(days)} days logged ({days[0]} to {days[-1]})" if days else "shadow.csv is empty")
    if not res: sys.exit("no call's week is over yet: nothing to score")
    print(f"{'run':6s} {'model':7s} {'calls':>5s} {'gain c/L':>9s} {'right':>6s} {'err7 c/L':>9s} {'wait_bj':>8s}")
    for run in ["first", "last"]:
        for model in ["live", "shadow"]:
            t = res.get((run, model))
            if t: print(f"{run:6s} {model:7s} {t['n']:5d} {t['gain'] / t['n']:9.2f} {t['right'] / t['n']:6.0%} "
                        f"{(t['err7'] / t['n7'] if t['n7'] else float('nan')):9.2f} {t['wait_bj']:8d}")
