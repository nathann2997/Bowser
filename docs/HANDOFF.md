# Session handoff — Bowser

Working notes so a fresh session can resume. Update before ending a session (or at ~70% context). The full history of every change, with commits, run ids and OTA update groups, is in `CHANGELOG.md`; this file only keeps what's current and what's still open.

## Where things stand (2026-11-17)
- **Everything runs on GitHub Actions; nothing is run from a laptop.**
  - `daily.yml`: the pipeline, 5 runs a day. State lives only on the `data` branch; the output is on GitHub Pages (dashboard at https://checkbowser.app/, API under `/api/v1/`).
  - `data-health.yml`: watches the API and fixes what a rerun fixes (`docs/DATA_HEALTH.md`).
  - `pipeline-ci.yml`: tests a pipeline change on a copy of the data, with no keys.
  - `app-ci.yml`: checks the app, then on `main` ships it: an OTA update for a JS change, or a new APK plus the update notice after a `version` bump.
- **App:** Bowser **0.9.1** (runtime 0.9.1) on Android. Preview APK: EAS build ad1c55ea, https://expo.dev/accounts/nathann97/projects/fuel-forecast/builds/ad1c55ea-4f63-4259-bc3e-9d52b059bbd7, built by `app-ci` (run 42969569188). `app_release.json` points at it. Not yet seen on a phone.
- **iOS:** compiles (simulator build 46497e9c) but isn't distributed; see the open item below.
- **Names:** the repo is `nathann2997/Bowser` (renamed 2026-11-11), and its Pages site is on the custom domain **https://checkbowser.app** (live 2026-11-17, OTA b475ffcb; bought at Porkbun, DNS there; AAAA, SPF `-all` and DMARC `p=reject` in place; see CHANGELOG). `https://nathann2997.github.io/Bowser/` redirects to it and is the app's fallback; data-health warns (`OLD_ADDRESS`) if that redirect stops. The old `…/FuelForecast/` address is gone (404). Still `fuelforecast`, because installed apps depend on them: the Android package, iOS bundle id, Expo slug and URL scheme.

## Owner to do
- **Google Play, now (2026-11-20):** the closed test (version code 3, 1.0.0) was blocked under the Misleading Claims policy (no link to the government source). 1.0.1 adds the source line and disclaimer in the app and the description in `docs/PLAY_STORE.md`; owner pastes the description, uploads the 1.0.1 bundle (built by a manual `ship=play-build` run, since `PLAY_RELEASE` is off) to closed testing and sends it for review, then sends testers the opt-in link once approved (14 days from 12 opted in). The service account `bowser-play-upload@bowser-512803` was "Invite sent" in Play Console; once it is Active, rerun `ship=play` and set `PLAY_RELEASE`. App signing uses the EAS key (option A).
- **Google Play launch (2026-11-18):** branch `release/google-play` (PR) holds Bowser 1.0.0 for Play. The step-by-step owner list is in the PR and `docs/PLAY_STORE.md` (One-time setup): Play Console account, merge, EAS `production` variables, signing choice, service account, first upload by hand (`ship=play-build`), listing and forms, a 14-day closed test with 12+ testers, production.
- **Search (`docs/SEO.md`):** Search Console verified with the sitemap submitted, and Bing set up (owner, 2026-11-17/18). Next for the owner: links (`docs/SEO.md`, step 4) and a contact email for AdSense.
- **Install 0.9.1 and check it on a phone**; testers on older versions now get the prompt by themselves (see the first open item), so sending the link is optional.
- Add the repo secret `VIC_API_KEY` if the Victorian archive is wanted (optional).
- Delete the old key files on the laptop, which nothing reads any more: `sydney/pipeline/credentials.py`, `sydney/pipeline/pull_nsw.js`, `fuel-api-credentials.md`. Rotate `NSW_API_KEY`/`NSW_API_SECRET` (set 2026-10-20, never rotated).
- Delete the retired claude.ai routine (disabled since 2026-10-28), if it should be gone for good.
- Confirm 2FA on GitHub and both Expo accounts, the Maps key restriction, PostHog "Discard client IP data", and fork PR approval set to "all external contributors".

## Product decisions (owner)
- Audience: the owner plus a handful of friends. No accounts. The forecast is Sydney only; from 2026-11-13 the station list and map cover all of NSW (owner: "ensure we include ALL stations"), with stations outside Sydney shown as prices only.
- 2026-10-21 MVP: the "fill now / wait" signal and 1/3/7/14-day outlook, price history, and a nearest-stations list. A Stations **map** was added at the owner's request on 2026-10-26.
- Data as early as possible: 5 pipeline runs a day since 0.6.0.
- Stack: React Native + Expo (TypeScript), EAS Build APKs via an internal distribution link, OTA updates through EAS Update.
- Keep the "new version available" notice (`UpdateNotice` in the root layout) until Bowser is on an app store.
- 2026-11-11: nothing runs locally and nothing depends on an AI assistant or a scheduled task outside GitHub.

## Open work
- **Make the repo private** (owner asked 2026-11-18 to keep the source private; links removed the same day). Not started. Plan: GitHub Pro (USD 4/mo: Pages from a private repo, 3,000 Actions minutes; current use is about 1,500–2,500 billed min/month, since app-ci waits on EAS builds); three tokenless reads of `data` need the job token (`contents: read`): `daily.yml` (the `ls-remote` check and the save job's `git clone`) and `pipeline-ci.yml`'s clone; CodeQL and secret scanning stop on a private personal repo (Dependabot stays). Earlier history may already be copied elsewhere.
- **Google Play** (2026-11-18, `docs/PLAY_STORE.md`): 1.0.0 drops background location (widget uses the saved area), blocks AD_ID, hides the APK notice in the Play build, adds the `play` CI job (internal track, draft), and the app section of the privacy page. **Next:** after the owner's first `play` run, check the bundle's permissions; once live in production, point `app_release.json` at the Play listing, set `PLAY_PUBLIC`, and carry the new notice to the `ota/` branches (and a new `ota/0.10.0-update-notice`) so old installs move too.
- **Search pages** (live 2026-11-17, PR #11, `daily.yml` run 44011072183; `docs/SEO.md`). `seo_pages.py` writes about 3,500 static pages, the sitemap and robots file inside `export_api.py`. The hub says NSW, with 23 region pages, `llms.txt` and named AI crawlers in `robots.txt` (2026-11-17 review). **Next:** watch Search Console for "Crawled, currently not indexed" on station pages. AdSense is not set up; the list of what it needs is in `docs/SEO.md`.
Newest first. Each item has its CHANGELOG entry of the same name for details.

- **Product roadmap: "best fuel forecasting app", ranked by search** (2026-11-20, owner: tick off the first 10 points in order, each confirmed done before the next; no timeframes). Competitor review in `docs/SEO.md` → "Competitors for forecast searches" (ACCC, Finder, NRMA, FuelRadar, PetrolSpy, PetrolPulse, the closest rival, Fuel Daddy, ConnectingTheDots).
  1. **Ship what's built: done.** PR #30 merged (includes #25, which was closed as superseded): forecast page chart, FAQ and Dataset; `/fuel-price-forecast/accuracy/`, `/best-day-to-buy-petrol/`, `/petrol-prices-christmas/`; cycle stage and jumps; `stats.recent_jumps` in `build.py`. Live, checked after daily run. Play listing short description rewritten for search (`docs/PLAY_STORE.md`); **the Play launch itself is the owner's Console steps.**
  2. **Tested record beside every call: done.** PR #31 merged and live: one line on every call card and Sydney station page, the same figure as the app's Today tile (`tested()`: replay's last year), plus "Why accuracy figures differ between sites" on the accuracy page.
  3. **"Should you fill up today?" title: done.** PR #32 merged and live (dashboard `<title>` and description; keyword map updated).
  4. **October history / full model: already done** when checked: `ctx.live_model` is "full (with cycle memory)", `history_last` 2026-10-31, no gaps since September (`docs/RULE_ANALYSIS_2026-10.md` finding 5 is resolved).
  5. **Next: the 2026 model weakness** (`docs/RULE_ANALYSIS_2026-10.md` finding 3): features for sustained wholesale trends and/or weighting recent years in `model.py`; judge by 2026 walk-forward value per call and Wait-before-a-5c-jump. Also the jump chance on days it rates under 5% (8% actual vs 0.8% predicted) and station forecasts with no mean reversion (`build.py` `advise()`). Experiments must run on GitHub Actions (nothing local). Publish improvements on the accuracy page.
  6. Android background refresh (`docs/NOTIFICATIONS_PLAN.md` P0, native: new APK), then Rise alert v2 (P1) and pinned-station price drop (P2) only.
  7. Weekly outlook pages with an archive: first save a weekly forecast snapshot (with ranges) on the `data` branch; then dated pages under `/fuel-price-forecast/` with last week's call scored.
  8. "Jump watch" social account: a GitHub Action posting when a jump is likely and after each weekly outlook. **Owner decides Bluesky or X** and holds the account credentials (repo secret).
  9. Links: news pitch when a jump is forecast, a free embeddable cycle-stage badge, FuelCheck / data.nsw showcase listing.
  10. Search Console–driven iteration once December data arrives: grow the page groups that earn clicks, fix station pages stuck in "crawled, not indexed", point the app's Share link at station pages.
  Not doing (and why) is in the plan the owner approved: route planner, trip calculator, outage tracker (no reliable signal checked), price-only pages for other states, accounts, loyalty, price lock, notification digests. **Owner decisions open:** name and ABN on About; Bluesky or X.

- **Track record in dollars saved, against one fixed habit** (2026-11-20, PR #28, live: OTA update group 800725ab-e401-4b1c-bdf4-1133227adb45 on runtime 1.0.1; `daily-forecast` run 44737498601 published the new `track.json`). App, web and share now lead with dollars saved against filling up the day you check (U91, the year to 22 Oct: 2.35c a litre, about $1.18 a 50 L tank; always Wait −0.65c). `gain` now equals `save`, so older apps show the honest figure too. Wait cut-offs re-checked: no change. **Next:** the model work on wholesale-driven rises (`docs/RULE_ANALYSIS_2026-10.md` finding 3): in the year to 22 Oct the calls said Wait on 15 of 86 weeks with a 5c+ jump, and the Gerrity score fell from 0.71 (2021–26) to about 0.55 for the last year.
- **Web: desktop map waits for the visitor** (2026-11-21, **live**: PR #34 merged as `de1d535`, `daily.yml` run 44899946518). PageSpeed desktop had 69 (TBT 1,870 ms); Lighthouse on the live site at 4× CPU now 99, TBT 10 ms. **Next:** confirm on pagespeed.web.dev; if TBT is still high there, the 5 s idle fallback may be landing inside its measured window.
- **Web: PageSpeed fixes** (2026-11-20, **live**: PR #29 merged as `0c7dbbd`, deployed by `daily.yml` run 44735468548). Lighthouse on the live site: mobile 98, desktop 100, CLS 0 (PageSpeed had 34 / 43). **Next:** confirm on pagespeed.web.dev; if a later change adds an inline `<script>` (even the text in a comment), `export_api.py` refuses to publish the dashboard.
- **Web: a simpler dashboard** (2026-11-20, **live** with PR #29). A web user said the page had too much content and too many definitions. **Next:** check on a real phone that the three-number row fits at 360 px.
- **All NSW stations on the map** (2026-11-13; **live** since 2026-11-17: PR #9 merged as `dfcafbf`, OTA group `f9830ab5` at runtime 0.9.1). First real run 44155647314 (2026-11-18): 3116 Sydney prices, 4893 elsewhere in NSW, 2388 stations (863 Sydney, 1525 `out: 1`, 1 without a postcode); Wollongong and Gosford search; `meta.warnings` empty; data-health OK. **Next:**
  - Size: `stations.json` is now about 1.09 MB (the app loads it whole) and `station/` about 19 MB across 2388 files. Watch app load time on slow connections; splitting or gzip-only serving is not built.
  - A station file outside Sydney has `start` 2025-10-15 with empty history before 2026-11-18 (the archive had no prices outside Sydney before then); charts fill in from here.
  - Device check: the map away from Sydney, a station page outside Sydney (price, chart from one day of history, the "forecast covers Sydney only" card), a pinned station outside Sydney on the widget.
  - **Owner's call:** rows and station pages outside Sydney still show the gap to the Sydney median, and Today's headline is Sydney's even when your area is elsewhere. A regional median, or hiding the gap there, is not built.
  - `archive/` grows by about 2.5 times per day (all of NSW, not only Sydney).
  - `model/fresh-inputs-shadow` (not merged) also edits `update.py`'s `snapshot_rows`: when it merges, keep both changes (it must call the five-value return and use the Sydney `pr`).

- **Update prompts and automatic shipping** (2026-11-12): live. expo-doctor is advisory in `app-ci`, so pushes to `main` ship OTAs (first one: ef6169d0, runtime 0.9.1, with the station-page price fix). The update notice shows on every open. `app-ota-legacy.yml` published the new API address and the new notice to 0.3.0–0.9.0 from the `ota/<version>-update-notice` branches (run 43113185748). **Next:** on a phone, check that the notice comes back after "Later" and that an older install recovers its prices and shows the 0.9.1 prompt. When a future change must reach old versions (for example another address move), commit it to each `ota/` branch and run `app-ota-legacy`.
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
- **Web map "Cheapest in view"** (2026-11-12): the app's cheapest tag, bar, group "from" prices and card badge, on the web map. **Next:** check on a real phone.
- **Web dashboard design review** (2026-11-12): scrolling over the map (cooperative gestures + a full screen button), the sticky column overlapping the map, the Filters panel running off screen, and phone fit. **Next:** check on a real phone and in Safari: one finger scrolls the page over the map, two move it, full screen works; owner to say if two-finger map movement is acceptable.
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
- API base: `https://checkbowser.app/api/v1/`; the file schema is in `sydney/README.md`.
- `stations.json` per-fuel tuple: `[price, days since update, advice code, advice label, reason, 7-day forecast price]` (the last is left off on a day the station files failed). Advice codes: now, by, ok, wait, hi, any, chk.
- The verdict rule is in `template.html` (`verdict()`) and mirrored in `export_api.py`; change both together. The rise date is `market()` in `build.py`, ported to `app/src/lib/outlook.ts`.
- The data (`store/`, `archive/`) lives only on the `data` branch; `main` holds code and docs. Don't merge `data` into `main`, and only Actions writes to `data`.
- Older versions are kept alive from the `ota/<version>-update-notice` branches (0.3.0–0.9.0), published by `app-ota-legacy.yml`; 0.1.0 APKs have no expo-updates and can't be reached. expo-doctor in `app-ci` is advisory: read it before a `version` bump.
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
