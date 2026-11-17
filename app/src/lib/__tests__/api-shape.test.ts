// API files are checked for the fields the screens rely on before they're shown or saved (shapeOk in lib/api.ts)
import { describe, expect, it } from '@jest/globals';

import { shapeOk } from '../api';

describe('shapeOk', () => {
  it('accepts the published shapes', () => {
    expect(shapeOk('meta', { asof: '2026-11-17' })).toBe(true);
    expect(shapeOk('forecast', { asof: 'x', live: [{ fuel: 'U91', now: 230 }] })).toBe(true);
    expect(shapeOk('stations', { asof: 'x', stations: [{ id: '1', n: 'A' }], suburbs: [] })).toBe(true);
    expect(shapeOk('history', { start: '2021-01-01', hist: {} })).toBe(true);
    expect(shapeOk('track', { asof: 'x' })).toBe(true);
    expect(shapeOk('station/231', { id: '231', n: 'A' })).toBe(true);
  });

  it('rejects damaged or tampered files', () => {
    expect(shapeOk('meta', {})).toBe(false);
    expect(shapeOk('forecast', { asof: 'x', live: 'nope' })).toBe(false);
    expect(shapeOk('forecast', { asof: 'x', live: [null] })).toBe(false);
    expect(shapeOk('stations', { asof: 'x', stations: [{ id: 1, n: 'A' }], suburbs: [] })).toBe(false);
    expect(shapeOk('stations', { asof: 'x', stations: [] })).toBe(false);
    expect(shapeOk('history', { start: 'x', hist: null })).toBe(false);
    expect(shapeOk('station/231', { id: '231' })).toBe(false);
  });
});
