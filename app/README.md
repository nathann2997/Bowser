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

## Run it
Node 22+ (installed at `~/.local/node`; `~/.zshrc` adds it to `PATH`).
```sh
cd app
npm install                      # postinstall applies patches/ (react-native-android-widget)
npx expo start                   # live JS reload; the widget and map only work in a preview APK (see Ship)
npx expo export --platform web   # browser preview (no widget or native map)
```

## Checks
```sh
npx tsc --noEmit && npx expo lint && npx jest && npx expo-doctor
```
`.github/workflows/app-ci.yml` runs the same on every push or PR that touches `app/`.

## Ship
- **JS-only change:** `npx eas-cli update --channel preview --environment preview --upload-source-maps`. It reaches installs whose `version` in `app.json` (the runtime version) matches, on their next cold start.
- **Native change** (new native module, plugin or native config in `app.json`): bump `version`, then run `npx eas-cli build -p android --profile preview`. When the build is done, update `sydney/pipeline/app_release.json` so older installs show the "new version" notice.
- Android builds need the EAS env var `GOOGLE_MAPS_ANDROID_API_KEY` for the Stations map.

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
