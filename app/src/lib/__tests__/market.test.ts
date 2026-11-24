import { describe, expect, it } from '@jest/globals';

import { gapWords, marketFor } from '../market';

const regions = { 'Canberra and Queanbeyan': { name: 'Canberra', f: { P95: [240.9, 42] as [number, number] } } };

describe('marketFor', () => {
  it('compares a Sydney station with the Sydney median', () => {
    expect(marketFor({}, 'U91', 202.9, regions)).toEqual({ med: 202.9, name: 'Sydney' });
    expect(marketFor({}, 'U91', null, regions)).toBeNull();
  });
  it('compares a Canberra station with the Canberra median, never Sydney', () => {
    expect(marketFor({ out: 1, rg: 'Canberra and Queanbeyan' }, 'P95', 221.4, regions)).toEqual({ med: 240.9, name: 'Canberra', n: 42 });
  });
  it('gives no comparison outside Sydney without a region figure for the fuel', () => {
    expect(marketFor({ out: 1, rg: 'Canberra and Queanbeyan' }, 'U91', 202.9, regions)).toBeNull();
    expect(marketFor({ out: 1 }, 'P95', 202.9, regions)).toBeNull();
    expect(marketFor({ out: 1, rg: 'Canberra and Queanbeyan' }, 'P95', 202.9, undefined)).toBeNull();   // an older stations.json
  });
});

describe('gapWords', () => {
  const m = { med: 240.9, name: 'Canberra' };
  it('names the market', () => {
    expect(gapWords(-5, m)).toEqual({ lead: '5.0c cheaper', rest: ' than the Canberra median (240.9c)' });
    expect(gapWords(0.01, m)).toEqual({ lead: 'At the Canberra median', rest: ' (240.9c)' });
  });
});
