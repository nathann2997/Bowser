"""Model experiments on GitHub Actions (model-experiment.yml), on a read-only copy of the `data` branch; it changes
nothing that is published. First run: 2026's sustained wholesale swings (finding 3, 2026-11-21, run 44744791846; its
variants are in git history at ac573d2). Current run: which learner, LightGBM or another (docs/MODEL_FAMILY_2026-11.md).

usage: python experiment.py BASE VARIANT OUTDIR   one variant's walk-forward, scored -> OUTDIR/VARIANT.json, and its
                                                  predictions -> OUTDIR/VARIANT_base/store/backtest_{preds,cls}.parquet
       python experiment.py BASE ENSEMBLE OUTDIR  an average of saved variants' predictions (PREDS=dir of preds-<name>/)
       python experiment.py --compare PREDSDIR OUTDIR   paired month-block bootstrap of every variant against `base`
       python experiment.py --report OUTDIR       the comparison (markdown) from every OUTDIR/*.json
       python experiment.py --list                the variant names as JSON (the workflow's matrix); --ensembles: theirs
QUICK=1 runs only the folds from 2025-10, to catch install and import errors cheaply. (Smoke test of this run: 45518266106, all jobs green.)

Each variant replays model.py's walk-forward backtest (monthly folds from 2021-01; the 1-, 3-, 7- and 14-day forecasts
and the 7-day jump chance) and scores its calls exactly as the app's tested figure does: the verdict rule
(export_api.verdict), the week-after move from daily.csv and `saved` (track_api.py).

Model-family decision rule, fixed 2026-11-25 before any result was seen. 2026 was already used to choose in the first run,
and there are almost no calls after that, so nothing here replaces production directly. A learner is ADVANCED TO A
SHADOW TRIAL (logged beside the live forecast like the station-feature shadow, never published, judged on real morning
calls from late November 2026 with shadow_score.py's six-week standard) only if, for all fuels pooled and for U91:
  - its 7-day MAE over 2021-26 is lower than `base`'s, the 95% block-bootstrap interval of the paired difference
    (compare(): 3-month blocks) is below zero, and the gain is larger than both its own family's seed gap and
    LightGBM's. A seed gap is |7-day MAE of NAME_seed2 - 7-day MAE of NAME| from compare(), per scope (pooled, U91):
    `base_seed2` for LightGBM and `lgbm_linear`, `xgb_seed2` for both XGBoost variants, `catboost_seed2`, and
    `extratrees_seed2`; `linear` is deterministic (gap 0); `avg3` uses the largest of its members' gaps;
  - its 3-day MAE is no worse than `base`'s by more than LightGBM's seed gap (the verdict reads d3 too);
  - its app saving (c/L) falls by no more than 0.05 in 2021-25 and does not fall in 2026;
  - its 7-day jump AUC over 2021-26 is no more than 0.01 below `base`'s;
  - and its walk-forward fit time is at most 3x LightGBM's (daily.yml refits every model 5 times a day); an
    ensemble's fit time is the sum of its members'.
If none passes, LightGBM stays. XGBoost against LightGBM is read from the capacity-matched pair (`xgb` vs `base`):
inside the seed gaps they are the same model, and LightGBM keeps the place for being already there and faster.

Finding-3 decision rule, fixed before any result was seen (2026-11-21). A variant replaces the production model only if, for U91
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
import json, os, sys, time

# The learner comparison's set (2026-11-25, run 45540309359). A push to a `model/` branch reruns whatever is listed
# here, so swap it for the next experiment's variants (finding 3's set: git show ac573d2:sydney/pipeline/experiment.py).
# name: (extra features, recency half-life in years or None, huber alpha, TGP lag in days, seed or None, learner).
# Every learner gets model.py's features, folds, petrol/diesel split and targets; only the estimator changes. Capacity is
# matched, not parameter names: 400 rounds at 0.03, about 15 leaves, 80% row and column sampling, L2 2 on leaf values.
VARIANTS = {
    "base": (False, None, 3.0, 1, None, "lgbm"),          # model.py's production model ("+cycle memory"), unchanged
    "base_seed2": (False, None, 3.0, 1, 2, "lgbm"),       # the same with another random seed: LightGBM's noise floor
    "xgb": (False, None, 3.0, 1, None, "xgb"),            # XGBoost grown like LightGBM: leaf-wise, 15 leaves, the same loss
    "xgb_seed2": (False, None, 3.0, 1, 2, "xgb"),         # XGBoost's own noise floor
    "xgb_depth": (False, None, 3.0, 1, None, "xgb_depth"),  # XGBoost's usual growth: level-wise to depth 4 (<= 16 leaves)
    "catboost": (False, None, 3.0, 1, None, "cat"),       # symmetric (oblivious) depth-4 trees, ordered boosting, Huber 3
    "catboost_seed2": (False, None, 3.0, 1, 2, "cat"),
    "lgbm_linear": (False, None, 3.0, 1, None, "lgbm_linear"),  # a linear model in each leaf: can extrapolate a trend
    "linear": (False, None, 3.0, 1, None, "linear"),      # Huber / logistic regression: what do the trees add?
    "extratrees": (False, None, 3.0, 1, None, "et"),      # bagged randomised trees (squared error): variance, not bias
    "extratrees_seed2": (False, None, 3.0, 1, 2, "et"),
}   # `linear` ignores the alpha column: HuberRegressor's epsilon 1.35 is on its own scale of the residuals
ENSEMBLES = {"avg3": ["base", "xgb", "catboost"]}         # plain average of saved predictions and jump chances
TREND = ["tgp_chg56", "tgp_vs90", "tgp_trend28", "tgp_up_weeks", "brent_pct56", "margin_vs90", "unpassed28"]
PROD = "+cycle memory"
H_RUN = (1, 3, 7, 14)
SHOCK = ["2022-02", "2022-03", "2022-04", "2022-05", "2022-06", "2022-07", "2022-08", "2022-09",   # model.py's list
         "2026-03", "2026-04", "2026-07", "2026-08"]


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
    CMP = R.pop("compare", None)
    order = [x for v in [*VARIANTS, *ENSEMBLES] for x in (v, *(["guard" + v[4:]] if v.startswith("base") and v != "base_seed2" else []))]
    names = [n for n in order if n in R] + [n for n in R if n not in order]
    missing = [v for v in [*VARIANTS, *ENSEMBLES] if v not in R]
    base = R.get("base")
    num = lambda x, f="{:.2f}": "–" if x is None else f.format(x)
    for n, ms in ENSEMBLES.items():   # an ensemble refits nothing here, but live it would fit every member
        if n in R and R[n].get("extra") and all((R.get(v) or {}).get("extra") for v in ms):
            R[n]["extra"]["fit_s"] = sum(R[v]["extra"]["fit_s"] for v in ms)
    L = ["# Model experiment: which learner", "",
         "Walk-forward from 2021-01, scored like the app's tested figure. `save`: c/L saved per call against filling the "
         "day you check. `W→J`: Wait calls followed by a 5c+ rise within 7 days. Decision rule: experiment.py's docstring.", ""]
    if any((R[n].get("extra") or {}).get("quick") for n in R):
        L += ["> **QUICK RUN: folds from 2025-10 only. A smoke test, not a result; the decision rule does not apply.**", ""]
    if CMP:
        L += ["## Forecast error against LightGBM (paired, all folds 2021–26)", "",
              "MAE in c/L; Δ = variant − `base`, with the 95% interval from a moving-block bootstrap of 3-month blocks (2,000 draws, "
              "the same draws for every variant).", ""]
        for scope in ["all", "U91"]:
            L += [f"**{'All fuels pooled' if scope == 'all' else 'U91'}**", "",
                  "| variant | " + " | ".join(f"MAE {h}d | Δ {h}d [95%]" for h in H_RUN) + " |", "|---|" + "---|---|" * len(H_RUN)]
            for n in [n for n in names if n in CMP]:
                cells = []
                for h in H_RUN:
                    c = CMP[n].get(scope, {}).get(str(h))
                    cells += ["–", "–"] if not c else [f"{c['mae']:.2f}", "" if n == "base" else f"{c['d']:+.3f} [{c['lo']:+.3f}, {c['hi']:+.3f}]"]
                L.append(f"| {n} | " + " | ".join(cells) + " |")
            L.append("")
    L += ["## Jump chance, ranges and cost", "",
          "`AUC`/`Brier`: the 7-day 5c+ jump classifier, all fuels, 2021–26. `cover`: share of actual 7-day moves inside an 80% "
          "range set from the variant's own errors over the year before each month (×today's wholesale volatility, as live); "
          "`width`: its mean width, c/L. From 2022, so a year of errors exists. `fit s`: the whole walk-forward.", "",
          "| variant | AUC | Brier | cover 7d | cover 7d shock | cover 7d calm | width 7d | cover 14d shock | fit s | in-sample bias 7d |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for n in names:
        x = R[n].get("extra")
        if not x: continue
        cv = x.get("cover") or {}
        g = lambda h, k: (cv.get(str(h)) or {}).get(k)
        L.append(f"| {n} | {num(x.get('auc'), '{:.3f}')} | {num(x.get('brier'), '{:.4f}')} | {num(g(7, 'all'), '{:.0%}')} | "
                 f"{num(g(7, 'shock'), '{:.0%}')} | {num(g(7, 'calm'), '{:.0%}')} | {num(g(7, 'width'))} | {num(g(14, 'shock'), '{:.0%}')} | "
                 f"{num(x.get('fit_s'), '{:.0f}')} | {num(x.get('fit_bias7'), '{:+.3f}')} |")
    L.append("")
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


def compare(preds, out, draws=2000, block=3):
    """Every variant's errors against `base` on the same rows: MAE per horizon and the paired difference, with a 95%
    interval from resampling whole calendar months (errors inside a month are correlated: overlapping 7- and 14-day
    windows, shared wholesale moves) and so are neighbouring months (2022's shock lasted eight), so whole months are
    drawn in overlapping 3-month blocks, wrapping round. Every variant gets the same draws for a scope and horizon.
    preds: a directory of preds-<variant>/backtest_preds.parquet."""
    import numpy as np, pandas as pd
    P = {d[len("preds-"):]: pd.read_parquet(f"{preds}/{d}/backtest_preds.parquet") for d in sorted(os.listdir(preds))
         if d.startswith("preds-") and os.path.exists(f"{preds}/{d}/backtest_preds.parquet")}
    if "base" not in P: print("compare: no base predictions", file=sys.stderr); return
    key = ["date", "fuel", "h"]
    b = P["base"][key + ["actual", PROD]].rename(columns={PROD: "pb"})
    res = {}
    for n, p in P.items():
        j = b.merge(p[key + [PROD]], on=key)
        j["eb"], j["ev"] = (j.actual - j.pb).abs(), (j.actual - j[PROD]).abs()
        j["m"] = j.date.dt.to_period("M")
        res[n] = {}
        for si, scope in enumerate(["all", "U91"]):
            res[n][scope] = {}
            for h, g in j[(j.fuel == "U91") if scope == "U91" else slice(None)].groupby("h"):
                s = g.assign(d=g.ev - g.eb).groupby("m").agg(d=("d", "sum"), n=("d", "size"))
                k = len(s); nb = -(-k // block)
                start = np.random.default_rng([si, int(h), k]).integers(0, k, size=(draws, nb))
                idx = ((start[:, :, None] + np.arange(block)) % k).reshape(draws, -1)[:, :k]
                boot = s.d.values[idx].sum(1) / s.n.values[idx].sum(1)
                res[n][scope][str(int(h))] = {"mae": round(float(g.ev.mean()), 3), "d": round(float(g.ev.mean() - g.eb.mean()), 4),
                                              "lo": round(float(np.quantile(boot, 0.025)), 4), "hi": round(float(np.quantile(boot, 0.975)), 4),
                                              "rows": int(len(g)), "months": int(len(s))}
    json.dump({"compare": res}, open(f"{out}/compare.json", "w"), indent=1)
    print(json.dumps({n: {s: r[s].get("7") for s in r} for n, r in res.items()}, indent=1))


if len(sys.argv) > 1 and sys.argv[1] == "--report":
    report(sys.argv[2]); sys.exit(0)
if len(sys.argv) > 1 and sys.argv[1] == "--list":
    print(json.dumps(list(VARIANTS))); sys.exit(0)
if len(sys.argv) > 1 and sys.argv[1] == "--ensembles":
    print(" ".join(ENSEMBLES)); sys.exit(0)
if len(sys.argv) > 1 and sys.argv[1] == "--compare":
    compare(sys.argv[2], sys.argv[3]); sys.exit(0)

# ---------------------------------------------------------------- one variant (or an ensemble of saved ones)
BASE, NAME, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
EXTRA, HALF_LIFE, ALPHA, TGP_LAG, SEED, LEARNER = VARIANTS["base" if NAME in ENSEMBLES else NAME]
QUICK = os.environ.get("QUICK") == "1"
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


def _fit(m, X, y, w):
    return m.fit(X, y) if w is None else m.fit(X, y, sample_weight=w)


def lgb_huber(y, p):
    """LightGBM's huber objective for XGBoost: the gradient is the residual clipped at alpha and the hessian is 1
    (LightGBM RegressionHuberLoss), so XGBoost gets the same loss and the same leaf values, not pseudo-Huber's."""
    return np.clip(p - y, -ALPHA, ALPHA), np.ones_like(p)


def xgb_kw(t):
    kw = dict(n_estimators=400, learning_rate=0.03, tree_method="hist", subsample=0.8, colsample_bytree=0.8,
              reg_lambda=2.0, n_jobs=-1, random_state=0 if SEED is None else SEED)
    return kw | (dict(grow_policy="lossguide", max_leaves=15, max_depth=0) if LEARNER == "xgb" else dict(max_depth=4))


CAT = lambda: dict(boosting_type="Ordered", iterations=400, learning_rate=0.03, depth=4, l2_leaf_reg=2.0, rsm=0.8, bootstrap_type="Bernoulli",
                   subsample=0.8, random_seed=0 if SEED is None else SEED, thread_count=-1, verbose=0, allow_writing_files=False)


def prep(fs, onehot):
    """Fold-local preprocessing for learners without native missing values: median fill plus a missing flag (CRACK is
    blank on every petrol row, the rolling features at the start), and for the linear model scaling and one-hot fuel/day."""
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    imp = lambda: SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)
    if not onehot: return imp()
    cat = [c for c in ("fuel_id", "dow") if c in fs]
    return ColumnTransformer([("num", make_pipeline(imp(), StandardScaler()), [c for c in fs if c not in cat]),
                              ("cat", OneHotEncoder(handle_unknown="ignore"), cat)])


