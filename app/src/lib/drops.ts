// Price drop at a pinned station (docs/NOTIFICATIONS_PLAN.md P2): one local notification when a station you pinned got
// cheap for your fuel. Runs only from the background refresh task (iOS and Android), never while the app is open: the
// app already shows the prices. Off until the user turns it on (More).
//
// The rule (fixed 2026-11-23, before it ran on any data): a pinned station's price for your fuel, changed within a day
// and lower than before that change, is
//   (a) a new 30-day low: under every end-of-day price of the 29 days before the change (15+ of them known), and 3c+
//       under their median (a station whose price never moves is always "at its low"), or
//   (b) 5c+ under its usual gap to the Sydney median (profile.typ, the same gap as the station advice), and
// the Sydney verdict isn't "Wait if you can" (no point nudging during a fall). A gap over 40c is a price slip (as the
// pipeline's station forecasts treat it), not a drop. Of several, only the biggest drop is sent.
// Budget, shared with the rise alert: at most 2 notifications in 7 days (sent or pending), none while a rise alert is
// pending, one per station per 7 days. Quiet hours: 9 pm to 7:30 am waits for 7:30. A pending drop is re-checked on
// every run and cancelled if it no longer holds.
import * as Notifications from 'expo-notifications';
import { AndroidImportance } from 'expo-notifications';
import { Platform } from 'react-native';

import { reportError, track } from './analytics';
import { offFor, yourPrice } from './discounts';
import { isPremium } from './diesel';
import { fuelName, stationName } from './format';
import { readPinsFromStorage } from './pins';
import { loadSettings, setSettings } from './settings';
import Storage from './storage';
import type { Fuel, LiveRow, StationDetail } from './types';
import type { WStation } from '@/widget/logic';

const CHANNEL = 'drops';
const NOTE_ID = 'bowser-drop';
const LOG_KEY = 'drops.log';
const RISE_KEY = 'alerts.state';   // lib/alerts.ts: { at } of the rise alert last scheduled
const DAY = 24 * 60 * 60 * 1000;
const WEEK = 7 * DAY;
export const WINDOW = 29, MIN_DAYS = 15, LOW_GAP = 3, USUAL_GAP = 5, SLIP = 40, BUDGET = 2;
const QUIET_FROM = 21;   // 9 pm
const MORNING = { h: 7, m: 30 };   // as lib/alerts.ts ALERT_AT (not imported: alerts imports this module)

export type Drop = { id: string; name: string; price: number; yours: boolean; why: 'low' | 'usual'; size: number; belowMedian: number; premium?: boolean };   // premium: premium diesel (lib/diesel.ts)

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b), m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

/** Whether this pinned station qualifies, and by how much (c/L). `price`/`age` from stations.json; `d` its station file. */
export function dropOf(s: WStation, d: StationDetail | null, fuel: Fuel, r: LiveRow | undefined, discounts: Record<string, number>): Drop | null {
  const p = s.p[fuel];
  if (!p || p[0] == null || p[1] == null || p[1] > 1 || !r || r.verdict.cls === 'down') return null;
  const price = p[0], age = p[1];
  const h = d?.hist?.[fuel];
  if (!h || h.length < WINDOW + 1 + age) return null;   // the 29 days before the change, then the change
  // hist ends on the stations' day (its last value is this price), so the change was `age` days back: before it, the
  // previous price, and the 29 days before the change
  const end = h.length - 1 - age;
  const num = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
  const before = h[end - 1];
  if (!num(before) || before <= price) return null;   // not a fall
  let why: Drop['why'] | null = null, size = 0;
  const prior = h.slice(end - WINDOW, end).filter(num);
  if (prior.length >= MIN_DAYS && price < Math.min(...prior) && median(prior) - price >= LOW_GAP) { why = 'low'; size = median(prior) - price; }
  const typ = d?.profile?.typ?.[fuel];
  if (typeof typ === 'number') {
    const under = r.now + typ - price;   // how far under its usual gap to the median
    if (under >= USUAL_GAP && under > size) { why = 'usual'; size = under; }
  }
  if (!why || size > SLIP) return null;
  const off = s.b ? offFor(discounts, s.b) : 0;
  // outside Sydney the Sydney median says nothing about the station
  return { id: s.id, name: stationName(s.n), price: off ? yourPrice(price, off) : price, yours: off > 0, why, size, belowMedian: d?.out ? 0 : r.now - price,
    ...(isPremium(s, fuel) || isPremium(d, fuel) ? { premium: true } : {}) };
}

export function dropText(x: Drop, fuel: Fuel): { title: string; body: string } {
  const why = x.why === 'low' ? 'its lowest in 30 days' : `about ${Math.round(x.size)}c under its usual price`;
  const med = x.belowMedian >= 1 ? `, ${Math.round(x.belowMedian)}c under the Sydney median` : '';
  return {
    title: `${x.name} dropped to ${x.price.toFixed(1)}${x.yours ? ' (your price)' : ''}`,
    body: `${x.premium ? 'Premium diesel' : fuelName(fuel)} at your pinned station: ${why}${med}.`,
  };
}

/** When a drop found now shows: a minute from now, or 7:30 am when it's quiet hours */
export function dropTime(now: Date): Date {
  const morning = new Date(now.getFullYear(), now.getMonth(), now.getDate(), MORNING.h, MORNING.m);
  if (now < morning) return morning;
  if (now.getHours() < QUIET_FROM) return new Date(now.getTime() + 60_000);
  return new Date(morning.getTime() + DAY);
}

