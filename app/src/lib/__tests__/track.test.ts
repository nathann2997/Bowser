import { describe, expect, it } from '@jest/globals';

import { trackMessage } from '../share';
import {
  callsFor, callValue, callWord, countsText, gainText, headline, lift, liftText, LIVE_MIN, liveLeads, liveNote, outcomeText, rangeText,
  runs, runText, tested,
} from '../track';
import type { Call, Counts, LiveTally, ReplayTally, Tally, Track } from '../types';
import published from './track.fixture.json';

const counts = (n: number, right: number, wrong = n - right): Counts => ({ n, right, close: n - right - wrong, wrong });
const tally = (n: number, right: number, from = '2021-01-01', to = '2026-08-24'): Tally => ({ ...counts(n, right), from, to });
const none: LiveTally = { ...tally(0, 0), since: null };
const track = (liveU91: LiveTally, replayU91: ReplayTally = tally(2062, 1723)): Track => ({
  schema: 1, asof: '2026-10-22', window: 7, min_days: 5, calls: [],
  live: { U91: liveU91, E10: none, P98: none, DL: none },
  replay: { U91: replayU91, E10: tally(2062, 1719), P98: tally(2062, 1703), DL: tally(0, 0) },
});
const call = (over: Partial<Call>): Call => ({ date: '2026-10-13', fuel: 'U91', cls: 'up', head: 'Fill up today', now: 242.9, move: 3.4, days: 7, status: 'right', ...over });
/** A live record with `n` scored calls split over the call types */
const live = (n: number, right: number, by: Partial<Record<'up' | 'down' | 'flat', number>>): LiveTally => ({
  ...counts(n, right, 0), from: '2026-10-22', to: '2026-12-20', since: '2026-10-22', pending: 8, gain: 2.7,
  by: { up: counts(by.up ?? 0, 0), down: counts(by.down ?? 0, 0), flat: counts(by.flat ?? 0, 0) },
});
const recent: ReplayTally = {
  ...tally(2098, 1736, '2021-01-01', '2026-10-22'), gain: 5.98, base: { cls: 'down', right: 1322 },
  recent: { ...tally(342, 246, '2025-10-23', '2026-10-22'), gain: 5.21, base: { cls: 'down', right: 164 } },
};

describe('headline', () => {
  it('is the tested figure until live calls lead: the last year of the replay when published, else the whole replay', () => {
    expect(headline(track(live(13, 5, { down: 13 }), recent), 'U91'))
      .toEqual({ pct: 72, n: 342, live: false, text: 'Right 72% of the time', sub: 'tested on the year to 22 Oct' });
    // a track.json from before 2026-11-11 has no `recent`, `by` or `base`
    expect(headline(track({ ...tally(13, 5, '2026-10-22', '2026-11-03'), since: '2026-10-22' }), 'U91'))
      .toEqual({ pct: 84, n: 2062, live: false, text: 'Right 84% of the time', sub: 'tested on 2021–2026 prices' });
  });
  it('13 Wait calls from one falling fortnight do not replace the tested figure (the 38% tile of 2026-11-11)', () => {
    expect(headline(published as Track, 'U91')).toMatchObject({ live: false, pct: 72, sub: 'tested on the year to 22 Oct' });
    for (const f of ['U91', 'E10', 'P95', 'P98', 'DL'] as const) expect(headline(published as Track, f)?.live).toBe(false);
  });
  it('live leads only with LIVE_MIN scored calls that include a Fill and a Wait', () => {
    expect(liveLeads(live(LIVE_MIN - 1, 30, { up: 10, down: 29 }))).toBe(false);
    expect(liveLeads(live(LIVE_MIN, 30, { down: 30, flat: 10 }))).toBe(false);   // never tested on a Fill
    expect(liveLeads({ ...tally(LIVE_MIN, 30), since: '2026-10-22' })).toBe(false);   // an old API: no `by`
    expect(liveLeads(live(LIVE_MIN, 30, { up: 12, down: 28 }))).toBe(true);
    expect(headline(track(live(LIVE_MIN, 30, { up: 12, down: 28 }), recent), 'U91'))
      .toMatchObject({ pct: 75, live: true, sub: '40 live calls since 22 Oct' });
  });
  it('is null with nothing to show (no replay for the fuel, or none at all)', () => {
    expect(headline(track(none), 'DL')).toBeNull();
    expect(headline({ ...track(none), replay: null }, 'U91')).toBeNull();
  });
});

