// Marks hardware features that Android would otherwise treat as required as optional, so Google Play doesn't hide
// Bowser from devices without them (Play's pre-review check, 2026-11-19, from 1.0.1):
//   android.hardware.screen.portrait  implied by "orientation": "portrait" in app.json
//   android.hardware.wifi             implied by the ACCESS_WIFI_STATE permission a library adds
// Every phone has both; this only stops Play listing them as requirements. An explicit <uses-feature
// android:required="false"> replaces the implied one. Needs a native build (it changes the manifest).
const { withAndroidManifest } = require('expo/config-plugins');

const OPTIONAL = ['android.hardware.screen.portrait', 'android.hardware.wifi'];

/** Adds (or turns off "required" on) a <uses-feature> for each name; the manifest object is changed in place */
function markOptional(manifest, names = OPTIONAL) {
  const list = (manifest['uses-feature'] = manifest['uses-feature'] || []);
  for (const name of names) {
    const found = list.find((f) => f.$ && f.$['android:name'] === name);
    if (found) found.$['android:required'] = 'false';
    else list.push({ $: { 'android:name': name, 'android:required': 'false' } });
  }
  return manifest;
}

const withOptionalFeatures = (config) =>
  withAndroidManifest(config, (c) => {
    markOptional(c.modResults.manifest);
    return c;
  });

module.exports = withOptionalFeatures;
module.exports.markOptional = markOptional;
module.exports.OPTIONAL = OPTIONAL;
