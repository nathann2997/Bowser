"""Model experiments for 2026's sustained wholesale swings (docs/RULE_ANALYSIS_2026-10.md, finding 3). Runs on GitHub
Actions (model-experiment.yml) on a read-only copy of the `data` branch; it changes nothing that is published.

usage: python experiment.py BASE VARIANT OUTDIR   one variant's walk-forward, scored -> OUTDIR/VARIANT.json
       python experiment.py --report OUTDIR       the comparison (markdown) from every OUTDIR/*.json
       python experiment.py --list                the variant names as JSON (the workflow's matrix)

Each variant replays model.py's walk-forward backtest (monthly folds from 2021-01; only the 3- and 7-day forecasts and
the 7-day jump chance, which are what the verdict uses) and scores its calls exactly as the app's tested figure does:
the verdict rule (export_api.verdict), the week-after move from daily.csv and `saved` (track_api.py).

Decision rule, fixed before any result was seen (2026-11-21). A variant replaces the production model only if, for U91
and for all fuels pooled:
  - its 2026 saving (c/L, against filling the day you check) goes up,
  - its 2026 Wait-before-a-jump count (a Wait followed by a 5c+ rise within 7 days) goes down,
  - its 2021-25 saving falls by no more than 0.05 c/L,
  - and it beats the rule-level guard ("guard": no Wait after wholesale rose 4c+ in 7 days, finding 4), or matches it
    without the guard's 2021-25 cost.
The 2026 months are listed too: a gain that comes from one episode alone is not a fix.
Added after the QA review, still before any result: a gain must be larger than the gap between `base` and `base_seed2`
(the same model with another random seed: the noise floor), and must hold with wholesale known 7 days late (`*_lag7`),
since live TGP arrives in weekly batches while the backtest sees it a day after.
"""
import json, os, sys

VARIANTS = {   # name: (extra features, recency half-life in years or None, huber alpha, TGP lag in days, seed or None)
    "base": (False, None, 3.0, 1, None),          # model.py's production model ("+cycle memory"), unchanged
    "base_seed2": (False, None, 3.0, 1, 2),       # the same with another random seed: the noise floor
    "trend": (True, None, 3.0, 1, None),          # + sustained wholesale trend features
    "recent2y": (False, 2.0, 3.0, 1, None),       # recent years weigh more: a 2-year half-life, counted from each fold's start
    "recent1y": (False, 1.0, 3.0, 1, None),
    "huber8": (False, None, 8.0, 1, None),        # big moves count more (huber alpha 3 treats errors over 3c linearly)
    "trend_recent2y": (True, 2.0, 3.0, 1, None),
    "base_lag7": (False, None, 3.0, 7, None),     # wholesale known 7 days late, as with a weekly batch at its worst
    "trend_lag7": (True, None, 3.0, 7, None),
    "trend_recent2y_lag7": (True, 2.0, 3.0, 7, None),
}
TREND = ["tgp_chg56", "tgp_vs90", "tgp_trend28", "tgp_up_weeks", "brent_pct56", "margin_vs90", "unpassed28"]
PROD = "+cycle memory"


def verdict(r):   # same rule as verdict() in export_api.py and template.html
    if r["d3"] >= 1.5 or r["p_jump7"] >= 0.5: return {"cls": "up", "head": "Fill up today"}
    if r["d7"] >= 2 or r["p_jump7"] >= 0.35: return {"cls": "up", "head": "Fill up this week"}
    if r["d3"] <= -1.5 or r["d7"] <= -3: return {"cls": "down", "head": "Wait if you can"}
    return {"cls": "flat", "head": "No rush either way"}


