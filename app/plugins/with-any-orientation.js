// Android follows the phone's rotation; iPhone stays portrait. Google Play (1.0.1, 2026-11-23): "Remove resizability
// and orientation restrictions": Android 16 ignores an orientation lock on large screens (tablets, foldables) anyway.
// Expo has one `orientation` for both platforms (no android.orientation), so app.json keeps "portrait" (iOS
// UISupportedInterfaceOrientations stays portrait) and this sets MainActivity's android:screenOrientation to
// "unspecified", the value Expo itself writes for "default". User plugins' mods run after Expo's built-in Orientation
// mod (built-ins are added last, and a mod added later runs first, then hands on), so this value wins.
// Nothing in the manifest sets resizeableActivity or an aspect ratio. Needs a native build (it changes the manifest).
const { AndroidConfig, withAndroidManifest } = require('expo/config-plugins');

/** Sets android:screenOrientation="unspecified" on the main activity; the manifest object is changed in place */
function unlockOrientation(manifest) {
  const main = AndroidConfig.Manifest.getMainActivityOrThrow(manifest);
  main.$['android:screenOrientation'] = 'unspecified';
  return manifest;
}

const withAnyOrientation = (config) =>
  withAndroidManifest(config, (c) => {
    unlockOrientation(c.modResults);
    return c;
  });

module.exports = withAnyOrientation;
module.exports.unlockOrientation = unlockOrientation;
