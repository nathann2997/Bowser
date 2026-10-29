# Session handoff — Bowser (FuelForecast)

Working notes so a fresh session can resume. Update before ending a session (or at ~70% context). The full history of every change, with commits, run ids and OTA update groups, is in `CHANGELOG.md`; this file only keeps what's current and what's still open.

## Where things stand (2026-10-29)
- **Pipeline:** GitHub Actions (`.github/workflows/daily.yml`, 5 runs a day) is the only pipeline. State lives on the `data` branch and the output on GitHub Pages: the dashboard at https://nathann2997.github.io/FuelForecast/ and the API under `/api/v1/`. The claude.ai scheduled task is disabled (2026-10-28), so `main`'s `sydney/store` stopped at 27 Oct. `data-health.yml` watches the API (`docs/DATA_HEALTH.md`).
- **App:** Bowser **0.8.0** (runtime 0.8.0) on Android: the Stations map plus everything before it. Preview APK: EAS build 69dad55d, https://expo.dev/accounts/nathann97/projects/fuel-forecast/builds/69dad55d-48de-4f95-90db-ade6fb1bbbf1. JS changes reach it as OTA updates on the `preview` channel. `app_release.json` points at 0.8.0, so older installs show the "new version" notice.
- **iOS:** compiles (simulator build 46497e9c) but isn't distributed; see the open item below.

## Product decisions (owner)
- Audience: the owner plus a handful of friends. Sydney only, no accounts.
- 2026-10-21 MVP: the "fill now / wait" signal and 1/3/7/14-day outlook, price history, and a nearest-stations list. A Stations **map** was added at the owner's request on 2026-10-26.
- Data as early as possible: 5 pipeline runs a day since 0.6.0.
- Stack: React Native + Expo (TypeScript), EAS Build APKs via an internal distribution link, OTA updates through EAS Update.
- Keep the "new version available" notice (`UpdateNotice` in the root layout) until Bowser is on an app store.

## Open work
Newest first. Each item has its CHANGELOG entry of the same name for details.

- **Analytics plan** (`docs/ANALYTICS_PLAN.md`, 2026-10-29): proposal, with the decisions marked **(decide)**.
- **Notifications plan** (`docs/NOTIFICATIONS_PLAN.md`, 2026-10-24): proposal, with the decisions marked **(decide)**.
- **Web dashboard map** (2026-10-28): **Next:** check the live map on a phone.
- **Premium 95** (2026-10-27): live. **Owner's call:** keep the shared model (the other fuels' 7-day error is up about 0.1c), or fit P95 separately. Device checks are in the CHANGELOG entry.
- **0.8.0 Stations map** (2026-10-26, reworked in 16f6ad5). **Next:** device check of the rework:
  - cluster counts show
  - tags recolour after a big pan
  - the card doesn't hide the tapped tag or the Google logo
  - clusters split on a tap
  - dark-mode contrast
- **OTA on first open** (2026-10-24): testers on an older OTA need two full restarts once (force stop, open, wait about 10 s, force stop, open); after that, updates show on the first open.
- **Design review, simpler Today** (2026-10-23). **Next:** a device check of Today with and without pins, and the Stations list on a Wait day.
- **0.7.0 analytics (EAS Insights + Observe)** (2026-10-22). **Next:** check the EAS dashboard (Insights → App usage; Observe → Errors, Navigation, Events) or run `npx eas-cli observe:events`. Owner decisions are in the CHANGELOG entry (store privacy forms, an opt-out switch).
- **Data health** (2026-10-22). **Next:** confirm an automatic run's `triggering_actor` is a Bot (`gh api repos/nathann2997/FuelForecast/actions/runs?per_page=5`) and that the job summary reads well. Dependabot has 3 alerts, in build tooling only, with no fixes released yet.
- **0.7 "prove it"** (2026-10-22, plan `docs/BOWSER_0.7_PLAN.md`). **Device checks:**
  - the keyboard lifts the Filled-up and discount sheets
  - the Share sheet on Android and iOS
  - the share link opens `/s/`, and "Have Bowser? Open it" opens the station
  - the widget shows your price after a discount change

  Fills and calls whose week overlaps 1–12 Oct show "pending" until NSW publishes October's history.
- **iOS build** (2026-10-22, `docs/IOS.md`). **Blocked on the owner:**
  - an Apple Developer Program account
  - a choice of TestFlight (recommended) or ad hoc

  Then run `npx eas-cli build -p ios --profile production --auto-submit` interactively once, so EAS can create the certificates, both bundle IDs and the app group.
- **0.6.0 feedback round** (2026-10-22). **Device checks:**
  - long one-thumb scrolls don't swipe a row
  - pull-to-refresh, and the AreaPicker keyboard
  - Map opens a labelled pin
  - widget taps, warm and cold; station-row taps open the app; no ⟳ on the widget
  - chip dots in light and dark
  - the Stations "Near you" line at home, after moving, and with location withdrawn
  - on the `data` branch: five commits a day, and `store/backtest_ran` written