describe('the tested figure', () => {
  it('leads with the last year of the replay and keeps the whole replay beside it', () => {
    const x = tested(track(none, recent), 'U91')!;
    expect(x).toMatchObject({ pct: 72, n: 342, period: 'the year to 22 Oct', gain: 5.21, lift: { pts: 24, rule: 'Wait', basePct: 48 } });
    expect(x.all).toMatchObject({ pct: 83, n: 2098, years: '2021–2026' });
  });
  it('falls back to the whole replay when the recent one is missing or thin', () => {
    expect(tested(track(none), 'U91')).toMatchObject({ pct: 84, period: '2021–2026 prices', lift: null, gain: null });
    const thin = { ...recent, recent: { ...tally(200, 100) } };   // not a year of days
    expect(tested(track(none, thin), 'U91')).toMatchObject({ pct: 83, period: '2021–2026 prices', lift: { pts: 20, rule: 'Wait' } });
  });
  it('says what the calls beat, and when they beat nothing', () => {
    expect(liftText(lift(recent.recent!)!)).toBe('24 points better than always saying “Wait”, which was right 48% of the time.');
    // diesel over 2021–26: "always No rush" was right 85% of the time, the calls 87%
    const dl = lift({ ...tally(2098, 1829), base: { cls: 'flat', right: 1790 } })!;
    expect(dl).toEqual({ pts: 2, rule: 'No rush', basePct: 85 });
    expect(liftText(dl)).toMatch(/^About the same as always saying “No rush” \(85%\)/);
    expect(liftText({ pts: -7, rule: 'Wait', basePct: 60 })).toMatch(/^7 points worse than/);
    // a Wait base near the calls means the calls added little, not that prices were quiet
    expect(liftText({ pts: 2, rule: 'Wait', basePct: 48 })).toBe('About the same as always saying “Wait” (48%).');
    expect(lift(tally(10, 5))).toBeNull();
  });
  it('puts the average value of a call on your tank', () => {
    expect(gainText(5.21, 50)).toBe('Following each call saved about $2.60 a tank on average.');
    expect(gainText(-1.2, 50)).toBe('Following each call cost about $0.60 a tank on average.');
    expect(gainText(0.19, 50)).toBeNull();
    expect(gainText(undefined, 50)).toBeNull();
  });
});

describe('the live record', () => {
  it('reads as counts, with the caveat while every scored call is the same call', () => {
    expect(countsText(counts(13, 5, 0))).toBe('5 right · 8 neutral · 0 wrong');
    expect(liveNote(live(13, 5, { down: 13 }))).toBe('Every call scored so far was “Wait”, so this isn’t a full test yet.');
    expect(liveNote(live(13, 5, { down: 3, flat: 10 }))).toBeNull();
    expect(liveNote(live(0, 0, {}))).toBeNull();
    expect(liveNote({ ...tally(13, 5), since: '2026-10-22' })).toBeNull();
  });
  it('shares the tested figure, what it beats, and the live counts', () => {
    expect(trackMessage(track(live(13, 5, { down: 13 }), recent), 'U91')).toBe(
      'Bowser’s fill-or-wait calls for Sydney Unleaded 91 were right 72% of the time, tested on the year to 22 Oct, 24 points better than always saying “Wait”. Live since 22 Oct: 5 right, 8 neutral, 0 wrong.\nhttps://nathann2997.github.io/FuelForecast/');
    expect(trackMessage(track(none), 'U91')).toBe(
      'Bowser’s fill-or-wait calls for Sydney Unleaded 91 were right 84% of the time, tested on 2021–2026 prices.\nhttps://nathann2997.github.io/FuelForecast/');
    expect(trackMessage(track(none), 'DL')).toBeNull();
  });
});

