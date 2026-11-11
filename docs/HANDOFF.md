# Session handoff — Bowser

Working notes so a fresh session can resume. Update before ending a session (or at ~70% context). The full history of every change, with commits, run ids and OTA update groups, is in `CHANGELOG.md`; this file only keeps what's current and what's still open.

## Where things stand (2026-11-12)
- **Everything runs on GitHub Actions; nothing is run from a laptop.**
  - `daily.yml`: the pipeline, 5 runs a day. State lives only on the `data` branch; the output is on GitHub Pages (dashboard at https://nathann2997.github.io/Bowser/, API under `/api/v1/`).
  - `data-health.yml`: watches the API and fixes what a rerun fixes (`docs/DATA_HEALTH.md`).
  - `pipeline-ci.yml`: tests a pipeline change on a copy of the data, with no keys.
  - `app-ci.yml`: checks the app, then on `main` ships it: an OTA update for a JS change, or a new APK plus the update notice after a `version` bump.
- **App:** Bowser **0.9.1** (runtime 0.9.1) on Android. Preview APK: EAS build ad1c55ea, https://expo.dev/accounts/nathann97/projects/fuel-forecast/builds/ad1c55ea-4f63-4259-bc3e-9d52b059bbd7, built by `app-ci` (run 42969569188). `app_release.json` points at it. Not yet seen on a phone.
- **iOS:** compiles (simulator build 46497e9c) but isn't distributed; see the open item below.
- **Names:** the repo is `nathann2997/Bowser` (renamed 2026-11-11), so the site is https://nathann2997.github.io/Bowser/. The old `…/FuelForecast/` address is gone (404). Still `fuelforecast`, because installed apps depend on them: the Android package, iOS bundle id, Expo slug and URL scheme.

## Owner to do
- **Send testers the 0.9.1 install link** (above). Installs on 0.9.0 or older read the old address, so they show their last prices and no update notice.
- Add the repo secret `VIC_API_KEY` if the Victorian archive is wanted (optional).
- Delete the old key files on the laptop, which nothing reads any more: `sydney/pipeline/credentials.py`, `sydney/pipeline/pull_nsw.js`, `fuel-api-credentials.md`. Rotate `NSW_API_KEY`/`NSW_API_SECRET` (set 2026-10-20, never rotated).
- Delete the retired claude.ai routine (disabled since 2026-10-28), if it should be gone for good.
- Confirm 2FA on GitHub and both Expo accounts, the Maps key restriction, PostHog "Discard client IP data", and fork PR approval set to "all external contributors".

## Product decisions (owner)
- Audience: the owner plus a handful of friends. Sydney only, no accounts.
- 2026-10-21 MVP: the "fill now / wait" signal and 1/3/7/14-day outlook, price history, and a nearest-stations list. A Stations **map** was added at the owner's request on 2026-10-26.
- Data as early as possible: 5 pipeline runs a day since 0.6.0.
- Stack: React Native + Expo (TypeScript), EAS Build APKs via an internal distribution link, OTA updates through EAS Update.
- Keep the "new version available" notice (`UpdateNotice` in the root layout) until Bowser is on an app store.
- 2026-11-11: nothing runs locally and nothing depends on an AI assistant or a scheduled task outside GitHub.

## Open work
Newest first. Each item has its CHANGELOG entry of the same name for details.

- **Repo rename, Bowser 0.9.1** (2026-11-11): done. APK built by `app-ci`, the notice went live at the old address, then the repo was renamed and run 43010272458 published the site at the new one; data-health passed after it. **Next:** device check of 0.9.1 (the Expo patch updates are untested on a phone); the first automatic OTA from `app-ci`; drop the old address from `lib/api.ts` once no install needs it.
- **GitHub only** (2026-11-11). **Next:** after the merge, check the first runs of `pipeline-ci` and of `app-ci`'s ship job (neither has run yet), and that the daily run still passes with `out/dashboard.html`.
- **Track record** (2026-11-11, 8b81609): live (run 42965402103; OTA 2abc8e7e at runtime 0.9.0). **Next:** device check of `/track` and Today's tile. **Owner's call:** should a Wait count as right when prices didn't rise (now "Neutral")? The dashboard card always leads with the tested figure; the app switches to live at 40 scored calls that include a Fill and a Wait.
- **Stations map: cheapest in view** (2026-11-11, d2477d5): live by OTA 988104b6. **Next:** device check on Android: the Cheapest tag and the "from" labels draw fully, the tag doesn't cover a neighbouring group's count, the card doesn't re-centre twice, the bar fits at 360 dp. Not built: "Change" on the area bar leaves the map for the list; the map header is about 170 dp tall.
- **Web analytics** (2026-11-10). **Next:** confirm `$pageview` arrives from the live site; the owner opens the dashboard once with `?internal=1` on each of their browsers. Only 1 phone had 0.9.0 (the only version with PostHog) on 2026-11-10; about 3 testers were still on 0.8.0.
- **Security review** (2026-11-03). **Owner decisions:**
  - **Model exposure.** The repo is public, so the model code, training data, backtests and `calls.csv` are readable, and git history can't be withdrawn. Going private needs GitHub Pro for Pages, auth for `daily.yml`'s two tokenless `data` clones, and about 2,200+ Actions minutes a month (more now, with `pipeline-ci` and builds). Alternative: a private source repo that deploys to a public Pages-only repo.
  - **Scraping** can't be prevented on static Pages. Real protection needs a Worker/API with Play Integrity / App Attest, plus a licence change for the forecasts.
  - **Next APK:** the widget image provider (`exported="true"`), `allowBackup`, OTA code signing.
- **Ranges per fuel, diesel crack, VIC archive** (2026-10-29): live. **Next:** once `VIC_API_KEY` is set, check `archive/vic/` appears; in 6–12 months, test whether Melbourne leads Sydney.
- **Verdict rule analysis** (2026-10-29, `docs/RULE_ANALYSIS_2026-10.md`). **Next:** a model experiment for sustained wholesale trends.
- **0.9.0 PostHog analytics** (2026-10-29). **Next:** from a real phone, check one raw event (`$geoip_disable: true`, no `$ip`, a person profile, `app.opened` has a `source`); then build the PostHog dashboard from the 8 metric definitions in `docs/ANALYTICS_PLAN.md`.
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
- **0.7.0 analytics (EAS Insights + Observe)** (2026-10-22). **Next:** check the EAS dashboard (Insights → App usage; Observe → Errors, Navigation, Events). Owner decisions are in the CHANGELOG entry (store privacy forms, an opt-out switch).
- **Data health** (2026-10-22). **Next:** confirm an automatic run's `triggering_actor` is a Bot (`gh api repos/nathann2997/Bowser/actions/runs?per_page=5`) and that the job summary reads well. Dependabot has 3 alerts, in build tooling only, with no fixes released yet.
- **0.7 "prove it"** (2026-10-22, plan `docs/BOWSER_0.7_PLAN.md`). **Device checks:**
  - the keyboard lifts the Filled-up and discount sheets
  - the Share sheet on Android and iOS
  - the share link opens `/s/`, and "Have Bowser? Open it" opens the station
  - the widget shows your price after a discount change

  Fills and calls whose week overlaps 1–12 Oct show "pending" until NSW publishes October's history.
- **iOS build** (2026-10-22, `docs/IOS.md`). **Blocked on the owner:**
  - an Apple Developer Program account
  - a choice of TestFlight (recommended) or ad hoc

  The first iOS build is the one step that can't run on GitHub: EAS has to create the Apple certificates, both bundle IDs and the app group interactively, once (`docs/IOS.md`). After that, add iOS to `app-ci.yml`.
- **0.6.0 feedback round** (2026-10-22). **Device checks:**
  - long one-thumb scrolls don't swipe a row
  - pull-to-refresh, and the AreaPicker keyboard
  - Map opens a labelled pin
  - widget taps, warm and cold; station-row taps open the app; no ⟳ on the widget
  - chip dots in light and dark
  - the Stations "Near you" line at home, after moving, and with location withdrawn
  - on the `data` branch: five commits a day, and `store/backtest_ran` written
- **Earlier device checks still open:**
  - v0.2/0.3.0: keyboard avoidance on Today's suburb search and the fuel sheet; widget placement, the 4 h refresh, a release launch without the R8 crash, chart scrubbing, directions
  - 0.4.0: the widget follows location
  - 0.5.0: welcome, swipe rows, rise alerts
  - new logo: launcher, themed icon, splash, widget

## Key facts
- A change is tested by pushing it: `app-ci` (typecheck, lint, jest, expo-doctor) and `pipeline-ci` (unit tests, then the whole pipeline on a copy of the `data` branch; the built site is a run artifact). Compare that artifact with the live site, ignoring `generated_at`.
- **Shipping the app:** push to `main`. JS-only → OTA to `preview`. Native change → bump `version` in `app/app.json` and edit `app/release_notes.txt`; the workflow builds the APK, updates `sydney/pipeline/app_release.json` and starts `daily.yml`. It refuses to OTA when native files changed without a bump. eas-cli is pinned in `app-ci.yml`.
- Keys exist only as GitHub Actions secrets (`NSW_API_KEY`, `NSW_API_SECRET`, `VIC_API_KEY`, `EXPO_TOKEN`) and in the EAS `preview` environment (`GOOGLE_MAPS_ANDROID_API_KEY`, PostHog key and host). There is no credentials file. Third-party actions are blocked in this repo, so workflows use GitHub's own actions and CLIs only.
- API base: `https://nathann2997.github.io/Bowser/api/v1/`; the file schema is in `sydney/README.md`.
- `stations.json` per-fuel tuple: `[price, days since update, advice code, advice label, reason, 7-day forecast price]` (the last is left off on a day the station files failed). Advice codes: now, by, ok, wait, hi, any, chk.
- The verdict rule is in `template.html` (`verdict()`) and mirrored in `export_api.py`; change both together. The rise date is `market()` in `build.py`, ported to `app/src/lib/outlook.ts`.
- The data (`store/`, `archive/`) lives only on the `data` branch; `main` holds code and docs. Don't merge `data` into `main`, and only Actions writes to `data`.
- Each runtime's update-notice OTA was built from the `ota/<runtime>-update-notice` branches; 0.1.0 APKs have no expo-updates and can't be reached.
- Web dashboard pins are keyed name|postcode|lat|lon (the dashboard data has no station codes), so they don't sync with the app. If `build.py` ever adds codes, switch the key to them.
- The owner has two Expo accounts (nathann97 and nathannguy); the project lives on nathann97.
- `docs/brand/render-brand.mjs` is a design tool (needs Chrome), rerun only when the logo changes; it isn't part of any pipeline.

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