- **Security hardening** (2026-10-22). **Pending a new native build:**
  - export the widget image provider (location leak)
  - `allowBackup`
  - unused template permissions
  - OTA code signing

  **Owner:** 2FA on Expo and GitHub; rotate the NSW secret if this folder was ever synced; delete the local `sydney/pipeline/pull_nsw.js`, which holds a key and is no longer used by anything.
- **Earlier device checks still open:**
  - v0.2/0.3.0: keyboard avoidance on Today's suburb search and the fuel sheet; widget placement, the 4 h refresh, a release launch without the R8 crash, chart scrubbing, directions
  - 0.4.0: the widget follows location
  - 0.5.0: welcome, swipe rows, rise alerts
  - new logo: launcher, themed icon, splash, widget

## Key facts
- Node 22 is at `~/.local/node/bin` (on PATH via `~/.zshrc`). App checks: `cd app && npx tsc --noEmit && npx expo lint && npx jest`. Pipeline tests: `python3 -m unittest sydney/pipeline/test_health.py`.
- Browser preview: `npx expo export --platform web`, serve it with an SPA fallback, and screenshot it with headless Chrome at ≥500 px wide.
- To check a pipeline change: run the pipeline on a copy of the `data` branch, and compare `export_api.py --allow-stale` output before and after, ignoring `generated_at`. The 2026-10-29 cleanup in the CHANGELOG shows how.
- API base: `https://nathann2997.github.io/FuelForecast/api/v1/`; the file schema is in `sydney/README.md`.
- `stations.json` per-fuel tuple: `[price, days since update, advice code, advice label, reason, 7-day forecast price]` (the last is left off on a day the station files failed). Advice codes: now, by, ok, wait, hi, any, chk.
- The verdict rule is in `template.html` (`verdict()`) and mirrored in `export_api.py`; change both together. The rise date is `market()` in `build.py`, ported to `app/src/lib/outlook.ts`.
- Workflow state lives on the `data` branch, never on `main`. Don't merge `data` into `main`.
- OTA updates: `--environment preview --upload-source-maps`. Each runtime's update-notice OTA is built from the `ota/<runtime>-update-notice` branches; 0.1.0 APKs have no expo-updates and can't be reached.
- **Release step:** after each native build, update `sydney/pipeline/app_release.json` (version, build URL, notes), push, then run `gh workflow run daily.yml`.
- Secrets never go in git: `sydney/pipeline/credentials.py`, `sydney/pipeline/pull_nsw.js` and `fuel-api-credentials.md` are gitignored.
- The track record ("Calls right") isn't on the web dashboard: it isn't in `__DATA__`.
- The Google Maps key `GOOGLE_MAPS_ANDROID_API_KEY` is set in EAS for preview and production; an Android build fails without it, by design.
- Web dashboard pins are keyed name|postcode|lat|lon (the dashboard data has no station codes), so they don't sync with the app. If `build.py` ever adds codes, switch the key to them.
- The owner has two Expo accounts (nathann97 and nathannguy); the project lives on nathann97.

## Open risks
- **Widget library:** `react-native-android-widget` has open issues.
  - #159: R8 release crash, mitigated by turning minify off.
  - #154: taps can stop after many redraws; the patch in PR #161 fixes it if testers hit it.
  - There's no picker preview image yet.
- **Station forecasts** reuse the Sydney path, shifted by the station's lag and damped by how often it joins jumps. There's no mean reversion for stations already well above their usual price, and the ranges are Sydney-wide.
- **October history:** 1–12 Oct 2026 is reconstructed from snapshots until the October monthly file lands.
- **"Shop around"** (`copy.ts`) still assumes a 50 L tank, not the user's `tankL`.
- **Expo Go** can't load our EAS updates; it's live-session only.
- **AIP and Brent/AUD** are best-effort: the model forward-fills them, and `meta.warnings` flags staleness.
- **GitHub cron** can start 10–30 min late. Scheduled workflows pause after 60 days without repo activity; the daily `data` commits count, and the save job re-enables the schedule.
- **Data licences** (`DATA-LICENSE.md`): the repo and API are public, so everything in them counts as published. NSW FuelCheck is CC BY-SA 3.0 AU and is attributed. **Open:**
  - AIP's TGP (© AIP, all rights reserved) is still republished: `tgp.csv`, `history.json` `tgp`, and the wholesale figures on Today and Trends. The owner was advised to email aip@aip.com.au.
  - Brent and AUD/USD come from the EIA and the RBA, but both cite commercial vendors (Refinitiv, WM/Reuters), and the raw series sit in the public `data` branch.
  - `main`'s `sydney/store/fred.csv` still holds old FRED values.