FIT_BIAS, BIAS_S = [], [0.0]   # BIAS_S: time spent on the check, left out of the fit time   # mean in-sample residual of each 7-day fit: a loss or base-score mismatch shows up here first


def reg(t, fs, y, t0):
    w = weights(t, t0)
    if LEARNER in ("lgbm", "lgbm_linear"):
        lin = dict(linear_tree=True, linear_lambda=1.0) if LEARNER == "lgbm_linear" else {}
        m = _fit(lgb.LGBMRegressor(objective="huber", alpha=ALPHA, **lin, **PARAMS), t[fs], t[y], w)
    elif LEARNER in ("xgb", "xgb_depth"):
        import xgboost as xgb
        # min_child_weight is a hessian sum; with hessian 1 it is a row count, as LightGBM's min_child_samples=40
        m = _fit(xgb.XGBRegressor(objective=lgb_huber, base_score=float(t[y].mean()), min_child_weight=40, **xgb_kw(t)), t[fs], t[y], w)
    elif LEARNER == "cat":
        from catboost import CatBoostRegressor
        m = _fit(CatBoostRegressor(loss_function=f"Huber:delta={ALPHA}", **CAT()), t[fs], t[y], w)
    else:
        from sklearn.pipeline import make_pipeline
        assert w is None, "recency weights are only wired for the boosted learners"
        if LEARNER == "linear":
            from sklearn.linear_model import HuberRegressor
            est = make_pipeline(prep(fs, True), HuberRegressor(epsilon=1.35, alpha=1e-3, max_iter=1000))
        else:
            from sklearn.ensemble import ExtraTreesRegressor
            est = make_pipeline(prep(fs, False), ExtraTreesRegressor(n_estimators=200, min_samples_leaf=40, max_features=0.5,
                                                                    n_jobs=-1, random_state=0 if SEED is None else SEED))
        m = est.fit(t[fs], t[y])
    if y == "y7":
        tb = time.time(); FIT_BIAS.append(float((t[y] - m.predict(t[fs])).mean())); BIAS_S[0] += time.time() - tb
    return m


