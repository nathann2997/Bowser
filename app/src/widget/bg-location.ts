// Whether the Android widget may read the phone's position while Bowser is closed ("Allow all the time").
//
// Off from 1.0.0 (the Google Play release, 2026-11-18): Play only allows ACCESS_BACKGROUND_LOCATION when it is core to
// the app, needs a declaration and a video, and a "stations near you" widget is routinely refused. The widget now works
// as on iOS: it lists stations near the saved area, and a GPS area keeps the fix the app took when it was set. The
// permission is also removed from the manifest (app.json: isAndroidBackgroundLocationEnabled false, and
// ACCESS_BACKGROUND_LOCATION in blockedPermissions). Turning it back on needs both of those, a version bump and the
// Play declaration.
export const WIDGET_BG_LOCATION = false;
