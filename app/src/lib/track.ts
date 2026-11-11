// The track record (track.json, sydney/pipeline/track_api.py) in words: the headline hit rate and what it's measured
// against, what happened after each call, and what following it was worth on your tank.
import { nice } from './format';
import { dollars } from './outlook';
import type { Call, CallStatus, Counts, Fuel, LiveTally, TestedTally, Track, VerdictCls } from './types';

/** Live calls lead once this many are scored AND they include a Fill and a Wait (liveLeads). Calls are daily and each
 *  is scored on the week after, so neighbours share most of their outcome: 40 is about six independent weeks. Ten
 *  (the first rule) let 13 "Wait" calls from one falling fortnight replace six years of testing. */
export const LIVE_MIN = 40;
/** The last year of the replay leads the tested figure when it really is about a year of days (else the whole replay does) */
export const RECENT_MIN = 300;

const pctOf = (c: Counts) => Math.round((c.right / c.n) * 100);

/** What the call said, in a few words: "Fill" / "Wait" / "No rush" */
export const callWord = (c: { cls: VerdictCls }) => (c.cls === 'up' ? 'Fill' : c.cls === 'down' ? 'Wait' : 'No rush');

export function liveLeads(l: LiveTally | undefined): l is LiveTally {
  return !!l && l.n >= LIVE_MIN && (l.by?.up?.n ?? 0) > 0 && (l.by?.down?.n ?? 0) > 0;
}

export type Lift = { pts: number; rule: string; basePct: number };

/** How far the calls beat the best rule that ignores the forecast, in percentage points */
export function lift(t: TestedTally): Lift | null {
  if (!t.base || !t.n) return null;
  const basePct = Math.round((t.base.right / t.n) * 100);
  return { pts: pctOf(t) - basePct, rule: callWord(t.base), basePct };
}

export function liftText(l: Lift): string {
  const rule = `always saying “${l.rule}”`;
  if (l.pts >= 5) return `${l.pts} points better than ${rule}, which was right ${l.basePct}% of the time.`;
  if (l.pts <= -5) return `${-l.pts} points worse than ${rule}, which was right ${l.basePct}% of the time.`;
  // Only "always No rush" scoring well means quiet prices; a Fill or Wait base near the calls means they added little
  return `About the same as ${rule} (${l.basePct}%)${l.rule === 'No rush' ? ': prices rarely moved enough here to test the calls' : ''}.`;
}

export type Tested = {
  pct: number; n: number;
  period: string;                 // "the year to 22 Oct" / "2021–2026 prices": reads after "tested on"
  by: TestedTally['by'];          // the counts per call type over the same period
  lift: Lift | null;
  gain: number | null;            // c/L a call, on average
  all: { pct: number; n: number; years: string };   // the whole replay
};

/** The replayed backtest for a fuel: its last year when published (the like-for-like for live calls; the average
 *  from 2021 hid a weak 2026), else the whole replay. The year is named by its last day, because the replay ends a
 *  week or more before today (and further back if the monthly backtest is late). */
export function tested(t: Track, fuel: Fuel): Tested | null {
  const r = t.replay?.[fuel];
  if (!r || !r.n) return null;
  const years = r.from && r.to ? `${r.from.slice(0, 4)}–${r.to.slice(0, 4)}` : 'past';
  const lead = r.recent && r.recent.n >= RECENT_MIN ? r.recent : r;
  return {
    pct: pctOf(lead), n: lead.n, period: lead === r || !lead.to ? `${years} prices` : `the year to ${nice(lead.to, false)}`,
    by: lead.by, lift: lift(lead), gain: lead.gain ?? null, all: { pct: pctOf(r), n: r.n, years },
  };
}

export type Headline = { pct: number; n: number; live: boolean; text: string; sub: string };

/** The one number for Today's tile: live calls once they lead (liveLeads), until then the tested figure */
export function headline(t: Track, fuel: Fuel): Headline | null {
  const live = t.live?.[fuel];
  if (liveLeads(live)) {
    const pct = pctOf(live);
    return { pct, n: live.n, live: true, text: `Right ${pct}% of the time`, sub: `${live.n} live calls since ${nice(live.since ?? live.from!, false)}` };
  }
  const x = tested(t, fuel);
  return x && { pct: x.pct, n: x.n, live: false, text: `Right ${x.pct}% of the time`, sub: `tested on ${x.period}` };
}

