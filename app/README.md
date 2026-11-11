# Bowser

Expo / React Native app for the Sydney pump price forecast. It runs on Android, and an iOS build is in progress (`docs/IOS.md`). It reads the static JSON API that `.github/workflows/daily.yml` publishes (`https://nathann2997.github.io/FuelForecast/api/v1/`; the schema is in `sydney/README.md`), and uses the same numbers and wording as the web dashboard.

| Screen | What |
|---|---|
| Today (tab) | "Fill up now or wait" per fuel, the trend, your pinned stations, the proof strip (you saved / calls right) |
| Stations (tab) | Cheapest stations near you or a suburb, as a list or a map; filters, pins, swipe for directions |
| More (tab) | Settings, discounts, alerts, widget location, data sources, about |
| `trends`, `track`, `savings` | Price history and cycle summary, the track record, your fill log |
| `station/[id]` | One station: price history, its own forecast, share |
| `welcome` | First run |

There's also a home-screen widget (`src/widget/`) and an opt-in price-rise alert (`src/lib/alerts.ts`). Data is cached on the device for offline use.

## Checks and shipping: all on GitHub
Nothing is run from a laptop. `.github/workflows/app-ci.yml` does it on every push or PR that touches `app/`:
- **Checks:** `tsc --noEmit`, `expo lint`, `jest` and `expo-doctor`.
- **JS-only change on `main`:** published as an OTA update to the `preview` channel. It reaches installs whose `version` in `app.json` (the runtime version) matches, on their next open.
- **Native change** (a new native module, a plugin, native config in `app.json`): bump `version` in `app.json` and put one line of "what's new" in `release_notes.txt`. The workflow then builds the Android preview APK, points `sydney/pipeline/app_release.json` at it and starts the daily pipeline, so older installs show the "new version" notice.
- If native files change without a `version` bump, the workflow stops and ships nothing, because an OTA could crash the installed APKs. Run it by hand with `ship=ota` if the change really is JS-only.

It needs the repo secret `EXPO_TOKEN`. The app's own keys (`GOOGLE_MAPS_ANDROID_API_KEY`, PostHog) live in the EAS `preview` environment. iOS isn't automated yet: the first build has to create Apple credentials interactively (`docs/IOS.md`).

## Layout
- `src/app/`: screens (expo-router). `_layout.tsx` sets up the query cache, analytics, the OTA check and the update notice. `(tabs)/_layout.tsx` sets up the tabs.
- `src/components/`: the UI kit (`ui.tsx`), charts, map and sheets.
- `src/lib/`: API types and fetching, settings and storage, and pure logic (`copy.ts`, `outlook.ts`, `filters.ts`, `fills.ts`…). Tests are in `src/lib/__tests__/`.
- `src/widget/`: the home-screen widget. `logic.ts` and `model.ts` are pure and shared by both platforms. The `*.android.ts` files use react-native-android-widget, and the `*.ios.ts` files use expo-widgets (WidgetKit).
- `src/hooks/` and `src/constants/theme.ts`: the area and theme hooks, and the colour tokens.
- `*.web.ts(x)`: stand-ins for the browser preview only.

## Keep in step with the pipeline
- `src/lib/types.ts` ↔ `sydney/pipeline/export_api.py` (the API shape).
- `src/lib/copy.ts` and `src/lib/outlook.ts` ↔ `sydney/pipeline/template.html` and `build.py` (wording, verdict, rise date).
- The fuel list ↔ `sydney/pipeline/fuels.py`.
