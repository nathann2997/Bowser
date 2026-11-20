# Bowser on Google Play

How Bowser gets onto Google Play and stays there: what the code does, what the owner sets up once, and the answers for every Play Console form. Status lives in `docs/HANDOFF.md`.

## What the code does (1.0.0, 1.0.1)

| Piece | Where | What |
|---|---|---|
| Play build | `app/eas.json` `build.production` | Android App Bundle (.aab), EAS channel `production`, EAS environment `production`, versionCode counted by EAS (`autoIncrement`, `appVersionSource: remote`) |
| Submit | `app/eas.json` `submit.production` | Play's **internal** track as a **draft**: nothing reaches anyone until it is rolled out in Play Console |
| CI | `.github/workflows/app-ci.yml`, job `play` | Builds the bundle and submits it. By hand: Actions → app-ci → Run workflow → `play` (build + submit) or `play-build` (build only). Automatic after a `version` bump once the repo variable `PLAY_RELEASE` is `true`; JS-only pushes then also go out as an OTA to `production` |
| No APK prompts in the Play build | `app/src/components/update-notice.tsx` (`fromPlay`) | The channel `production` never shows the "new version" notice. Play updates the app, and Play doesn't allow sending people to install an APK |
| Moving testers to Play | `update-notice.tsx` `PLAY_URL`, `export_api.py` `REL_URL` | `app_release.json` may point at the Play listing instead of an APK, with its own wording ("Bowser is now on Google Play…") |
| No background location | `app/src/widget/bg-location.ts`, `app.json` | `ACCESS_BACKGROUND_LOCATION` is blocked and the widget uses the saved area, as on iOS. No Play declaration or video is needed |
| No advertising ID | `app.json` `blockedPermissions` | `com.google.android.gms.permission.AD_ID` is removed, so the Advertising ID answer is "No" |
| Privacy policy | `sydney/pipeline/seo_pages.py` → https://checkbowser.app/privacy/ | Covers the website and the app (`#app`), and is linked from More → About in the app |
| Government source and disclaimer | `app/src/lib/sources.ts`, `components/source-line.tsx` | "Prices: NSW Government FuelCheck … Bowser is not a government app" on the welcome screen, Today, the Stations list and station pages, and in More → About with links (from 1.0.1) |
| Optional hardware | `app/plugins/with-optional-features.js` | Portrait screen and Wi-Fi declared as not required, so Play doesn't restrict devices (from 1.0.1) |
| Store graphics | `docs/play/icon-512.png`, `docs/play/feature-graphic.jpg` | 512×512 icon and 1024×500 feature graphic, from the brand files (no tagline, `docs/BRAND.md`) |

## One-time setup (owner)

