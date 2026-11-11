# Bowser pipeline

Daily forecast of Sydney pump prices (U91, E10, Premium 95, Premium 98, diesel; the list is `pipeline/fuels.py`): a "fill up now or wait" signal, a 14-day outlook, a station finder and the evidence behind it.

## Daily flow
`.github/workflows/daily.yml` runs the pipeline on GitHub Actions up to 5 times a day (see the cron slots there):
1. `pipeline/fetch.py` writes the day's raw inputs into `inbox/`: NSW FuelCheck live prices (required), Brent from the US EIA (which sources it from Refinitiv), AUD/USD from the RBA (sourced from WM/Reuters), AIP terminal gate prices and any newly published NSW monthly history (all best-effort). The AIP workbook and EIA's history files only gain a week's rows at a time, so two daily pages fill the days after them: AIP's terminal gate prices page and EIA's daily prices page (`pages.py` parses both; the weekly files win wherever they have a value). Brent and AUD/USD don't come from FRED, whose terms bar using its content to train models. Neither is relicensed here (see `DATA-LICENSE.md`). `update.py` stores them in `store/fred.csv` under FRED's column ids, so `model.py` reads them unchanged.
2. `pipeline/run_daily.sh`: rebuilds history when a new month arrives, or once when `store/station_feats.csv` is missing (`build_history.py`, `station_profile.py`), adds today's snapshot (`update.py`), then retrains and forecasts (`model.py`). `model.py` also logs a shadow forecast, the same model plus station-level features (`station_feats.py`), to `store/shadow.csv`; it is on trial and never published, and `python pipeline/shadow_score.py BASE` compares it with the live one (`docs/MODEL_INPUTS_2026-11.md`). The walk-forward backtest (`model.py --backtest`, about 8 minutes) runs once every 28 days, on request (`workflow_dispatch` input `backtest`), or by itself on the first run after the model's features change (`BT_VERSION` in `model.py`).
3. `pipeline/export_api.py` runs `build.py` (the dashboard) and writes the app API, with `station_api.py` for the per-station files and `track_api.py` for the track record. It fails if the data isn't today's or a check fails.
4. State (`store/`, `archive/`) is committed to the `data` branch; the API and dashboard are deployed to GitHub Pages at https://nathann2997.github.io/FuelForecast/.

Needs repo secrets `NSW_API_KEY` / `NSW_API_SECRET` and Pages set to deploy from GitHub Actions.

