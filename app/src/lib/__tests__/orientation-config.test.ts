/**
 * @jest-environment node
 */
// The whole config, as prebuild resolves it (introspection: nothing is written): Android's main activity follows the
// rotation although app.json says "portrait", because plugins/with-any-orientation.js runs after Expo's own
// orientation step; iPhone stays portrait.
import { beforeAll, describe, expect, it, jest } from '@jest/globals';

/* eslint-disable @typescript-eslint/no-require-imports */
const path = require('path');
// Through the packages that declare them (expo -> @expo/cli -> @expo/prebuild-config), not npm's hoisting
const resolve = (require as unknown as { resolve: (id: string, o?: { paths: string[] }) => string }).resolve;   // no @types/node
const cli = resolve('@expo/cli/package.json', { paths: [resolve('expo/package.json')] });
const { getPrebuildConfigAsync } = require(resolve('@expo/prebuild-config', { paths: [cli] }));
const { compileModsAsync } = require('expo/config-plugins');
/* eslint-enable @typescript-eslint/no-require-imports */

declare const __dirname: string;   // jest's, in a node environment (no @types/node here)
const root: string = path.resolve(__dirname, '../../..');

describe('orientation in the resolved native config', () => {
  beforeAll(() => { jest.spyOn(console, 'warn').mockImplementation(() => {}); });   // plugins' notes about iOS targets

  it('Android: unspecified on MainActivity; iOS: portrait only', async () => {
    const { exp } = await getPrebuildConfigAsync(root, { platforms: ['android', 'ios'] });
    expect(exp.orientation).toBe('portrait');
    const config = await compileModsAsync(exp, { projectRoot: root, platforms: ['android', 'ios'], introspect: true, assertMissingModProviders: false });
    const manifest = config._internal.modResults.android.manifest;
    const main = manifest.manifest.application[0].activity.find((a: { $: Record<string, string> }) => a.$['android:name'] === '.MainActivity');
    expect(main.$['android:screenOrientation']).toBe('unspecified');
    expect(main.$['android:resizeableActivity']).toBeUndefined();
    expect(config._internal.modResults.ios.infoPlist.UISupportedInterfaceOrientations).toEqual([
      'UIInterfaceOrientationPortrait', 'UIInterfaceOrientationPortraitUpsideDown',
    ]);
  }, 60000);
});
