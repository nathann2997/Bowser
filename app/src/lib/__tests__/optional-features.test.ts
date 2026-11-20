// plugins/with-optional-features.js: the portrait screen and Wi-Fi are optional in the Android manifest, so Google Play
// doesn't restrict which devices can install Bowser.
import { describe, expect, it } from '@jest/globals';

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { markOptional, OPTIONAL } = require('../../../plugins/with-optional-features');

type Feature = { $: Record<string, string> };

describe('markOptional', () => {
  it('declares portrait and Wi-Fi as not required on a manifest with no features', () => {
    const m = markOptional({}) as { 'uses-feature': Feature[] };
    expect(m['uses-feature']).toEqual(
      ['android.hardware.screen.portrait', 'android.hardware.wifi'].map((n) => ({ $: { 'android:name': n, 'android:required': 'false' } })),
    );
    expect(OPTIONAL).toHaveLength(2);
  });

  it('turns off "required" on an existing declaration instead of adding a second one, and keeps others', () => {
    const m = {
      'uses-feature': [
        { $: { 'android:name': 'android.hardware.wifi', 'android:required': 'true' } },
        { $: { 'android:name': 'android.hardware.camera', 'android:required': 'false' } },
      ],
    };
    markOptional(m);
    const wifi = m['uses-feature'].filter((f) => f.$['android:name'] === 'android.hardware.wifi');
    expect(wifi).toEqual([{ $: { 'android:name': 'android.hardware.wifi', 'android:required': 'false' } }]);
    expect(m['uses-feature']).toHaveLength(3);
  });

  it('is idempotent', () => {
    const m = markOptional(markOptional({}));
    expect(m['uses-feature']).toHaveLength(2);
  });
});
