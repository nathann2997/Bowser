// Price drop at a pinned station (lib/drops.ts): the trigger rule, the shared budget, quiet hours, self-cancelling
import { beforeEach, describe, expect, it, jest } from '@jest/globals';

import { cancelPendingDrop, dropOf, dropTime, setDrops, syncDrops } from '../drops';
import type { LiveRow, StationDetail } from '../types';
import type { WStation } from '../../widget/logic';
import fixture from './forecast.fixture.json';

const mockStore = new Map<string, string>();
jest.mock('@/lib/storage', () => ({
  __esModule: true,
  default: {
    getItemSync: (k: string) => mockStore.get(k) ?? null,
    setItemSync: (k: string, v: string) => void mockStore.set(k, v),
    getItem: async (k: string) => mockStore.get(k) ?? null,
    setItem: async (k: string, v: string) => void mockStore.set(k, v),
    removeItem: async (k: string) => void mockStore.delete(k),
  },
}));
const mockNotes = { scheduled: [] as { identifier: string; content: { title: string; data: { stationId: string } }; trigger: { date: Date } }[], cancelled: 0, granted: true };
jest.mock('expo-notifications', () => ({
  AndroidImportance: { DEFAULT: 5 },
  SchedulableTriggerInputTypes: { DATE: 'date' },
  setNotificationHandler: () => {},
  setNotificationChannelAsync: async () => null,
  getPermissionsAsync: async () => ({ granted: mockNotes.granted, canAskAgain: false }),
  requestPermissionsAsync: async () => ({ granted: mockNotes.granted }),
  cancelScheduledNotificationAsync: async () => void mockNotes.cancelled++,
  scheduleNotificationAsync: async (r: never) => (mockNotes.scheduled.push(r), 'id'),
}));


const U91 = (fixture as unknown as { live: LiveRow[] }).live.find((r) => r.fuel === 'U91')!;
const R = { ...U91, now: 220, verdict: { ...U91.verdict, cls: 'flat' as const } };
const st = (id: string, price: number, age = 0, b = 'Metro'): WStation =>
  ({ id, n: `Station ${id}`, b, la: -33.9, lo: 151.1, m: 0, p: { U91: [price, age, 'ok', 'No rush', null] } });
const detail = (hist: (number | null)[], typ?: number): StationDetail =>
  ({ hist: { U91: hist }, profile: typ == null ? null : { typ: { U91: typ }, lag: null, part: null, n: 0 } }) as unknown as StationDetail;
// 29 prior days around 230 (median 230, low 228), then today
const prior = Array.from({ length: 29 }, (_, i) => 228 + (i % 5));

describe('drop trigger', () => {
  it('a strict 30-day low 3c+ under the window median', () => {
    expect(dropOf(st('1', 226), detail([...prior, 226]), 'U91', R, {})).toMatchObject({ why: 'low', size: 4 });
    expect(dropOf(st('1', 228), detail([...prior, 228]), 'U91', R, {})).toBeNull();   // equals the low
    const flat = Array(29).fill(220);
    expect(dropOf(st('1', 219), detail([...flat, 219]), 'U91', R, {})).toBeNull();     // new low, but only 1c under
    expect(dropOf(st('1', 220), detail([...flat, 220]), 'U91', R, {})).toBeNull();     // never moves: not a drop
    expect(dropOf(st('1', 226), detail([...Array(20).fill(null), ...prior.slice(20), 226]), 'U91', R, {})).toBeNull();   // under 15 days known
  });
  it('5c+ under its usual gap to the median, after a fall', () => {
    // usual: 4c over the median (224); now 218 = 6c under its usual; the 30 days were at 219 (not a 3c-low)
    const near = [...Array(28).fill(219), 225];
    expect(dropOf(st('1', 218), detail([...near, 218], 4), 'U91', R, {})).toMatchObject({ why: 'usual', size: 6, belowMedian: 2 });
    expect(dropOf(st('1', 220), detail([...near, 220], 4), 'U91', R, {})).toBeNull();   // 4c under
    expect(dropOf(st('1', 218), detail([...near.slice(0, 28), 218, 218], 4), 'U91', R, {})).toBeNull();   // steady at 218: no fall
  });
  it('a change yesterday is judged against the days before it; a price slip is not a drop', () => {
    expect(dropOf(st('1', 226, 1), detail([...prior, 226, 226]), 'U91', R, {})).toMatchObject({ why: 'low' });
    expect(dropOf(st('1', 129.9), detail([...prior, 129.9]), 'U91', R, {})).toBeNull();
  });
  it('needs a fresh price, a forecast that is not Wait, and gives your price', () => {
    expect(dropOf(st('1', 226, 2), detail([...prior, 226]), 'U91', R, {})).toBeNull();
    expect(dropOf(st('1', 226), detail([...prior, 226]), 'U91', { ...R, verdict: { ...R.verdict, cls: 'down' } }, {})).toBeNull();
    expect(dropOf(st('1', 226), detail([...prior, 226]), 'U91', R, { Metro: 4 })).toMatchObject({ price: 222, yours: true });
    expect(dropOf(st('1', 226), null, 'U91', R, {})).toBeNull();
  });
  it('waits for 7:30 am in quiet hours', () => {
    const t = (h: number, m = 0) => dropTime(new Date(2026, 10, 23, h, m));
    expect([t(6).getDate(), t(6).getHours(), t(6).getMinutes()]).toEqual([23, 7, 30]);
    expect(t(14).getTime() - new Date(2026, 10, 23, 14).getTime()).toBe(60_000);
    expect([t(22).getDate(), t(22).getHours()]).toEqual([24, 7]);
  });
});

