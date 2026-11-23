// plugins/with-any-orientation.js: on Android the main activity follows the phone's rotation (Google Play asks apps not
// to lock orientation on large screens); app.json keeps "portrait" for iPhone.
import { describe, expect, it } from '@jest/globals';

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { unlockOrientation } = require('../../../plugins/with-any-orientation');

type Activity = { $: Record<string, string>; 'intent-filter'?: unknown[] };
const manifest = (main: Record<string, string>) => ({
  manifest: {
    application: [{
      $: { 'android:name': '.MainApplication' },
      activity: [
        { $: { 'android:name': '.MainActivity', ...main } },
        { $: { 'android:name': 'com.reactnativeandroidwidget.RNWidgetConfigurationActivity' } },
      ] as Activity[],
    }],
  },
});

describe('unlockOrientation', () => {
  it('replaces the portrait lock Expo writes from app.json', () => {
    const m = unlockOrientation(manifest({ 'android:screenOrientation': 'portrait', 'android:exported': 'true' }));
    const [main, other] = m.manifest.application[0].activity;
    expect(main.$['android:screenOrientation']).toBe('unspecified');
    expect(main.$['android:exported']).toBe('true');
    expect(other.$['android:screenOrientation']).toBeUndefined();
  });

  it('sets it when there was none, and is idempotent', () => {
    const m = unlockOrientation(unlockOrientation(manifest({})));
    expect(m.manifest.application[0].activity[0].$['android:screenOrientation']).toBe('unspecified');
  });
});
