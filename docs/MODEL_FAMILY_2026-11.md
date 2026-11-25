# Which learner: LightGBM, XGBoost and the alternatives (2026-11)

`sydney/pipeline/experiment.py` on branch `model/gbm-compare`, `model-experiment.yml` on GitHub Actions, on a read-only
copy of the `data` branch. Nothing published changes: `model.py` is untouched and the workflow's `same-forecast` job
checks that. The decision rule is in the script's docstring and was committed before the first run.

## The question

Production fits LightGBM: a Huber (alpha 3) regressor per horizon (1, 3, 7, 14 days) and a classifier for a 5c+ jump
within 7 days, on ~40 features (wholesale TGP, Brent/AUD, margins, station spread, cycle memory), one model for petrol
fuels and a second, with diesel crack features, for diesel. About 15,000 training rows (eight years × five fuels).

Is another learner better? The first question is LightGBM vs XGBoost. The second is whether any family we haven't tried
does something LightGBM structurally can't.

## Priors (from what is already known)

- **The learner is probably not the lever.** The 2026-11 experiment (`docs/RULE_ANALYSIS_2026-10.md`) found ten
  variants within ±0.04c seed noise, and that wholesale freshness moved results 4–7× more than any model change.
- **LightGBM and XGBoost are the same algorithm family.** Both are second-order gradient-boosted trees with histogram
  splits and L2 leaf regularisation. Their real differences are the default growth policy (LightGBM leaf-wise, XGBoost
  level-wise), how they bin features and route missing values, and engineering (speed, memory). Once growth, loss and
  capacity are matched, they should agree to within seed noise on 15k rows. The test is built to check that.
- **Trees can't extrapolate.** A tree predicts a constant per leaf, so a wholesale move larger than anything in the
  training data is forecast as the largest move it has seen. That is the 2026 weakness (sustained wholesale swings),
  and it is the one place where a different structure, such as linear leaves or a linear model, could help.
- **The 80% ranges under-cover in shocks** (`model.py`'s `vol_ratio` note: 0.69 at 7 days, 0.61 at 14 before the
  volatility scaling). A learner whose errors are steadier across regimes would make ranges more honest. Coverage is
  scored for that reason.

## What is tested, and why

Every learner gets the same features, monthly folds from 2021-01, training cut-offs, petrol/diesel split and targets.
Only the estimator changes. Capacity is matched, not parameter names: 400 rounds at learning rate 0.03, about 15
leaves, 80% row and column sampling, L2 2 on leaf values.

| variant | what it is | why |
|---|---|---|
| `base` | production LightGBM | the reference; also checked against the stored production backtest |
| `base_seed2` | the same, another seed | LightGBM's noise floor |
| `xgb` | XGBoost, leaf-wise, 15 leaves, **LightGBM's exact Huber loss** (custom objective: clipped gradient, hessian 1), `min_child_weight` 40 | the like-for-like comparison: same loss, growth and leaf-size rule, so any gap is the library |
| `xgb_seed2` | the same, another seed | XGBoost's own noise floor (its sampling differs from LightGBM's) |
| `xgb_depth` | XGBoost level-wise to depth 4 (≤16 leaves) | how XGBoost is normally used: does growth policy matter here? |
| `catboost` (+ `_seed2`) | CatBoost, symmetric depth-4 trees, ordered boosting, Huber 3 | the GBM most different in design; symmetric trees and ordered boosting are known to resist overfitting on small, noisy tables |
| `lgbm_linear` | LightGBM with a linear model in each leaf | can extrapolate a wholesale trend beyond the training range |
| `linear` | Huber regression / logistic regression, fold-local median fill + missing flags + scaling + one-hot fuel and weekday | what do trees add at all? |
| `extratrees` (+ `_seed2`) | bagged randomised trees, 200 trees, min 40 rows a leaf | a variance-reducing, non-boosted family |
| `avg3` | average of `base`, `xgb`, `catboost` predictions | ensembles of different GBMs often beat each member; averaged from saved predictions, not refitted |

Two matching details that would otherwise bias the comparison:

- XGBoost's `min_child_weight` is a sum of hessians, not a row count. With the custom Huber loss the hessian is 1, so
  40 means 40 rows, as in LightGBM. For the classifier the hessian is p(1−p), so the limit is set to 40 × p̄(1−p̄).
  Copying `40` straight across would have crippled XGBoost's jump classifier.
- XGBoost's built-in `reg:pseudohubererror` is not LightGBM's Huber: its hessian shrinks with large errors, which
  changes the leaf values. The custom objective gives XGBoost exactly LightGBM's loss.

## Scored on