def clf(t, fs, t0):
    w = weights(t, t0)
    if LEARNER in ("lgbm", "lgbm_linear"):
        lin = dict(linear_tree=True, linear_lambda=1.0) if LEARNER == "lgbm_linear" else {}
        return _fit(lgb.LGBMClassifier(**lin, **PARAMS), t[fs], t.y_jump7, w)
    if LEARNER in ("xgb", "xgb_depth"):
        import xgboost as xgb
        pb = float(t.y_jump7.mean())
        # logistic hessians are p(1-p): 40 rows at the base rate, so the leaf-size limit means what LightGBM's does
        return _fit(xgb.XGBClassifier(objective="binary:logistic", base_score=pb, min_child_weight=40 * pb * (1 - pb),
                                      **xgb_kw(t)), t[fs], t.y_jump7, w)
    if LEARNER == "cat":
        from catboost import CatBoostClassifier
        return _fit(CatBoostClassifier(loss_function="Logloss", **CAT()), t[fs], t.y_jump7, w)
    from sklearn.pipeline import make_pipeline
    if LEARNER == "linear":
        from sklearn.linear_model import LogisticRegression
        return make_pipeline(prep(fs, True), LogisticRegression(C=1.0, max_iter=2000)).fit(t[fs], t.y_jump7)
    from sklearn.ensemble import ExtraTreesClassifier
    return make_pipeline(prep(fs, False), ExtraTreesClassifier(n_estimators=200, min_samples_leaf=40, max_features=0.5, n_jobs=-1,
                                                               random_state=0 if SEED is None else SEED)).fit(t[fs], t.y_jump7)