1. **EAS `production` environment.** expo.dev → fuel-forecast → Environment variables: for each of `GOOGLE_MAPS_ANDROID_API_KEY`, `EXPO_PUBLIC_POSTHOG_KEY` and `EXPO_PUBLIC_POSTHOG_HOST` (and any other variable that `preview` has), tick **production** as well. If the Maps key is missing, the build fails in `app.config.js`. If PostHog is missing, the Play build has no analytics and nothing warns you.
2. **Google service account** (lets CI upload to Play; Expo's guide: https://expo.fyi/creating-google-service-account):
   - In Google Cloud (the project that holds the Maps key is fine), enable the **Google Play Android Developer API**, create a service account and download a **JSON key**.
   - In Play Console → Users and permissions, invite the service account's email with release permissions for Bowser (or admin for the app).
   - On expo.dev → fuel-forecast → Credentials → Android → `com.nathann2997.fuelforecast`, upload the JSON key under **Google Service Account Key for Play Store submissions**. Then delete the downloaded file. Nothing goes into GitHub.
3. **First upload by hand.** Google's API may refuse the first upload for an app that has never had one. Run app-ci with `ship=play-build`, download the .aab from the build link in the run's summary, and upload it in Play Console → Test and release → Internal testing → Create new release (choose the signing option below at this step). After that, `ship=play` uploads by itself.

## Repo variables (Settings → Secrets and variables → Actions → Variables)

| Variable | Set to `true` when | Effect |
|---|---|---|
| `PLAY_RELEASE` | the first `play` run has submitted successfully | every `version` bump also builds and submits to Play; every JS push also goes out as an OTA to Play installs |
| `PLAY_PUBLIC` | Bowser is live in production on Play and `app_release.json` points at the Play listing | stops `app-ci`'s notice job from pointing the update notice back at a new APK |

## Signing (decide before the first upload)

Testers' APKs are signed with the EAS keystore. Android only installs an update signed with the same key.

- **A. Recommended: let Play use the EAS key.** In Play Console, when asked how to sign, choose to upload your own app signing key ("Export and upload a key from Java keystore"). Download the keystore from expo.dev (Project → Credentials → Android → `com.nathann2997.fuelforecast` → Download), run the PEPK command that Play Console shows, upload the zip, then delete the downloaded keystore. Testers can then upgrade in place from Play and keep their pins and fills. The Maps key restriction already has this SHA-1.
- **B. Let Google generate a key.** Simpler. But testers have to uninstall the APK before installing from Play, and they lose pins, fills and settings, because `allowBackup` is off. Add Play's **app signing** SHA-1 (Play Console → Test and release → App integrity) to the Maps key restriction in Google Cloud, or the Play build's map is blank.

Either way, EAS keeps signing uploads with its key, which is then the **upload key**.

## Store listing

- **App name:** `Bowser`. The brand rule is no descriptor after the name (`docs/BRAND.md`). The short description carries the search words.
- **Short description (80 max):** `When to fill up in Sydney, and where fuel is cheapest near you.`
- **Full description (4000 max):**

```
Bowser is not a government app. It is independent and is not affiliated with, endorsed by or representing the NSW Government or any government agency.

Bowser tells you whether to fill up today or wait, and where fuel is cheapest near you.

Sydney petrol prices move in cycles: they climb sharply, then drift down for weeks. Bowser reads every price NSW service stations report to the NSW Government's FuelCheck service, up to five times a day, and turns it into one plain call: fill now, or wait.

• Today's call for your fuel: Unleaded 91, E10, Premium 95 and 98, or Diesel
• A 1, 3, 7 and 14-day outlook for Sydney prices, with a likely range
• The cheapest stations near you on a list or a map, across all of NSW
• Every station's price history and 7-day forecast
• Pin the stations you use, and log your fills to see what you saved
• An alert before prices are expected to jump
• Home-screen widgets with today's call and your stations
• A public track record: every call is scored a week later

No account, no ads. Your location stays on your phone.

The forecast covers Sydney; prices cover all of NSW. Forecasts are estimates for planning, not financial advice. Prices are the stations' own reports and can be a few hours old, so check the board before you fill.

SOURCES
• Fuel prices: NSW Government FuelCheck – https://www.fuelcheck.nsw.gov.au
• FuelCheck data and licence: https://data.nsw.gov.au/data/dataset/fuel-check
• AUD/USD exchange rate: Reserve Bank of Australia – https://www.rba.gov.au/statistics/frequency/exchange-rates.html
• Brent crude oil price: U.S. Energy Information Administration – https://www.eia.gov/dnav/pet/hist/RBRTED.htm
• Wholesale (terminal gate) prices: Australian Institute of Petroleum – https://www.aip.com.au/pricing/terminal-gate-prices

Contains NSW Government FuelCheck data © State of New South Wales (NSW Fair Trading), licensed under CC BY-SA 3.0 AU.
```

**Government information (Misleading Claims policy).** Play counts FuelCheck prices (and the RBA rate) as government information. The description must open with the "not a government app" line and list a link to each official source, and the app must show both where they're easy to see (`app/src/lib/sources.ts`: Today, Stations, More → About). The closed test of 1.0.0 was blocked on 2026-11-20 for missing this; 1.0.1 fixes it. Keep the description, the app and the site's `SOURCES` (`seo_pages.py`) in step.

- **Category:** Maps & Navigation. **Tags:** fuel, petrol prices (pick from Play's list).
- **Contact:** website `https://checkbowser.app`, the email address you choose for the listing (Play shows it publicly), privacy policy `https://checkbowser.app/privacy/`.
- **Graphics:** the icon and feature graphic in `docs/play/`, plus **4 to 8 phone screenshots** (PNG or JPEG, portrait, at least 1080 px wide) taken on a phone running the Play build. Suggested: Today, Stations map, a station page, the track record, the widget on a home screen.
- **Countries:** Australia only. **Price:** free.

## App content (Play Console → Policy → App content)

| Form | Answer |
|---|---|
| Privacy policy | `https://checkbowser.app/privacy/` |
| App access | All functionality is available without special access (no login) |
| Ads | No, the app does not contain ads |
| Content rating (IARC) | Category: Utility / Other. No violence, sexual content, language, drugs, gambling or user-generated content; users can't interact or exchange content; it doesn't share the user's location with other users; no digital purchases. Expect Everyone / PEGI 3 / Australia G |
| Target audience | 18 and over (drivers). Not designed for children; no appeal-to-children elements |
| News app | No |
| Government app | No (it uses public NSW data but isn't made by or for a government) |
| Financial features | None |
| Health | None |
| Advertising ID | No (the permission is blocked in the manifest) |
| Data safety | Below |

### Data safety

Includes what the Google Maps SDK collects (Google's disclosure: https://developers.google.com/maps/documentation/android-sdk/play-data-disclosure). Keep this in step with the privacy page.

- Does the app collect or share any of the required user data types? **Yes**
- Is all user data encrypted in transit? **Yes** (HTTPS only)
- Do you provide a way for users to request that their data is deleted? **Yes**: the privacy page's contact. Uninstalling deletes everything on the phone.
- **Shared** with third parties: **none**. PostHog, Expo and Google Maps act as service providers, which Play doesn't count as sharing.

| Data type | Collected | Optional? | Purposes | Why |
|---|---|---|---|---|
| App activity → App interactions | Yes | No (Maps SDK map interactions; Bowser's own events can be turned off) | Analytics, App functionality | PostHog / EAS Observe events; Maps SDK pan and zoom |
| App info and performance → Crash logs | Yes | No | Analytics, App functionality | EAS Observe; Maps SDK stack traces |
| App info and performance → Diagnostics | Yes | No | Analytics, App functionality | load times; Maps SDK request metadata |
| Device or other IDs | Yes | No | Analytics | random install ID (PostHog); Maps SDK pseudonymous ID |
| Location (approximate or precise) | **No** | | | used only on the phone, never sent (Play doesn't count on-device processing as collection) |
| Everything else (personal info, financial, messages, photos, contacts, health, web browsing) | No | | | |

If someone asks about the **IP address**: PostHog discards it, and the Maps SDK's use of it is covered by Diagnostics.

## Permissions the bundle should have

After the first upload, check Play Console → Test and release → App bundle explorer → the version → Permissions. Expected, roughly: internet, network state, fine and coarse location, notifications, vibrate, boot completed and wake lock (widget and alerts), plus whatever the libraries add for the widget. **Not expected:** `ACCESS_BACKGROUND_LOCATION`, `AD_ID`, `SYSTEM_ALERT_WINDOW`, storage. If `SCHEDULE_EXACT_ALARM` or `USE_EXACT_ALARM` appears, tell the next session: Play asks for a declaration for those, and they can be blocked, because Bowser's alerts don't need exact timing.

## New personal developer accounts: the closed test

A personal Play developer account created after November 2023 can't publish to production until it has run a **closed test** (not internal) with **at least 12 testers opted in for 14 days in a row**. Then apply for production access in the Dashboard. Promote the internal release to closed testing in Play Console, add the testers' Google account emails as a list, and send them the opt-in link. An organisation account (needs a D-U-N-S number) skips this.

## After Bowser is live in production

1. Set `sydney/pipeline/app_release.json` `android` to `{"version": "<Play version>", "url": "https://play.google.com/store/apps/details?id=com.nathann2997.fuelforecast", "notes": "…"}` and push. Sideloaded 1.0.0+ installs **older than that version** then show "Bowser is now on Google Play". The notice only fires for a newer version, so testers on the 1.0.0 APK move once Play has 1.0.1 or later. Ship the next version bump before switching the link.
2. Set the repo variable `PLAY_PUBLIC` to `true`.
3. **Older sideloaded versions (0.3.0–0.10.0)** have an older copy of the notice that only accepts EAS links, so they show nothing for a Play link. To move them too, put the new `update-notice.tsx` on each `ota/<version>-update-notice` branch (and create `ota/0.10.0-update-notice`), then run `app-ota-legacy`. That's a job for a session ("point the old versions at Play").
4. Optional: change `submit.production.android.releaseStatus` to `completed` so internal-track uploads roll out by themselves (production stays a manual promotion in Play Console).