export const MARK: Record<CallStatus, string> = { right: '✓', close: '≈', wrong: '✗', pending: '…' };
/** "close" in the data is "Neutral" on screen: prices moved too little to say the call was right or wrong */
export const STATUS_WORD: Record<CallStatus, string> = { right: 'Right', close: 'Neutral', wrong: 'Wrong', pending: 'Awaiting result' };

/** "5 right · 8 neutral · 0 wrong" */
export const countsText = (c: Counts, sep = ' · ') => `${c.right} right${sep}${c.close} neutral${sep}${c.wrong} wrong`;

/** What following a call was worth on your tank on average; null when it's too small to matter (under 0.25c a litre) */
export function gainText(gain: number | null | undefined, tankL: number): string | null {
  if (gain == null || Math.abs(gain) < 0.25) return null;
  return `Following each call ${gain > 0 ? 'saved' : 'cost'} about ${dollars(gain, tankL)} a tank on average.`;
}

/** The caveat on a young live record: every scored call so far is the same call, so only half the rule is tested */
export function liveNote(l: LiveTally): string | null {
  if (!l.n || !l.by) return null;
  const kinds = (['up', 'down', 'flat'] as const).filter((k) => (l.by?.[k]?.n ?? 0) > 0);
  return kinds.length === 1 ? `Every call scored so far was “${callWord({ cls: kinds[0] })}”, so this isn’t a full test yet.` : null;
}

/** What happened after a call, against the median on the day */
export function outcomeText(c: Call, window = 7): string {
  if (c.move == null) return 'Too early to tell';
  const m = Math.abs(c.move);
  const dir = m < 0.5 ? null : c.move > 0 ? 'higher' : 'lower';
  if (c.status === 'pending') return `So far ${dir ? `${m.toFixed(1)}c ${dir}` : 'about the same'} (${c.days} of ${window} days)`;
  return dir ? `Prices averaged ${m.toFixed(1)}c ${dir} the week after` : 'Prices held steady the week after';
}

/** Dollars that following the call was worth on a tank (positive = it paid off). A wrong "No rush" has a cost too:
 *  what the other call would have saved. Null with no outcome yet, or a "No rush" that wasn't wrong. */
export function callValue(c: Call, tankL: number): { text: string; good: boolean } | null {
  if (c.move == null || c.status === 'pending') return null;
  if (c.cls === 'flat') {
    if (c.status !== 'wrong') return null;
    return { text: `${c.move < 0 ? 'Waiting' : 'Filling up'} would have saved about ${dollars(c.move, tankL)} a tank`, good: false };
  }
  const gain = c.cls === 'up' ? c.move : -c.move;   // filling before a rise, or waiting through a fall
  if (Math.abs(gain) < 0.5) return null;
  return { text: `${gain > 0 ? 'Saved' : 'Cost'} about ${dollars(gain, tankL)} a tank`, good: gain > 0 };
}

/** Calls for one fuel, newest first */
export const callsFor = (t: Track, fuel: Fuel) => t.calls.filter((c) => c.fuel === fuel);

/** A stretch of days with the same call (newest first), so three weeks of "Wait" is one line, not 21 */
export type Run = Counts & { cls: VerdictCls; calls: Call[]; from: string; to: string };

/** One fuel's calls (newest first) as the ones still awaiting a result and the scored ones in runs of the same call */
export function runs(calls: Call[]): { pending: Call[]; scored: Run[] } {
  const scored: Run[] = [];
  for (const c of calls) {
    if (c.status === 'pending') continue;
    let r = scored[scored.length - 1];
    if (!r || r.cls !== c.cls) scored.push((r = { cls: c.cls, calls: [], from: c.date, to: c.date, n: 0, right: 0, close: 0, wrong: 0 }));
    r.calls.push(c); r.from = c.date; r.n++; r[c.status]++;
  }
  return { pending: calls.filter((c) => c.status === 'pending'), scored };
}

/** "22 Oct – 3 Nov" (or one date) */
export const rangeText = (from: string, to: string) => (from === to ? nice(from, false) : `${nice(from, false)} – ${nice(to, false)}`);

/** "13 calls: 5 right, 8 neutral" (only the counts that aren't zero) */
export function runText(r: Run): string {
  const parts = ([['right', 'right'], ['close', 'neutral'], ['wrong', 'wrong']] as const).filter(([k]) => r[k] > 0).map(([k, w]) => `${r[k]} ${w}`);
  return `${r.n} calls: ${parts.join(', ')}`;
}