describe('syncDrops', () => {
  beforeEach(() => {
    mockStore.clear();
    mockNotes.scheduled = []; mockNotes.cancelled = 0; mockNotes.granted = true;
    mockStore.set('pins.v1', JSON.stringify(['1', '2', '3']));
  });
  const day = (d: number, h = 10) => new Date(2026, 10, d, h);
  const list = [st('1', 226), st('2', 224), st('3', 231)];
  const files: Record<string, StationDetail> = { '1': detail([...prior, 226]), '2': detail([...prior, 224]), '3': detail([...prior, 231]) };
  const get = async (id: string) => files[id];

  it('is off by default, then sends the biggest drop only', async () => {
    await syncDrops([R], list, get, { now: day(23) });
    expect(mockNotes.scheduled).toHaveLength(0);
    expect(await setDrops(true)).toBe(true);
    await syncDrops([R], list, get, { now: day(23) });
    expect(mockNotes.scheduled.map((x) => x.content.data.stationId)).toEqual(['2']);
    expect(mockNotes.scheduled[0].content.title).toBe('Station 2 dropped to 224.0');
  });
  it('one per station a week, two a week in all, counting a rise alert', async () => {
    await setDrops(true);
    await syncDrops([R], list, get, { now: day(23) });                 // station 2, sent at 10:01
    await syncDrops([R], list, get, { now: day(24) });                 // 2 is spent: station 1
    await syncDrops([R], [st('1', 226), st('2', 224), st('3', 225)], async (id) => (id === '3' ? detail([...prior, 225]) : get(id)), { now: day(25) });   // 3 qualifies, budget used
    expect(mockNotes.scheduled.map((x) => x.content.data.stationId)).toEqual(['2', '1']);
    mockStore.delete('drops.log');
    mockStore.set('alerts.state', JSON.stringify({ at: day(22).getTime() }));   // a rise alert sent this week
    await syncDrops([R], list, get, { now: day(26) });
    await syncDrops([R], list, get, { now: day(27) });
    expect(mockNotes.scheduled).toHaveLength(3);
  });
  it('none while a rise alert is pending; a pending drop is cancelled when it no longer holds', async () => {
    await setDrops(true);
    mockStore.set('alerts.state', JSON.stringify({ at: day(24, 7).getTime() }));
    await syncDrops([R], list, get, { now: day(23) });
    expect(mockNotes.scheduled).toHaveLength(0);
    mockStore.delete('alerts.state');
    await syncDrops([R], list, get, { now: day(23, 22) });             // 10 pm: for 7:30 tomorrow
    expect(mockNotes.scheduled[0].trigger.date.getHours()).toBe(7);
    const before = mockNotes.cancelled;
    await syncDrops([R], [st('1', 231), st('2', 231), st('3', 231)], get, { now: day(23, 23) });   // prices bounced back
    expect(mockNotes.cancelled).toBeGreaterThan(before);
    expect(JSON.parse(mockStore.get('drops.log')!)).toEqual([]);
  });
  it('a slow or failed station file is skipped, not waited on', async () => {
    await setDrops(true);
    const slow = (id: string) => (id === '2' ? new Promise<StationDetail>(() => {}) : id === '1' ? Promise.reject(new Error('404')) : Promise.resolve(detail([...prior, 225])));
    await syncDrops([R], [st('1', 226), st('2', 224), st('3', 225)], slow, { now: day(23), timeoutMs: 20 });
    expect(mockNotes.scheduled.map((x) => x.content.data.stationId)).toEqual(['3']);
  });
  it('keeps a pending drop when its file fails to load; switching off or a new rise alert clears it', async () => {
    await setDrops(true);
    await syncDrops([R], list, get, { now: day(23, 22) });            // station 2 for 7:30 tomorrow
    const n = mockNotes.cancelled;
    await syncDrops([R], list, async (id) => (id === '2' ? Promise.reject(new Error('offline')) : get(id)), { now: day(23, 23) });
    expect(mockNotes.cancelled).toBe(n);
    expect(JSON.parse(mockStore.get('drops.log')!)).toHaveLength(1);
    await cancelPendingDrop(day(23, 23).getTime());                    // what syncAlerts does when it schedules a rise
    expect(JSON.parse(mockStore.get('drops.log')!)).toEqual([]);
    await syncDrops([R], list, get, { now: day(23, 23) });
    // setDrops reads the real clock: pin it to the test's day, or the 7:30 drop counts as already sent once that date passes
    const clock = jest.spyOn(Date, 'now').mockReturnValue(day(23, 23).getTime());
    try {
      await setDrops(false);
    } finally {
      clock.mockRestore();
    }
    expect(JSON.parse(mockStore.get('drops.log')!)).toEqual([]);
  });
});