type Log = { id: string; at: number }[];
function readLog(): Log {
  try {
    const v = JSON.parse(Storage.getItemSync(LOG_KEY) ?? '[]');
    return Array.isArray(v) ? v.filter((x) => x && typeof x.id === 'string' && typeof x.at === 'number') : [];
  } catch {
    return [];
  }
}
function riseAt(): number | null {
  try {
    const v = JSON.parse(Storage.getItemSync(RISE_KEY) ?? 'null');
    return v && typeof v.at === 'number' ? v.at : null;
  } catch {
    return null;
  }
}

async function cancel() {
  try {
    await Notifications.cancelScheduledNotificationAsync(NOTE_ID);
  } catch {
    // nothing scheduled
  }
}

async function fetchDetail(id: string, get: (id: string) => Promise<StationDetail>, ms: number): Promise<StationDetail | null> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([get(id).catch(() => null), new Promise<null>((res) => { timer = setTimeout(() => res(null), ms); })]);
  } finally {
    clearTimeout(timer);
  }
}

/** Cancel a pending drop and forget it (a rise alert was just scheduled: it outranks a drop). Never throws. */
export async function cancelPendingDrop(now = Date.now()) {
  try {
    const log = readLog();
    await cancel();
    if (log.some((x) => x.at > now)) await Storage.setItem(LOG_KEY, JSON.stringify(log.filter((x) => x.at <= now)));
  } catch {
    // nothing to cancel
  }
}

/**
 * Bring the drop notification in line with the latest data. `stations`: the compact station list (the widget's
 * snapshot); `getDetail` fetches a station file (lib/api getStationDetail). Never throws.
 */
export async function syncDrops(
  live: LiveRow[] | undefined, stations: WStation[] | undefined,
  getDetail: (id: string) => Promise<StationDetail>, opts: { now?: Date; timeoutMs?: number } = {},
): Promise<void> {
  if (Platform.OS === 'web' || !live || !stations) return;
  const now = opts.now ?? new Date(), t = now.getTime();
  try {
    const s = loadSettings();
    const log = readLog().filter((x) => t - x.at < WEEK || x.at > t);
    const pending = log.find((x) => x.at > t);
    const forget = async () => {
      await cancel();
      if (pending) await Storage.setItem(LOG_KEY, JSON.stringify(log.filter((x) => x !== pending)));
    };
    if (!s.drops) return void (await forget());
    if (!(await Notifications.getPermissionsAsync()).granted) {
      setSettings({ drops: false });
      return void (await forget());
    }
    const rise = riseAt();
    const sent = log.filter((x) => x.at <= t).length + (rise != null && rise <= t && t - rise < WEEK ? 1 : 0);
    const r = live.find((x) => x.fuel === s.fuel);
    // nothing can be sent: don't fetch anything
    if ((rise != null && rise > t) || sent >= BUDGET || !r || r.verdict.cls === 'down') return void (await forget());
    const pins = readPinsFromStorage();
    const byId = new Map(stations.map((x) => [x.id, x]));
    // stations sent within the week can't send again; a pending one is re-checked; a stale price can't qualify
    const recent = new Set(log.filter((x) => x.at <= t).map((x) => x.id));
    const cands = pins.map((id) => byId.get(id)).filter((x): x is WStation => {
      const p = x?.p[s.fuel];
      return !!x && !recent.has(x.id) && !!p && p[1] != null && p[1] <= 1;
    });
    const details = await Promise.all(cands.map((x) => fetchDetail(x.id, getDetail, opts.timeoutMs ?? 8000)));
    // the pending station's file didn't load (offline, a failed export): no data, so leave it as it is
    const pi = pending ? cands.findIndex((x) => x.id === pending.id) : -1;
    if (pending && pi >= 0 && !details[pi]) return;
    const best = cands
      .map((x, i) => dropOf(x, details[i], s.fuel, r, s.discounts))
      .filter((x): x is Drop => !!x)
      .sort((a, b) => b.size - a.size)[0];
    if (!best) return void (await forget());
    const at = pending ? new Date(pending.at) : dropTime(now);   // a replacement keeps the pending time (quiet hours hold)
    const { title, body } = dropText(best, s.fuel);
    await cancel();
    await Notifications.scheduleNotificationAsync({
      identifier: NOTE_ID,
      content: { title, body, data: { type: 'drop', stationId: best.id } },
      trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: at, channelId: CHANNEL },
    });
    await Storage.setItem(LOG_KEY, JSON.stringify([...log.filter((x) => x !== pending), { id: best.id, at: at.getTime() }]));
  } catch (e) {
    console.warn('Bowser price drop not scheduled', e);
    reportError(e);
  }
}

/** Turn drop notifications on (asks for permission) or off. Returns whether they are on afterwards. */
export async function setDrops(on: boolean): Promise<boolean> {
  if (!on) {
    setSettings({ drops: false });
    await cancelPendingDrop();
    track('drops.toggled', { on: false, granted: false });
    return false;
  }
  try {
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync(CHANNEL, { name: 'Price drops at pinned stations', importance: AndroidImportance.DEFAULT });
    }
    const cur = await Notifications.getPermissionsAsync();
    const ok = cur.granted || (cur.canAskAgain && (await Notifications.requestPermissionsAsync()).granted);
    setSettings({ drops: ok });
    track('drops.toggled', { on: true, granted: ok });
    return ok;
  } catch (e) {
    setSettings({ drops: false });
    reportError(e);
    return false;
  }
}
