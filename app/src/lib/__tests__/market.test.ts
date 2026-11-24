import { describe, expect, it } from '@jest/globals';

import { gapWords, marketFor, marketNote } from '../market';

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

describe('marketNote', () => {
  const two = { ...regions, Goulburn: { name: 'Goulburn', f: { P95: [238.0, 9] as [number, number] } } };
  const cbr = { out: 1 as const, rg: 'Canberra and Queanbeyan' };
  it('says nothing when every gap is to Sydney', () => {
    expect(marketNote([{}, {}], 'P95', 220.1, regions)).toBeNull();
    expect(marketNote([{}, { out: 1 }], 'P95', 220.1, regions)).toBeNull();   // the outside row has no gap at all
    expect(marketNote([], 'P95', 220.1, regions)).toBeNull();
  });
  it('names the one local market when every gap is to it', () => {
    expect(marketNote([cbr, cbr], 'P95', 220.1, regions)).toEqual({ one: { med: 240.9, name: 'Canberra', n: 42 } });
  });
  it('looks past the first row: a Sydney row first, or a mix of markets, is "mixed"', () => {
    expect(marketNote([{}, cbr], 'P95', 220.1, regions)).toEqual({ mixed: ['Sydney', 'Canberra'] });
    expect(marketNote([cbr, {}], 'P95', 220.1, regions)).toEqual({ mixed: ['Canberra', 'Sydney'] });
    expect(marketNote([cbr, { out: 1, rg: 'Goulburn' }], 'P95', 220.1, two)).toEqual({ mixed: ['Canberra', 'Goulburn'] });
  });
});