t_start = time.time()
if NAME in ENSEMBLES:   # average the members' saved walk-forward predictions; nothing is refitted
    pre = os.environ["PREDS"]
    Ps = [pd.read_parquet(f"{pre}/preds-{v}/backtest_preds.parquet").set_index(["date", "fuel", "h"]) for v in ENSEMBLES[NAME]]
    Cs = [pd.read_parquet(f"{pre}/preds-{v}/backtest_cls.parquet").set_index(["date", "fuel"]) for v in ENSEMBLES[NAME]]
    ix = Ps[0].index
    for p in Ps[1:]: ix = ix.intersection(p.index)
    P = Ps[0].loc[ix, ["actual"]].assign(**{PROD: np.mean([p.loc[ix, PROD].values for p in Ps], axis=0)}).reset_index()
    ic = Cs[0].index
    for c in Cs[1:]: ic = ic.intersection(c.index)
    C = Cs[0].loc[ic, ["y_jump7"]].assign(p=np.mean([c.loc[ic, "p"].values for c in Cs], axis=0)).reset_index()
else:
    # walk-forward, the same folds and training cut-offs as model.py's backtest
    preds, cls = [], []
    for m in pd.period_range("2025-10" if QUICK else "2021-01", (M.asof - pd.Timedelta(days=15)).strftime("%Y-%m"), freq="M"):
        t0 = m.start_time
        te_all = F[F.date.dt.to_period("M") == m]
        for h in H_RUN:
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
        print(m, f"{time.time() - t_start:.0f}s", flush=True)
    P = pd.concat(preds, ignore_index=True); C = pd.concat(cls, ignore_index=True)
