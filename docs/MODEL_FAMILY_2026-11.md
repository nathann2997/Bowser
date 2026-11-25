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

_Pending the Actions run._

## Decision

_Pending._
