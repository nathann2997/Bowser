// Premium diesel (PDL) on load (lib/diesel.ts).
import { describe, expect, it } from '@jest/globals';

import { detailWithPremiumDiesel, fuelLabel, isPremium, withPremiumDiesel } from '../diesel';
import type { Station, StationDetail, StationPrice, Stations } from '../types';

const price = (c: number): StationPrice => [c, 0, 'ok', 'No rush', 'No rise expected in the next 2 weeks', c - 1];
const station = (id: string, p: Record<string, StationPrice>): Station =>
  ({ id, n: `S${id}`, b: 'BP', s: 'Ryde', pc: 2112, la: -33.8, lo: 151.1, m: 0, p }) as unknown as Station;
const list = (...stations: Station[]) => ({ schema: 1, asof: '2026-11-25', stations, suburbs: [] }) as unknown as Stations;

describe('premium diesel (PDL) on load', () => {
  it('shows a premium-only station under Diesel, flagged', () => {
    const j = withPremiumDiesel(list(station('1', { U91: price(205.9), PDL: price(263.9) } as Record<string, StationPrice>)));
    const s = j.stations[0];
    expect(s.p.DL?.[0]).toBe(263.9);
    expect(s.pd).toBe(1);
    expect('PDL' in s.p).toBe(false);
    expect(isPremium(s, 'DL')).toBe(true);
    expect(isPremium(s, 'U91')).toBe(false);
    expect(fuelLabel(s, 'DL')).toBe('Premium diesel');
    expect(fuelLabel(s, 'U91')).toBe('Unleaded 91');
  });

  it('keeps regular diesel where a station lists both, the premium price aside', () => {
    const s = withPremiumDiesel(list(station('2', { DL: price(258.9), PDL: price(261.9) } as Record<string, StationPrice>))).stations[0];
    expect(s.p.DL?.[0]).toBe(258.9);
    expect(s.pd).toBeUndefined();
    expect(s.pdl?.[0]).toBe(261.9);
    expect(fuelLabel(s, 'DL')).toBe('Diesel');
  });

  it('leaves other stations alone, and is safe to run twice', () => {
    const j = list(station('3', { U91: price(199.9) }), station('4', { PDL: price(262.9) } as Record<string, StationPrice>));
    withPremiumDiesel(withPremiumDiesel(j));
    expect(j.stations[0].p).toEqual({ U91: price(199.9) });
    expect(j.stations[1].p.DL?.[0]).toBe(262.9);
    expect(j.stations[1].pd).toBe(1);
  });

  it('ignores a malformed PDL entry', () => {
    const s = withPremiumDiesel(list(station('5', { PDL: ['x'] } as unknown as Record<string, StationPrice>))).stations[0];
    expect(s.p).toEqual({});
    expect(s.pd).toBeUndefined();
  });

  const detail = (hist: Record<string, (number | null)[]>, fc: Record<string, unknown>) =>
    ({ schema: 1, asof: '2026-11-25', id: '1', n: 'S1', hist, fc }) as unknown as StationDetail;

  it('station file: premium is its diesel when there is no current regular diesel', () => {
    const fcP = { now: 263.9 };
    const d = detailWithPremiumDiesel(detail({ U91: [1, 2], DL: [258, null], PDL: [262, 263.9] }, { PDL: fcP }));
    expect(d.hist.DL).toEqual([262, 263.9]);
    expect(d.fc.DL).toBe(fcP);
    expect(d.pd).toBe(1);
    expect('PDL' in d.hist || 'PDL' in d.fc).toBe(false);
  });

  it('station file: the pipeline flag wins over a DL history that runs on (forward-filled)', () => {
    const raw = { ...detail({ DL: [258, 258.9], PDL: [262, 263.9] }, { PDL: { now: 263.9 } }), pd: 1, profile: { typ: { DL: -3, U91: 1 } } };
    const d = detailWithPremiumDiesel(raw as unknown as StationDetail);
    expect(d.hist.DL).toEqual([262, 263.9]);
    expect(d.pd).toBe(1);
    expect(d.profile?.typ).toEqual({ U91: 1 });
    expect(detailWithPremiumDiesel(d).hist.DL).toEqual([262, 263.9]);   // twice: unchanged
  });

  it('station file: regular diesel stays when it is current', () => {
    const d = detailWithPremiumDiesel(detail({ DL: [258, 258.9], PDL: [262, 261.9] }, { DL: { now: 258.9 }, PDL: { now: 261.9 } }));
    expect(d.hist.DL).toEqual([258, 258.9]);
    expect((d.fc.DL as { now: number }).now).toBe(258.9);
    expect(d.pd).toBeUndefined();
    expect('PDL' in d.hist || 'PDL' in d.fc).toBe(false);
  });
});
