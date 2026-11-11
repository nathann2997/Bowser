# Model inputs: what would improve the forecast (2026-11-11)

Question: which extra data would make the forecast more accurate, using only sources that are free and whose terms allow this use? Five ideas were tested. Two were built into the pipeline, one runs on trial beside the live forecast, and two were rejected.

## Method

- **Data:** the `data` branch as of 2026-11-11 (history to 2026-10-31).
- **Test:** the production walk-forward (`model.py --backtest`): refit each month from 2021-01, predict that month, horizons 1, 3, 7 and 14 days, 2,130 days × 5 fuels. A separate harness rebuilt `model.py`'s features and matched them exactly, and matched its 7-day errors to within 0.03 c/L.
- **Measures:**
  - 7-day error: mean absolute error of the 7-day forecast, c/L.
  - Money: c/L gained per call by following the verdict, scored as `track_api.py` does. This is the measure that decides.
  - Wait-before-jump: "Wait" calls followed by a 5c+ rise within the week.
- **Noise:** refitting with a different random seed moves the petrol 7-day error by about 0.02 c/L and money by 0.01 (0.03 in 2026 alone). Differences of that size mean nothing.
- **Significance:** each comparison is paired by month (70 months); t is the paired t-statistic.

## Findings

### 1. The inputs were older than the test assumed (built)

The model is fitted on wholesale and oil prices one day old. The pipeline was getting them weekly:

| Input | Source | New rows arrive | Age when the forecast is made |
|---|---|---|---|
| Wholesale (TGP) | AIP workbook | Fridays | 0–6 days |
| Brent, NY Harbor diesel | EIA history files | Thursdays (Sydney) | 2–8 days |

Measured on 151 pipeline runs from 21 Oct to 11 Nov 2026: TGP was 3.4 days old on average and Brent 5.4. The backtest, and so the app's tested track record, assumed one day for both.

Scoring the same model with inputs as old as they really were:

| | Tested as published (1 day old) | As the pipeline really ran | With the two daily pages |
|---|---|---|---|
| Money, 2021–26 (c/L per call) | 4.96 | 4.81 | 4.94 |
| Money, 2026 | 3.69 | 2.95 | 3.56 |
| Share of perfect hindsight, 2026 | 66% | 53% | 64% |
| Wait-before-jump, 2021–26 | 134 | 183 | 126 |
| Petrol 7-day error, 2026 (c/L) | 7.91 | 8.56 | 8.12 |
| Diesel 7-day R², 2026 | 0.12 | −0.02 | 0.09 |

The gain from the daily pages over the real pipeline is +0.12 c/L per call over 2021–26 (t = 2.4) and +0.61 in 2026 (t = 1.9). The last column is the new `model.py` run end to end, not the harness.

