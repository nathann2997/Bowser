"""Weekly outlook archive (roadmap item 7): one saved forecast a week, scored once the weeks after it are known.

Called by export_api.py. Each Sydney week (Monday to Sunday) the first successful, non-stale run saves the forecast it
published to store/weekly/<Monday>.json (`snapshot()`, `save()`): every fuel's median then, the 1/3/7/14-day expected
change with the 80% range, the jump chance and the call. It's never rewritten, and nothing is backfilled: the archive
starts with the first real snapshot (2026-11).

Two scorings, kept apart on the pages because they answer different questions (`score()`):
  the call             the fill-or-wait call of the snapshot's day exactly as the track record scores it (track_api:
                       store/calls.csv's first call of that day, the average median over the 7 days after against the
                       median it was made with), so a week's verdict always matches the track record
  where it landed      the Sydney median 7 and 14 days after the snapshot (end of day, store/daily.csv) against its own
                       starting median: the change, the error against the forecast, and whether it fell in the range
A horizon is pending until its day is over (the latest day in daily.csv is today, a partial day). A day missing from
daily.csv once it's over uses the nearest known day within NEAR days; with none, the horizon is marked missing (scored,
with no price), so one gap never leaves a week unscored.
"""
import datetime as dt, json, os

import track_api
from fuels import FUELS

VERSION = 1
HZ = [7, 14]
NEAR = 2
NUM = ["now"] + [f"{k}{h}" for h in (1, 3, 7, 14) for k in ("d", "lo", "hi")] + ["p_jump7"]


def week_of(asof):
    d = dt.date.fromisoformat(asof)
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def path(base, week):
    return f"{base}/store/weekly/{week}.json"


def snapshot(asof, live, saved_at):
    rows = []
    for r in live:
        if r.get("fuel") not in FUELS or not all(isinstance(r.get(k), (int, float)) for k in NUM): continue
        v = r.get("verdict") or {}
        rows.append({"fuel": r["fuel"], **{k: round(float(r[k]), 3) for k in NUM}, "verdict": {"cls": v.get("cls"), "head": v.get("head")}})
    return {"version": VERSION, "week": week_of(asof), "asof": asof, "saved": saved_at, "live": rows}


def pending(base, asof, live, saved_at):
    """This week's snapshot if none is saved yet (else None). export_api shows it with the rest and saves it at the end."""
    s = snapshot(asof, live, saved_at)
    return None if os.path.exists(path(base, s["week"])) or not s["live"] else s


def save(base, snap):
    p = path(base, snap["week"])
    if os.path.exists(p): return False
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh: json.dump(snap, fh, separators=(",", ":"))
    return True


def valid(s):
    try:
        return (isinstance(s, dict) and s.get("version") == VERSION and week_of(s["asof"]) == s["week"]
                and isinstance(s.get("live"), list) and s["live"]
                and all(r.get("fuel") in FUELS and all(isinstance(r.get(k), (int, float)) for k in NUM)
                        and isinstance(r.get("verdict"), dict) for r in s["live"]))
    except (KeyError, TypeError, ValueError):
        return False


def load(base):
    """Saved snapshots, oldest first; a file that doesn't read or doesn't fit is skipped, not fatal."""
    d = f"{base}/store/weekly"
    out = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not f.endswith(".json"): continue
        try:
            with open(os.path.join(d, f)) as fh: s = json.load(fh)
        except (OSError, ValueError):
            continue
        if valid(s) and f == f"{s['week']}.json": out.append(s)
    return out


def score(base, snaps):
    """The snapshots with a `score` per fuel: {call: {cls, head, now, move, status}, h7/h14: {actual, change, err, inside}
    or None while pending}, plus `scored` (the last day a horizon was scored, for lastmod) and `done` (U91's 7 days known)."""
    med, last = track_api.medians(base)
    # the track record's own scored calls (same row checks, rounding and rule), so the two can't disagree
    calls = {}
    for c in track_api.live_calls(base, med, last): calls.setdefault((c["date"], c["fuel"]), c)
    out = []
    for s in sorted(snaps, key=lambda x: x["week"]):
        s = {**s, "score": {}}; scored = None
        for r in s["live"]:
            f, a = r["fuel"], s["asof"]
            c = calls.get((a, f))
            if c:
                call = {k: c[k] for k in ("cls", "head", "now", "move", "status")}
                if call["status"] == "pending": call["move"] = None
            else:   # no saved call that day: the snapshot's own, scored the same way
                avg, _, done = track_api.window(med, f, a, last)
                move = round(avg - r["now"], 1) + 0.0 if done and avg is not None else None
                cls = r["verdict"].get("cls")
                call = {"cls": cls, "head": str(r["verdict"].get("head") or "")[:40], "now": r["now"], "move": move, "status": track_api.score(cls, move)}
            sc = {"call": call}
            for h in HZ:
                day = (dt.date.fromisoformat(a) + dt.timedelta(days=h)).isoformat()
                if day >= last: sc[f"h{h}"] = None; continue          # pending
                scored = max(scored or day, day)
                near = [d for k in range(NEAR + 1) for d in [(dt.date.fromisoformat(day) + dt.timedelta(days=s * k)).isoformat() for s in (-1, 1)]
                        if a < d < last and med.get(f, {}).get(d) is not None]   # the day itself, then the day before, after, ...
                if not near: sc[f"h{h}"] = {"day": day, "missing": True}; continue
                v = med[f][near[0]]
                ch = v - r["now"]
                sc[f"h{h}"] = {"day": day, "actual": round(v, 1), "change": round(ch, 1), "err": round(ch - r[f"d{h}"], 1),
                               "inside": r[f"lo{h}"] <= ch <= r[f"hi{h}"]}
            s["score"][f] = sc
        s["scored"] = scored
        s["done"] = bool((s["score"].get("U91") or {}).get("h7"))
        out.append(s)
    return out