- **Forecast error:** MAE at 1, 3, 7 and 14 days, all fuels pooled and U91, paired against `base` on the same rows,
  with a 95% interval from a moving-block bootstrap of 3-month blocks (errors within and across neighbouring months are correlated; the 2022 shock lasted eight months).
- **What users get:** the app's tested figure (verdict rule, c/L saved against filling the day you check, Waits
  before a jump, Gerrity skill), 2021–25 and 2026.
- **Jump chance:** AUC, Brier score, calibration on the days rated under 5%.
- **Ranges:** coverage of an 80% range built as the live one is (80th percentile of the learner's own past-year
  errors, scaled by wholesale volatility), rolled forward month by month, overall and in shock months; mean width.
- **Cost:** walk-forward fit time (`daily.yml` refits every model 5 times a day).

## Researched but not tested

| family | why not here |
|---|---|
| TabPFN / tabular foundation models | strong on small tables, but inference is slow without a GPU and the licence/weights download is a new dependency for a five-runs-a-day CPU job; revisit if a GPU runner is ever used |
| Deep sequence models (LSTM, TFT, N-BEATS/N-HiTS with covariates) | built for many long series; with five fuel series and ~15k rows they overfit, and they need tuning infrastructure the pipeline doesn't have |
| Time-series foundation models (Chronos, TimesFM, Moirai) | mostly univariate or weak on exogenous inputs, and wholesale TGP is the main signal; zero-shot price-cycle forecasts would ignore it |
| ARIMA / ETS / Prophet | can't use wholesale inputs well (ARIMAX can, linearly, which `linear` already covers), and Sydney's price cycle isn't a fixed seasonality |
| NGBoost / quantile GBMs for the ranges | the ranges are an empirical-quantile layer on top of the point model; a quantile learner is a separate, later experiment if coverage is still the problem |
| Random forest | ExtraTrees covers the bagged-trees family more cheaply |
| Hyperparameter search per learner | with 2026 already used for choosing, tuning on the same walk-forward would overfit the backtest; capacity-matched defaults keep the comparison about the learner |

## Results

Run 45540309359 (data to 2026-11-25; smoke test 45518266106). Full report: the run's `report` artifact.

**The harness reproduces production exactly:** `base` matches the stored production backtest on 42,895 rows (0.0c
difference), and its rows equal `track_api.replay`'s.

7-day MAE, paired against `base` (Δ, 95% 3-month block-bootstrap interval), and the app's tested figure:

| variant | Δ 7d pooled | Δ 7d U91 | save 2021–25 / 2026, pooled (Δ) | save 2026 U91 (Δ) | jump AUC | fit time |
|---|---|---|---|---|---|---|
| `base` (LightGBM) | 4.66c | 4.93c | 2.51 / 1.61 | 1.68 | 0.936 | 317 s |
| `base_seed2` | −0.004 [−0.027, +0.017] | −0.016 [−0.047, +0.014] | −0.01 / +0.01 | +0.01 | 0.936 | 315 s |
| `xgb` (matched) | −0.011 [−0.037, +0.012] | −0.016 [−0.053, +0.018] | −0.02 / −0.02 | +0.05 | 0.936 | 343 s |
| `xgb_seed2` | +0.014 [−0.009, +0.036] | +0.004 [−0.031, +0.037] | −0.01 / −0.00 | +0.02 | 0.935 | 552 s |
| `xgb_depth` | −0.053 [−0.129, +0.018] | −0.086 [−0.202, +0.020] | −0.02 / +0.01 | +0.00 | 0.938 | 333 s |
| `catboost` | −0.209 [−0.354, −0.070] | −0.090 [−0.337, +0.138] | +0.01 / +0.04 | +0.13 | 0.933 | 985 s |
| `catboost_seed2` | −0.067 [−0.211, +0.063] | +0.075 [−0.149, +0.286] | +0.00 / −0.01 | +0.08 | 0.934 | 1,318 s |
| `lgbm_linear` | +0.052 [−0.038, +0.154] | +0.080 [−0.024, +0.192] | −0.02 / −0.04 | +0.13 | 0.924 | 424 s |
| `linear` | +0.808 [+0.488, +1.115] | +0.424 [+0.087, +0.779] | −0.18 / +0.06 | +0.06 | 0.909 | 346 s |
| `extratrees` | +0.310 [+0.121, +0.500] | +0.482 [+0.235, +0.724] | −0.06 / −0.36 | −0.22 | 0.932 | 523 s |
| `avg3` (LGBM+XGB+Cat) | −0.151 [−0.207, −0.099] | −0.138 [−0.237, −0.050] | −0.00 / −0.04 | +0.03 | 0.937 | 1,644 s (sum) |

Range coverage (80% target, rolled forward): every learner gets 76–77% overall, 70–74% in shock months at 7 days and
64–71% at 14 days.

### Against the decision rule