FIT_S = time.time() - t_start - BIAS_S[0]

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


def cover():
    """80% ranges as the live ones are built (model.py: the 80th percentile of |error| / wholesale volatility over the last
    year, times today's volatility), but rolled forward: each month's range comes only from errors whose outcome was
    known before the month began. Coverage and mean width per horizon, overall and in model.py's shock months."""
    out = {}
    q = P.assign(v=[float(M.VOL[f].get(d, 1.0)) for f, d in zip(P.fuel, P.date)])
    q["r"] = (q.actual - q[PROD]).abs() / q.v
    for h in (7, 14):
        g = q[q.h == h]; parts = []
        for m in sorted(g.date.dt.to_period("M").unique()):
            t0 = m.start_time
            past = g[(g.date + pd.Timedelta(days=h) < t0) & (g.date >= t0 - pd.Timedelta(days=365 + h))]
            if t0 < pd.Timestamp("2022-01-01") or len(past) < 500: continue
            k = past.groupby("fuel").r.quantile(0.8)
            cur = g[g.date.dt.to_period("M") == m]
            hw = cur.fuel.map(k).fillna(past.r.quantile(0.8)) * cur.v
            parts.append(pd.DataFrame({"in": (cur.actual - cur[PROD]).abs() <= hw, "w": 2 * hw, "shock": str(m) in SHOCK}))
        if not parts: continue
        z = pd.concat(parts)
        f = lambda s: round(float(s.mean()), 3) if len(s) else None
        out[str(h)] = {"all": f(z["in"]), "shock": f(z["in"][z.shock]), "calm": f(z["in"][~z.shock]), "width": f(z.w)}
    return out


