# Product

<!-- impeccable:product-schema 1 -->

Written 2026-11-24 from the repo's recorded owner decisions (`docs/HANDOFF.md` "Product decisions", `docs/DESIGN.md`, `docs/PLAY_STORE.md`, `CHANGELOG.md`) and user feedback relayed by the owner, not from a fresh interview: the owner asked for it to be built and has delegated UX calls. Facts marked *(inferred)* come from the code or docs rather than an owner statement; correct them here.

## Platform

web

## Users

- Drivers in Sydney, and since 2026-11-24 also Canberra and regional NSW, each with one car (the owner, friends, closed-test users and Reddit-referred visitors). They open Bowser a couple of times a week, right before a drive or when the tank is low, often standing at or near the pump.
- The job is always the same: **should I fill up today, and where?** History and the model exist to earn trust; most people check them once, if at all.
- Many arrive on the web first, from a link shared in a social app or a search result, on a phone.

## Product Purpose

Tell a driver whether to fill up now or wait (Sydney's price cycle), and which nearby station is cheapest, in that order: the decision, the place, the saving, the evidence. Success is a driver who acts on the call and saves money, and comes back on the next low tank.

## Positioning

A forecast of the Sydney fuel price cycle (fill now / wait, with a 1–14 day outlook and a public track record), on top of every NSW FuelCheck station's live price, including ACT stations that report to it. Other apps list prices; Bowser says when to buy. The forecast covers Sydney only; elsewhere Bowser shows prices compared with the local median and says so.

## Operating Context

- Two surfaces, one brand and one data API: an Android app (Expo / React Native, on Google Play in closed testing; iOS builds but isn't distributed) that renders Bowser's own design language rather than Material, and the web dashboard at https://checkbowser.app with about 3,500 static search pages. The web is not a wrapper of the app.
- Phone first, outdoors and in cars: glanceable, one hand, sometimes bright sun or at night.
- Entry points: the app's Today and Stations (map first) tabs, the Android widget, shared links (`/s/` share page, social previews), search pages per suburb, station, region and brand.
- Data refreshes five times a day on GitHub Actions; nothing runs on a laptop. App JS changes ship as OTA updates.

## Capabilities and Constraints

- Fill / wait verdict and outlook for U91, E10, P95, P98 and diesel (Sydney); per-station "when to fill" advice in Sydney.
- Prices for every station in the NSW FuelCheck feed (NSW and the ACT); stations outside Sydney are "prices only", compared with their regional median when 8+ stations report (`sydney/pipeline/local_median.py`).
- Pins, discounts, fill logging and a savings record, all stored on the phone. **No accounts.**
- Privacy: anonymous analytics only (PostHog, no IP, no location sent); fills, pins and area never leave the device.
- Source attribution to NSW FuelCheck is required on every surface (Play policy); Bowser is not a government app.
- Undecided *(open)*: iOS distribution; going private on GitHub; AdSense.

## Brand Commitments

- Name **Bowser**; domain **checkbowser.app**; contact checkbowser@gmail.com. The Android package and Expo slug keep the old `fuelforecast` id (installed apps depend on it).
- The mark: a fuel drop with a down arrow cut out (prices about to drop); the wordmark in `app/assets/brand/`. Brand amber `#FFB22E` on ink `#141618` (binding since the 2026-11-24 brand pass; roles in `docs/DESIGN.md`).
- Voice: plain, Australian English, short, concrete ("Wait if you can", "about $3.30 on a 50 L tank"); no jargon, no hype, no analyst terms in the main path.

## Evidence on Hand

- The live track record of past calls (`/track` in the app, the dashboard's "Can I trust it?"), from `store/calls.csv` and the backtest.
- Live price and forecast data via the public API under `/api/v1/`.
- No testimonials, ratings, press or user counts exist: future work must not invent them.

## Product Principles

1. Answer the question first: decision, then place, then saving, then evidence.
2. Never compare a driver with a market they aren't in (Sydney's median for Sydney stations only).
3. Fewer steps over more features: the common path (check, pick a station, log a fill) is one or two taps.
4. Honest about scope: the forecast is Sydney's, and the product says so where it matters.
5. Nothing personal leaves the phone.