- **`xgb`:** gain 0.011c pooled, 0.016c U91, inside its own seed gap (0.025 / 0.020) and with intervals spanning 0. Fails.
- **`xgb_depth`, `lgbm_linear`, `linear`, `extratrees`:** intervals span 0 or are worse. Fail.
- **`catboost`:** fails on U91: the interval spans 0 (−0.090 [−0.337, +0.138]). The pooled gain (0.209c) is
  significant and beats both seed gaps (its own 0.14c, 35× LightGBM's; U91 0.17c, about 10×). Its fit time (3.1×) is
  over the rule's 3× cap as written, though one run per runner can't measure that finely. Outside the rule: its 14-day
  error is worse (U91 +0.45c, interval above 0).
- **`avg3`:** the closest. Significant on both scopes at 7 and 3 days, but the U91 gain (0.138c) is inside CatBoost's
  seed gap (0.165c), the pooled 2026 saving is −0.04c (the rule says it must not fall, though that size is within save
  noise) and it costs about 5× the fit time. It also averages in the luckier CatBoost seed (−0.21c pooled against the
  other seed's −0.07c), so its gain is probably overstated. Fails.

## Decision

**No learner advances; LightGBM stays.** Nothing goes to a shadow trial.

**XGBoost vs LightGBM:** the same model here. With the loss, growth and leaf-size rule matched, XGBoost's 3-, 7- and
14-day errors are within 0.02c of LightGBM's, inside XGBoost's own seed gap (0.025c pooled at 7 days), and its calls
and jump AUC are the same. The only hint of a difference: both XGBoost seeds are slightly worse at 1 day pooled (+0.005
to +0.006c, intervals just above 0; not for U91), about 0.5% of the error and borderline against LightGBM's own seed
copy (+0.003c), so trivial. Level-wise growth (`xgb_depth`) doesn't change that. There is no reason to switch, and none to add
XGBoost as a dependency.

**Fit time:** one run per runner can't separate learners closer than about 2×: identical settings differed by 60–70%
(`xgb` 343 s vs `xgb_seed2` 552 s; `extratrees` 523 vs 312 s). Only the ensemble's cost (sum of members, ~5×) is clear.

What the run says beyond the rule:

1. **Trees earn their place.** Linear regression is 0.8c (17%) worse at 7 days and in 2026 makes 74% more Waits before a
   jump (pooled; U91 +58%).
   The interactions (margin × wholesale × cycle phase) matter.
2. **Lower MAE doesn't mean better calls.** `avg3` cuts 7-day error 3% with tight intervals, yet its calls show no
   measurable gain (saving within ±0.04c of `base`). The verdict depends on crossing thresholds (d3 ±1.5, d7 ±2/−3, jump 35/50%), not on average error. A future
   model change should be judged on the calls, as this harness does, not on MAE.
3. **CatBoost is unstable here.** Its two seeds differ by 0.14c at 7 days pooled, and its gains don't survive a seed
   change. Likely cause (not tested): ordered boosting with 80% Bernoulli sampling on ~15k rows. ExtraTrees has the best Brier score and is the only
   learner whose low-band jump chances are calibrated (1.5% predicted, 1.5% actual against LightGBM's 0.9% / 7.1%), but
   its point forecasts and calls are clearly worse. `jump_floor.py` already handles that calibration gap.
4. **No learner fixes the ranges.** 80% ranges cover 76–77% overall (77–78% in calm months) and 70–74% in shock months
   at 7 days, 64–71% at 14 days, whatever the model. The learner doesn't fix it; the range layer (a year of errors ×
   volatility ratio) is the likely place to. That is the next lever if ranges matter: a regime-aware calibration (for example conformal intervals weighted toward recent
   or high-volatility months), tested in this harness with `cover()`.
5. **Every Huber model under-predicts at 7 days:** in-sample by +0.9 to +1.3c (LightGBM +1.19c), and out of sample in
   2026 by +0.8c (U91) and +1.4c (pooled) for LightGBM. Price
   changes are right-skewed (sharp restorations, slow declines) and Huber with alpha 3 lands between the median and the
   mean. Out of sample in 2026, squared-error ExtraTrees is near unbiased (+0.17c pooled, −0.42c U91) but less accurate;
   alpha 8 removed the bias in the 2026-11 experiment but cost 2021–25. (ExtraTrees' zero in-sample bias proves nothing:
   a squared-error forest fits leaf means.) This is a loss question, not a learner one, and it's already been tried.

As before, the lever is the inputs (wholesale freshness: 4–7× any model change in the 2026-11 run), not the learner.
The harness now takes a learner per variant (`VARIANTS`' last field), runs all four horizons, scores range coverage
and fit time, averages saved predictions into ensembles, and gives paired block-bootstrap intervals (`--compare`).