# ---------------------------------------------------------------- report (no model import: it loads the data)
def report(out):
    R = {}
    for fn in sorted(os.listdir(out)):
        if fn.endswith(".json"):
            for k, v in json.load(open(f"{out}/{fn}")).items(): R[k] = v
    order = [x for v in VARIANTS for x in (v, *(["guard" + v[4:]] if v.startswith("base") and v != "base_seed2" else []))]
    names = [n for n in order if n in R] + [n for n in R if n not in order]
    missing = [v for v in VARIANTS if v not in R]
    base = R.get("base")
    L = ["# Model experiment: 2026's sustained wholesale swings", "",
         "Walk-forward from 2021-01, scored like the app's tested figure. `save`: c/L saved per call against filling the "
         "day you check. `W→J`: Wait calls followed by a 5c+ rise within 7 days. Decision rule: experiment.py's docstring.", ""]
    if missing: L += [f"**No result (job failed?):** {', '.join(missing)}", ""]
    if base and "repro" in base:
        rp = base["repro"]
        L += ["## Does the harness reproduce production?", "",
              f"- `base` predictions vs the stored backtest (`store/backtest_preds.parquet`, {rp['overlap']} shared rows): "
              f"largest difference {rp['max_diff']} c, mean {rp['mean_diff']} c.",
              f"- U91, last 365 days of the replay as the app computes it (live model: {rp['live_model']}): stored backtest save {rp['stored_recent_save']} c/L, "
              f"{rp['stored_recent_right']} right; `base` save {rp['base_recent_save']} c/L, {rp['base_recent_right']} right. "
              f"The stored backtest ran up to 28 days earlier on an older daily.csv (its window ends earlier, and history "
              f"filled in since can change features), so small differences are expected.",
              f"- Hand-built rows equal track_api.replay's U91 recent tally: {rp['rows_match_replay']}.",
              f"- Live TGP lag on this data copy: forecast asof {rp['asof']}, last TGP {rp['tgp_last']} ({rp['tgp_lag_days']} days).", ""]
    for scope in ["U91", "all"]:
        L += [f"## {'U91' if scope == 'U91' else 'All fuels pooled'}", "",
              "| variant | save 2021–25 | save 2026 | save last 365 d | right 2026 | W→J 2026 | Waits 2026 | GSS 2026 | 7-day MAE 2021–25 | 7-day MAE 2026 | 7-day bias 2026 |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for n in names:
            s = R[n]["score"][scope]; e = R[n]["err"][scope]
            d = lambda k, p: "" if not base or n == "base" else f" ({s[p][k] - base['score'][scope][p][k]:+.2f})"
            L.append(f"| {n} | {s['2021-25']['save']:.2f}{d('save', '2021-25')} | {s['2026']['save']:.2f}{d('save', '2026')} | "
                     f"{s['recent']['save']:.2f} | {s['2026']['right']:.0%} | {s['2026']['wait_jump']} | {s['2026']['waits']} | "
                     f"{s['2026']['gss']} | {e['2021-25']['mae']:.2f} | {e['2026']['mae']:.2f} | {e['2026']['bias']:+.2f} |")
        L.append("")
    L += ["## U91 saving by month, 2026 (c/L; `possible`: perfect hindsight)", ""]
    months = sorted({m for n in names for m in R[n]["months"]})
    L += ["| month | possible | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
    for m in months:
        poss = next((R[n]["months"][m]["possible"] for n in names if m in R[n]["months"]), None)
        L.append(f"| {m} | {poss:.2f} | " + " | ".join(f"{R[n]['months'][m]['save']:.2f}" if m in R[n]["months"] else "" for n in names) + " |")
    L += ["", "## Jump chance on the days it rates under 5% (2025–26, all fuels)", "",
          "| variant | days | predicted | actual | AUC 2021–25 | AUC 2026 |", "|---|---|---|---|---|---|"]
    for n in names:
        c = R[n].get("calib")
        if c: L.append(f"| {n} | {c['n']} | {c['pred']:.1%} | {c['actual']:.1%} | {c['auc_2021_25']} | {c['auc_2026']} |")
    print("\n".join(L))


if len(sys.argv) > 1 and sys.argv[1] == "--report":
    report(sys.argv[2]); sys.exit(0)
if len(sys.argv) > 1 and sys.argv[1] == "--list":
    print(json.dumps(list(VARIANTS))); sys.exit(0)

# ---------------------------------------------------------------- one variant
BASE, NAME, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
EXTRA, HALF_LIFE, ALPHA, TGP_LAG, SEED = VARIANTS[NAME]
sys.argv = [sys.argv[0], BASE]                       # model.py reads BASE from argv at import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
import model as M
import track_api as TA
from fuels import FUELS

PARAMS = dict(M.PARAMS, **({"random_state": SEED} if SEED is not None else {}))
if TGP_LAG != 1:   # wholesale known TGP_LAG days late: rebuild model.py's lagged series and features on it
    M.TL = M.T.reindex(M.cal).ffill().shift(TGP_LAG)
    M.F = M.features(M.D)


def trend_features():
    """Sustained wholesale moves, from the same lagged series as model.py (TL, FrL: known with a 1-day lag)."""
    parts = []
    for f in FUELS:
        tg = M.TL["tgp_dl" if f == "DL" else "tgp_ulp"]
        med = M.D[M.D.fuel == f].set_index("date")["median"].reindex(M.cal)
        margin = med - tg
        x = pd.DataFrame(index=M.cal)
        x["tgp_chg56"] = tg - tg.shift(56)
        x["tgp_vs90"] = tg - tg.rolling(90, 30).mean()
        x["tgp_trend28"] = tg.rolling(14, 10).mean() - tg.shift(14).rolling(14, 10).mean()   # last 2 weeks vs the 2 before
        x["tgp_up_weeks"] = sum(((tg.shift(7 * k) - tg.shift(7 * k + 7)) > 0.5).astype(float) for k in range(4))
        x["brent_pct56"] = 100 * (M.FrL.brent_aud / M.FrL.brent_aud.shift(56) - 1)
        x["margin_vs90"] = margin - margin.rolling(90, 30).median()                        # a squeezed margin vs recent normal
        x["unpassed28"] = (tg - tg.shift(28)) - (med - med.shift(28))                       # wholesale moves not yet at the pump
        x["fuel"] = f
        parts.append(x.reset_index(names="date"))
    return pd.concat(parts, ignore_index=True)


F = M.F
if EXTRA:
    F = F.merge(trend_features(), on=["date", "fuel"], how="left")
FEATS = M.FD + (TREND if EXTRA else [])


def weights(t, t0):
    return None if HALF_LIFE is None else 0.5 ** ((t0 - t.date).dt.days.values / (365.25 * HALF_LIFE))


def reg(t, fs, y, t0):
    return lgb.LGBMRegressor(objective="huber", alpha=ALPHA, **PARAMS).fit(t[fs], t[y], sample_weight=weights(t, t0))


def clf(t, fs, t0):
    return lgb.LGBMClassifier(**PARAMS).fit(t[fs], t.y_jump7, sample_weight=weights(t, t0))


# walk-forward, the same folds and training cut-offs as model.py's backtest
preds, cls = [], []
for m in pd.period_range("2021-01", (M.asof - pd.Timedelta(days=15)).strftime("%Y-%m"), freq="M"):
    t0 = m.start_time
    te_all = F[F.date.dt.to_period("M") == m]
    for h in (3, 7):
        y = f"y{h}"
        tr = F[(F.date + pd.Timedelta(days=h) < t0) & F[y].notna()]
        te = te_all[te_all[y].notna()]
        if te.empty: continue
        rec = te[["date", "fuel", y]].rename(columns={y: "actual"}).assign(h=h)
        rec[PROD] = M.predict(lambda t, fs: reg(t, fs, y, t0), tr, te, FEATS)
        preds.append(rec)
    tr = F[(F.date + pd.Timedelta(days=7) < t0) & F.y_jump7.notna()]
    te = te_all[te_all.y_jump7.notna()]
    if len(te):
        cls.append(te[["date", "fuel", "y_jump7"]].assign(p=M.predict(lambda t, fs: clf(t, fs, t0), tr, te, FEATS, proba=True)))
    print(m, flush=True)
P = pd.concat(preds, ignore_index=True); C = pd.concat(cls, ignore_index=True)

# the app's replay, on this variant's predictions (track_api.replay reads them from a store/ like model.py writes)
tmp = f"{OUT}/{NAME}_base"; os.makedirs(f"{tmp}/store", exist_ok=True)
P.to_parquet(f"{tmp}/store/backtest_preds.parquet"); C.to_parquet(f"{tmp}/store/backtest_cls.parquet")
json.dump({"prod": PROD}, open(f"{tmp}/store/backtest.json", "w"))
med, last = TA.medians(BASE)
FC = json.load(open(f"{BASE}/store/forecast.json"))["ctx"] if os.path.exists(f"{BASE}/store/forecast.json") else {}
LIVE_MODEL = FC.get("live_model") or "full (with cycle memory)"   # the model the app's tested figure follows
mine = TA.replay(tmp, med, last, verdict, LIVE_MODEL)

# the same rows replay() scores, kept with the jump flag and the week's wholesale change
w = P[P["h"].isin([3, 7])].pivot_table(index=["date", "fuel"], columns="h", values=PROD)
w = w.rename(columns={3: "d3", 7: "d7"}).join(C.set_index(["date", "fuel"])["p"].rename("p_jump7")).dropna()
w = w.join(C.set_index(["date", "fuel"])["y_jump7"]).join(F.set_index(["date", "fuel"])["tgp_chg7"]).reset_index()


def rows_for(guard):
    rows = []
    for r in w.itertuples(index=False):
        date = pd.Timestamp(r.date).date().isoformat()
        now = med.get(r.fuel, {}).get(date)
        if now is None: continue
        avg, _, done = TA.window(med, r.fuel, date, last)
        if not done: continue
        c = verdict({"d3": r.d3, "d7": r.d7, "p_jump7": r.p_jump7})["cls"]
        if guard and c == "down" and r.tgp_chg7 >= 4: c = "flat"
        mv = avg - now
        rows.append({"date": date, "fuel": r.fuel, "cls": c, "move": mv, "status": TA.score(c, mv), "jump": r.y_jump7 == 1})
    return rows


def tally(rs):
    if not rs: return None
    return {"n": len(rs), "save": round(float(np.mean([TA.saved(r["cls"], r["move"]) for r in rs])), 3),
            "right": round(sum(r["status"] == "right" for r in rs) / len(rs), 3), "right_n": sum(r["status"] == "right" for r in rs),
            "waits": sum(r["cls"] == "down" for r in rs), "wait_jump": sum(r["cls"] == "down" and r["jump"] for r in rs),
            "gss": TA.gerrity(rs)}


def scored(rows):
    cut = (pd.Timestamp(max(r["date"] for r in rows)) - pd.Timedelta(days=TA.RECENT_DAYS)).date().isoformat()
    out = {}
    for scope in ["U91", "all"]:
        rs = [r for r in rows if scope == "all" or r["fuel"] == scope]
        out[scope] = {"2021-25": tally([r for r in rs if r["date"] < "2026"]), "2026": tally([r for r in rs if r["date"] >= "2026"]),
                      "recent": tally([r for r in rs if r["date"] > cut])}
    months = {}
    for r in rows:
        if r["fuel"] == "U91" and r["date"] >= "2026": months.setdefault(r["date"][:7], []).append(r)
    months = {m: {"save": round(float(np.mean([TA.saved(r["cls"], r["move"]) for r in rs])), 3),
                  "possible": round(float(np.mean([max(0.0, -r["move"]) for r in rs])), 3)} for m, rs in sorted(months.items())}
    return out, months


def errors():
    p7 = P[P.h == 7]; out = {}
    for scope in ["U91", "all"]:
        g = p7 if scope == "all" else p7[p7.fuel == scope]
        out[scope] = {}
        for per, gg in [("2021-25", g[g.date < "2026"]), ("2026", g[g.date >= "2026"])]:
            e = gg.actual - gg[PROD]
            out[scope][per] = {"mae": round(float(e.abs().mean()), 3), "bias": round(float(e.mean()), 3)}
    return out


def calib():
    c = C[C.date >= "2025"]; lo = c[c.p < 0.05]
    auc = lambda g: round(float(roc_auc_score(g.y_jump7, g.p)), 3) if g.y_jump7.nunique() > 1 else None
    return {"n": int(len(lo)), "pred": float(lo.p.mean()), "actual": float(lo.y_jump7.mean()),
            "auc_2021_25": auc(C[C.date < "2026"]), "auc_2026": auc(C[C.date >= "2026"])}


res = {}
GUARD = "guard" + NAME[4:] if NAME in ("base", "base_lag7") else None   # the rule-level benchmark, on the same wholesale lag
for name, guard in [(NAME, False)] + ([(GUARD, True)] if GUARD else []):
    rows = rows_for(guard)
    if not guard: own_recent = tally([r for r in rows if r["fuel"] == "U91" and r["date"] > (pd.Timestamp(max(r["date"] for r in rows)) - pd.Timedelta(days=TA.RECENT_DAYS)).date().isoformat()])
    sc, months = scored(rows)
    res[name] = {"score": sc, "months": months, "err": errors(), "calib": None if guard else calib(),
                 "app_replay_u91_recent": mine["U91"].get("recent") if mine else None}

if NAME == "base":   # does this harness reproduce the stored production backtest and its replay?
    S = pd.read_parquet(f"{BASE}/store/backtest_preds.parquet")
    j = P.merge(S[["date", "fuel", "h", PROD]], on=["date", "fuel", "h"], suffixes=("", "_stored"))
    diff = (j[PROD] - j[f"{PROD}_stored"]).abs()
    stored = TA.replay(BASE, med, last, verdict, LIVE_MODEL)
    fc = FC
    rec = mine["U91"]["recent"] if mine else {}
    lag = (pd.Timestamp(fc["asof"]) - pd.Timestamp(fc["tgp_last"])).days if fc.get("tgp_last") else None
    res["base"]["repro"] = {
        "overlap": int(len(j)), "max_diff": round(float(diff.max()), 3) if len(j) else None,
        "mean_diff": round(float(diff.mean()), 4) if len(j) else None,
        "stored_recent_save": stored["U91"]["recent"]["save"] if stored else None,
        "stored_recent_right": f"{stored['U91']['recent']['right'] / stored['U91']['recent']['n']:.0%}" if stored else None,
        "base_recent_save": mine["U91"]["recent"]["save"],
        "base_recent_right": f"{mine['U91']['recent']['right'] / mine['U91']['recent']['n']:.0%}",
        "live_model": LIVE_MODEL,
        "rows_match_replay": bool(rec) and rec["n"] == own_recent["n"] and rec["right"] == own_recent["right_n"]
                             and abs(rec["save"] - own_recent["save"]) < 0.006,
        "asof": fc.get("asof"), "tgp_last": fc.get("tgp_last"), "tgp_lag_days": lag}

json.dump(res, open(f"{OUT}/{NAME}.json", "w"), indent=1)
print(json.dumps({k: v["score"] for k, v in res.items()}, indent=1))