API (`https://nathann2997.github.io/FuelForecast/api/v1/`), static JSON regenerated daily:
| File | What |
|---|---|
| `meta.json` | schema version, generated time, as-of date per source, file sizes (`station/` = total bytes of the station files, `station/count` = how many). Check `asof` for staleness |
| `forecast.json` | `live[]` per fuel (now, d1/d3/d7/d14 with lo/hi ranges, p_jump7, `verdict`), `ctx`, `stats`, `brands`, `bt` (backtest) |
| `stations.json` | `stations[]` with `id` (NSW station code) and `p: {fuel: [price, days since update, advice code, advice label, reason, 7-day forecast price]}` (index 5 = the station file's `fc.now + fc.d7`; left off, tuple length 5, on a day the station files failed); `suburbs[]` centroids for radius search |
| `station/{id}.json` | one station (`StationDetail` in `app/src/lib/types.ts`): `hist[fuel]` end-of-day price for the 400 days from `start` to `asof` (monthly history, then the `archive/` snapshots, then today; carried forward up to 30 days, else null), `profile` (`typ`, `lag`, `part`, `n`), and `fc[fuel]`, the station's own 14-day forecast (`now`, d/lo/hi at 1/3/7/14 days, `rise` date, `adv` as in `stations.json`). Method in `pipeline/station_api.py`. About 8 KB each |
| `history.json` | `hist[fuel].{med,p10,p90}` and `tgp.{ulp,dl}`, daily from `start` |
| `track.json` | the track record (`pipeline/track_api.py`): `calls[]` (the first call of each Sydney day per fuel, last 60 days, newest first: `date, fuel, cls, head, now, move, days, status`), `live[fuel]` and `replay[fuel]` tallies (`n, right, close, wrong, from, to`, plus `gain`: the average value of following the call in c/L, and `by`: the counts per call type; `live` adds `since` and `pending`; `replay` adds `base`: the best always-the-same-call rule and its right count, and `recent`: the same tally over the last 12 months). Each call is scored on the average median over the 7 days after it; today, a partial day, never counts. Live calls are appended to `store/calls.csv` on the `data` branch; `replay` applies the same verdict rule to the walk-forward backtest. Fails soft (no file plus a `meta.warnings` entry) |

The site also serves `s/?id=<station code>&f=<fuel>`, the share page behind the app's Share button (`pipeline/share.html`, published by `export_api.py` with a hash-pinned CSP). It reads `stations.json` and `forecast.json` from this API and shows the station's pump prices and advice to friends without the app.

## Testing a change
Nothing is run from a laptop. Open a PR (or push to `main`) and `.github/workflows/pipeline-ci.yml` runs the unit tests (`pipeline/test_*.py`), then the whole pipeline on a copy of the `data` branch, using the newest archived NSW snapshot in place of the fetch step, so it needs no keys. It keeps the site it built as a run artifact (`site`, 3 days) to compare with the live one, and saves and deploys nothing.

Keys exist only as GitHub Actions secrets (`NSW_API_KEY`, `NSW_API_SECRET`, optional `VIC_API_KEY`); `fetch.py` reads them from the environment and there is no credentials file. Only Actions writes to the `data` branch: the save job refuses to save if the branch moved during a run.

## Layout
`pipeline/` is on `main`; everything else is on the `data` branch.

| Path | What |
|---|---|
| `pipeline/` | all code (tests are `test_*.py`) |
| `store/daily.csv` | Sydney daily price summary per fuel, Jan 2019 onward (history + daily snapshots) |
| `store/events/` | Sydney price-change records from the NSW monthly files |
| `store/tgp.csv`, `store/fred.csv` | wholesale TGP (AIP), Brent and AUD/USD (EIA and RBA; the file keeps FRED's name and column ids) |
| `store/eia_daily.csv` | the EIA daily page's readings (the page only shows the latest close), last 60 |
| `store/station_feats.csv`, `store/shadow.csv` | station-level features per day and fuel, and the shadow forecast logged beside the live one (trial only) |
| `store/backtest*` | walk-forward backtest results |
| `store/forecast.json`, `store/stations_today.json` | today's forecast and station prices |
| `archive/` | daily station-level Sydney snapshots (gzipped JSON) |
| `out/` | build output (`build.py`'s dashboard, `export_api.py`'s site); never committed |

Sydney = postcodes 2000-2234, 2555-2574, 2740-2786. Prices in cents per litre incl. GST.
Sources: NSW Government FuelCheck (API.NSW, data.nsw.gov.au; CC BY-SA 3.0 AU), Australian Institute of Petroleum (© AIP), Brent crude from the U.S. Energy Information Administration (Refinitiv), AUD/USD from the Reserve Bank of Australia (WM/Reuters). Licence and attribution for the data and the API: [`DATA-LICENSE.md`](../DATA-LICENSE.md). Every API file carries `generated_at` (the app's "Refreshed" time), plus `attribution` and `license_note`.

## Data health
`.github/workflows/data-health.yml` checks the published API after every run and every 30 minutes (`pipeline/health.py`), reruns the pipeline for problems a rerun fixes and re-enables a paused schedule (`pipeline/remediate.py`, within a daily budget), and alerts through a `data-health` GitHub issue. `export_api.py` also hides implausible prices before publishing. Alert codes and fixes: [`docs/DATA_HEALTH.md`](../docs/DATA_HEALTH.md).