**The two pages:**
- **AIP terminal gate prices page:** the last five business days, "collated each weekday morning" (on 12 Nov that day's price was up by 09:55). It matched the workbook on every date they shared.
- **EIA Today in Energy daily prices page:** the previous US close, each US weekday morning (before Sydney's first run), except US federal holidays. Brent matched EIA's history file on five dates checked back to 2024, and NY Harbor diesel on three (to the page's two decimals). In Sydney the newest close is 2 days old Wednesday to Saturday, 3 on Sunday and 4 on Monday and Tuesday.

Both are the same series from the same publishers the pipeline already used, so no new terms apply (`DATA-LICENSE.md`).

**On the day of this analysis** the live model was using TGP 212.8 and Brent US$107.0; the real figures were 204.3 and US$91.0. With them the 7-day U91 forecast moved from −7.5c to about −11.8c.

### 2. The tested track record now assumes what the live forecast gets (built)

`model.py` reads Brent and diesel at the ages the EIA daily page gives (above) in the fit, the backtest and the live row. The tested figures fall slightly as a result (U91 7-day error 4.91 → 4.95 c/L; money 4.96 → 4.94), and that is the honest figure. One gap remains: after a US federal holiday (about 11 a year) the page is a trading day behind for a day or two, which the test doesn't model. Fitting on the realistic ages scored the same as fitting on one-day-old data (within noise).

Fitting on the old weekly ages, with no new data, recovered little: 2026 money 2.95 → 3.14 (t = 1.1).

Using today's TGP instead of yesterday's tested slightly better again (2026 money 3.80), but AIP posts it during the morning and the first run is at 05:13, so the morning call would be fitted on something it may not have. Not built.

### 3. Station-level features (on trial, not live)

The stored price-change history has every station's prices, but the model only sees daily summaries. Its view of a restoration is the 90th percentile, which doesn't move until a tenth of stations have hiked. Eleven features were added (`station_feats.py`): the share of stations up 5c+ on 1, 3 and 7 days ago, the same for the leading brands and the rest, the share priced 8c+ over the median, and the 95th percentile.

| 2021–26, with the daily pages | Without | With station features |
|---|---|---|
| Petrol 7-day error (c/L) | 5.21 | 4.87 (t = −4.1) |
| Diesel 7-day error | 2.56 | 2.48 |
| Money (c/L per call) | 4.94 | 5.03 (t = 3.6) |
| Money, 2026 | 3.52 | 3.78 |
| Wait-before-jump | 129 | 106 |

This was the largest gain found. It is not live, for three reasons:
- **Time of day.** The test scores end-of-day prices. The call people act on is the first of the day, and only 7% of a day's hikes are in by 06:00. A restoration that starts mid-morning is invisible to the morning call.
- **Short check against live data.** The features were rebuilt from the archived snapshots on the 17 days that snapshots and published history overlap. The eleven kept correlate 0.94 or higher with their history values. Three others did not reproduce (98th percentile 0.23, share 15c over the median 0.44, share cutting 0.63) and were dropped, which cost some of the gain (all fourteen: money 5.07).
- **Selection.** The set was chosen after seeing results, and the 2026-only change in petrol 7-day error is not clear (8.07 → 7.82 c/L, t = −0.8).

So `model.py` logs a shadow forecast with these features beside the live one, at the first and the latest run of each day (`store/shadow.csv`). `python pipeline/shadow_score.py BASE` compares them on the money measure.

**Decision rule:** look at the `first` rows (the scorer only counts those logged before 12:00) once at least six weeks are scored and they include two or more restorations. Make the features live if the shadow's gain is higher there. To do it, add `SF.COLS` to `FD` in `model.py` and bump `BT_VERSION`.

### 4. Petrol crack spread (rejected)

A gasoline price against Brent, as the diesel model has for diesel. Tested with three EIA spot series (NY Harbor and Gulf Coast conventional, Los Angeles RBOB). All three made petrol worse: 7-day error 5.19 → 5.25–5.30 c/L, money 4.94 → 4.90–4.94.

### 5. Singapore benchmarks and a futures curve (not buildable)

- **Singapore Mogas 95 and Gasoil 10ppm** are Platts assessments, sold by subscription. No free daily source was found.
- **Futures:** EIA stopped publishing NYMEX futures on 2024-04-05, and its daily page shows them as "NA". Yahoo Finance's data is for personal use only.
- **Would they help?** Probably. US product prices one day old predict the next week's TGP change better than Brent alone (out-of-sample R² 0.27 against 0.22 for petrol, 0.42 against 0.31 for diesel). At the age the free EIA page gives, that falls by about half.

### Also tested, no clear gain

- **Brent in c/L and the TGP-to-Brent gap** ("wholesale catch-up"): within noise.
- **Gulf Coast diesel in place of NY Harbor** for the diesel crack: diesel 7-day error 2.53 → 2.50 and jump AUC 0.89 → 0.91, money +0.01. Small but consistent, and the daily page carries it. A candidate for later.

## What changed in the pipeline

See the CHANGELOG entry of 2026-11-11, "Fresh wholesale and oil prices; shadow forecast with station features".

## Not in the repo

The harness, the experiment outputs and the saved pages were in the session's scratch folder and are not kept. The method above is enough to rebuild them: the harness was `model.py`'s `features()` with each input lagged by a per-weekday age.