describe('what happened', () => {
  it('describes complete and pending windows', () => {
    expect(outcomeText(call({}))).toBe('Prices averaged 3.4c higher the week after');
    expect(outcomeText(call({ move: -2.3, status: 'wrong' }))).toBe('Prices averaged 2.3c lower the week after');
    expect(outcomeText(call({ move: 0.2, cls: 'flat', status: 'right' }))).toBe('Prices held steady the week after');
    expect(outcomeText(call({ move: -1.2, days: 4, status: 'pending' }))).toBe('So far 1.2c lower (4 of 7 days)');
    expect(outcomeText(call({ move: null, days: 0, status: 'pending' }))).toBe('Too early to tell');
  });
  it('a pending call never shows the whole window (today is a partial day and is not counted)', () => {
    for (const c of (published as Track).calls) if (c.status === 'pending') expect(c.days).toBeLessThan(7);
  });
  it('values following the call on your tank', () => {
    expect(callValue(call({}), 50)).toEqual({ text: 'Saved about $1.70 a tank', good: true });
    expect(callValue(call({ cls: 'down', move: -4, status: 'right' }), 50)).toEqual({ text: 'Saved about $2.00 a tank', good: true });
    expect(callValue(call({ move: -2.3, status: 'wrong' }), 50)).toEqual({ text: 'Cost about $1.15 a tank', good: false });
    expect(callValue(call({ status: 'pending' }), 50)).toBeNull();
    expect(callValue(call({ move: 0.3, status: 'close' }), 50)).toBeNull();
  });
  it('a wrong No rush has a cost too: what the other call would have saved', () => {
    expect(callValue(call({ cls: 'flat', move: -9.3, status: 'wrong' }), 50)).toEqual({ text: 'Waiting would have saved about $4.65 a tank', good: false });
    expect(callValue(call({ cls: 'flat', move: 6, status: 'wrong' }), 50)).toEqual({ text: 'Filling up would have saved about $3.00 a tank', good: false });
    expect(callValue(call({ cls: 'flat', move: 1, status: 'right' }), 50)).toBeNull();
    expect(callValue(call({ cls: 'flat', move: 4, status: 'close' }), 50)).toBeNull();
  });
  it('names the call and filters by fuel', () => {
    expect([callWord({ cls: 'up' }), callWord({ cls: 'down' }), callWord({ cls: 'flat' })]).toEqual(['Fill', 'Wait', 'No rush']);
    const t = { ...track(none), calls: [call({}), call({ fuel: 'DL' })] };
    expect(callsFor(t, 'DL')).toHaveLength(1);
  });
});

describe('runs of the same call', () => {
  const day = (d: number, over: Partial<Call> = {}) => call({ date: `2026-10-${d}`, cls: 'down', head: 'Wait if you can', ...over });
  it('groups scored calls by consecutive call, newest first, and sets the pending ones aside', () => {
    const r = runs([
      day(30, { status: 'pending', move: null }), day(29, { status: 'pending' }),
      day(28), day(27, { status: 'close' }), day(26, { status: 'wrong' }),
      day(25, { cls: 'flat', head: 'No rush either way' }),
      day(24), day(23),
    ]);
    expect(r.pending.map((c) => c.date)).toEqual(['2026-10-30', '2026-10-29']);
    expect(r.scored.map((x) => [x.cls, x.from, x.to, x.n, x.right, x.close, x.wrong])).toEqual([
      ['down', '2026-10-26', '2026-10-28', 3, 1, 1, 1], ['flat', '2026-10-25', '2026-10-25', 1, 1, 0, 0], ['down', '2026-10-23', '2026-10-24', 2, 2, 0, 0],
    ]);
    expect(runText(r.scored[0])).toBe('3 calls: 1 right, 1 neutral, 1 wrong');
    expect(runText(r.scored[2])).toBe('2 calls: 2 right');
    expect(rangeText(r.scored[0].from, r.scored[0].to)).toBe('26 Oct – 28 Oct');
    expect(rangeText('2026-10-25', '2026-10-25')).toBe('25 Oct');
    expect(runs([])).toEqual({ pending: [], scored: [] });
  });
  it('turns the published U91 record into one Wait run and one pending group', () => {
    const r = runs(callsFor(published as Track, 'U91'));
    expect(r.scored).toHaveLength(1);
    expect(r.scored[0]).toMatchObject({ cls: 'down', n: 13, right: 5, close: 8, wrong: 0, from: '2026-10-22', to: '2026-11-03' });
    expect(r.pending).toHaveLength(8);
  });
});
