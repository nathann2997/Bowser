# Bowser app: project rules

Read `README.md` here first, then `docs/HANDOFF.md` at the repo root for the current status.

- **Release notes:** when you bump `version`, put one line (up to 300 characters) of "what's new" in `release_notes.txt`; the workflow copies it into the update notice.
- **Runtime version = `version` in `app.json`** (`runtimeVersion.policy: appVersion`). A JS-only change ships as an OTA update; anything that changes native code (a new native module, a plugin, native config) needs a `version` bump and a new build. Older installs don't get OTAs for a newer runtime.
- **iOS-only native modules are excluded from Android autolinking** (`expo.autolinking.android.exclude` in `package.json`), so the APK is unaffected. Add any new iOS-only dependency there.
- **Widget:** pure logic goes in `src/widget/logic.ts` / `model.ts` (tested). Platform code goes in `*.android.ts` (react-native-android-widget, patched in `patches/`) and `*.ios.ts` (expo-widgets).
- **Keep in step with the pipeline:** `src/lib/types.ts` with `sydney/pipeline/export_api.py`; `src/lib/copy.ts` and `outlook.ts` with `template.html` and `build.py`.
- **Privacy:** the location permission copy promises that Bowser never sends your position anywhere. Don't use `showsUserLocation` on the map, and don't put coordinates in analytics.
- **Technical identifiers stay `fuelforecast`** (package, slug, scheme, API path); the user-facing name is Bowser (`docs/BRAND.md`).
- **Checks and shipping run on GitHub** (`.github/workflows/app-ci.yml`): typecheck, lint, tests, then an OTA update or, after a `version` bump, a new APK and the update notice. A change is done when that workflow is green. Don't publish OTAs or builds by hand.

# Expo notes (from the Expo template)

This is an Expo/React Native mobile application. Prioritize mobile-first patterns, performance, and cross-platform compatibility.

## Expo has changed — do not trust your training data

Expo ships breaking changes every SDK release. APIs you remember are likely renamed, moved, or removed. Before writing any code that touches an Expo, EAS, or React Native API:

1. Read the major version of the `expo` package in `package.json`.
2. Fetch the matching versioned docs: `https://docs.expo.dev/versions/v<major>.0.0/`
3. For anything else, fetch https://docs.expo.dev/llms.txt — an index of all Expo docs with corrections to common LLM misconceptions. Follow its links to the specific page you need; never answer from memory.

## Commands

Use `bunx` instead of `npx` if the project uses bun (`bun.lock` present).

```bash
npx expo install <package>  # ALWAYS use instead of npm/yarn/pnpm/bun add — resolves SDK-compatible versions
npx expo start              # start the dev server
npx expo lint               # lint
npx tsc --noEmit            # typecheck
npx expo-doctor             # diagnose dependency and config issues
npx expo install --fix      # fix incompatible package versions
```

Run lint and typecheck before declaring any task done.

## Navigation & Routing

- Use **Expo Router** for all navigation. Routes live in `src/app/` — every file there is a screen, `_layout.tsx` files define navigators. Keep non-route code (components, hooks, utils) outside `src/app/`.
- Import `Link`, `router`, and `useLocalSearchParams` from `expo-router`.
- Docs: https://docs.expo.dev/router/introduction.md

## Building with EAS

Use EAS to build, sign, and submit the app in the cloud (`eas build`, `eas submit`) and to ship over-the-air updates (`eas update`) — no local Xcode or Android Studio required. Run EAS CLI as `bunx eas-cli <command>` in Bun projects, or `npx eas-cli@latest <command>` otherwise; substitute that for bare `eas` in docs examples.
Docs: https://docs.expo.dev/eas/index.md

## Rules

- If `ios/` and `android/` directories do not exist, they are generated (Continuous Native Generation). Never create or edit them by hand — configure native behavior in `app.json` and config plugins.
- Expo Go only includes its bundled native modules. After adding a library with native code, the app needs a development build: `npx expo run:ios|android` locally, or `eas build --profile development`.
- Prefer recommended Expo modules over third-party libraries, and check your available skills before adding dependencies. Docs: https://docs.expo.dev/versions/latest/index.md
