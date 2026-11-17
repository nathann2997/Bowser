# Security

How Bowser is kept safe, what was reviewed, and what only the owner can do. Last full review: 2026-11-17 (CHANGELOG).

## What there is to protect
- **Who can change what users see.** The data and the site are public on purpose (NSW FuelCheck is open data), so the risk is someone changing them: the repo (`main`, `data`), the Pages site on `checkbowser.app`, and the app's OTA updates (anyone holding `EXPO_TOKEN` can ship JavaScript to every installed phone; EAS update code signing needs Expo's paid Production plan).
- **Users' location and habits.** Location is used on the device only. Nothing sends coordinates, suburbs or station codes anywhere (analytics strips them; see `docs/ANALYTICS_PLAN.md`).
- **The NSW API keys** (GitHub secrets only; never committed, checked against all of git history on 2026-11-17).

## In place
- **Repo:** one admin; ruleset "Protect main and data" blocks deletion and force pushes on `main`, `data` and `ota/*`. Only GitHub-owned actions may run, each pinned to a commit SHA; default token read-only, write permissions per job. Secret scanning with push protection, Dependabot alerts and security updates, CodeQL code scanning.
- **Secrets:** `EXPO_TOKEN` is only used by jobs in the `release` environment (deployments from `main` only). The pipeline (`daily.yml`) only runs, and only writes to `data`, from `main`. Tools that run next to secrets are locked: Python by hashes (`sydney/requirements.txt`), eas-cli and expo-doctor by `tools/ci/package-lock.json`; nothing is fetched fresh by `npx`.
- **Data in:** downloads only over HTTPS from an allowlist of domains (`fetch.py`), size-capped; no pickle/eval/yaml; pipeline code always comes from `main`, never from the data branch.
- **Site:** every page has a hash-pinned Content-Security-Policy (no inline script that isn't ours), third-party scripts by exact URL with SRI, everything from the NSW API escaped before it reaches HTML, and a script refuses to run inside another site's frame (GitHub Pages can't send X-Frame-Options). TLS 1.3; `.app` is HSTS-preloaded.
- **App:** API files are checked for shape before they're shown or saved; the update notice only opens this project's EAS build pages; deep links only take digit station codes; no cloud backup of on-device data (`allowBackup: false`, from 0.10.0); the widget's images need a per-install token (patch in `app/patches/`).
- **Monitoring:** `data-health` checks the live API every 30 minutes, including that the old `github.io` address still reaches it.

## Owner-only (not visible to the repo)
- [ ] 2FA on GitHub, Expo, Porkbun (security key or passkey where offered) and PostHog.
- [ ] `EXPO_TOKEN`: a robot-user token with the smallest role that can publish, stored as an environment secret of `release` (Settings → Environments → release), not a repo secret.
- [ ] Porkbun: DNSSEC on; CAA record `0 issue "letsencrypt.org"`; auto-renew, WHOIS privacy and transfer lock on.
- [ ] PostHog: project setting "Discard client IP data" on (the share page says the IP is never kept).
- [ ] Google Cloud: the Maps Android key restricted to package `com.nathann2997.fuelforecast` + the EAS signing SHA-1, API "Maps SDK for Android" only, a daily quota and a budget alert.

## Accepted, on purpose
- **Precise location permission** stays: "nearest" and distances need better than Android's ~2 km coarse fix. It is never sent off the phone.
- **Background location** (widget, only when the user turns it on in More) stays; a Play listing will need its declaration.
- **`style-src 'unsafe-inline'`** on the dashboard (generated inline styles); scripts are hash-pinned, so injected HTML can't run code.
- **OTA updates aren't signed** (paid plan); covered by the `release` environment, the locked eas-cli and the token's scope.
- **Dependabot alerts for glob, minimatch and zod**: build and lint tooling only, never in the app; dismissed with that reason until Expo moves them.