def extra():
    ok = C.y_jump7.nunique() > 1
    return {"auc": round(float(roc_auc_score(C.y_jump7, C.p)), 4) if ok else None,
            "brier": round(float(((C.p - C.y_jump7) ** 2).mean()), 5), "cover": cover(),
            "fit_s": round(FIT_S, 1), "fit_bias7": round(float(np.median(FIT_BIAS)), 4) if FIT_BIAS else None,
            "learner": "ensemble:" + "+".join(ENSEMBLES[NAME]) if NAME in ENSEMBLES else LEARNER, "quick": QUICK}


res = {}
GUARD = "guard" + NAME[4:] if NAME in ("base", "base_lag7") else None   # the rule-level benchmark, on the same wholesale lag
for name, guard in [(NAME, False)] + ([(GUARD, True)] if GUARD else []):
    rows = rows_for(guard)
    if not guard: own_recent = tally([r for r in rows if r["fuel"] == "U91" and r["date"] > (pd.Timestamp(max(r["date"] for r in rows)) - pd.Timedelta(days=TA.RECENT_DAYS)).date().isoformat()])
    sc, months = scored(rows)
    res[name] = {"score": sc, "months": months, "err": errors(), "calib": None if guard else calib(),
                 "app_replay_u91_recent": mine["U91"].get("recent") if mine else None}
res[NAME]["extra"] = extra()

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
