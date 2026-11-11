// The track record: how the daily call has done. Two figures, never blended: the rule tested on past prices (the last
// year of the replay, against the best rule that ignores the forecast) and the live calls kept since launch. Live leads once
// there are enough of them (lib/track.ts liveLeads). Then accuracy by call, and the recent calls grouped into runs of
// the same call. Opened from Today's proof strip and More. Data: track.json (sydney/pipeline/track_api.py).
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Button, Card, Disclosure, Loading, Screen, Section, T } from '@/components/ui';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useReady } from '@/lib/analytics';
import { isNotFound, useTrack } from '@/lib/api';
import { fuelName, nice } from '@/lib/format';
import { useSettings } from '@/lib/settings';
import { canShare, shareText, trackMessage } from '@/lib/share';
import {
  callsFor, callValue, callWord, countsText, gainText, liftText, LIVE_MIN, liveLeads, liveNote, MARK, outcomeText, rangeText, runs,
  runText, STATUS_WORD, tested, type Run, type Tested,
} from '@/lib/track';
import type { Call, CallStatus, Counts, LiveTally } from '@/lib/types';

export default function TrackRecord() {
  const c = useTheme();
  const s = useSettings();
  const q = useTrack();
  useReady(!q.isPending);
  const t = q.data;
  const live = t?.live[s.fuel];
  const x = t ? tested(t, s.fuel) : null;
  const lead = liveLeads(live);
  const { pending, scored } = runs(t ? callsFor(t, s.fuel) : []);
  const brag = t ? trackMessage(t, s.fuel) : null;
  const liveCard = live?.since ? <LiveCard key="live" l={live} tankL={s.tankL} lead={lead} /> : null;
  const testedCard = x ? <TestedCard key="tested" x={x} tankL={s.tankL} lead={!lead} /> : null;

  return (
    <Screen
      title="Track record"
      subtitle={`Sydney ${fuelName(s.fuel)}`}
      onBack={() => (router.canGoBack() ? router.back() : router.replace('/'))}
      onRefresh={() => q.refetch()}
      refreshing={q.isRefetching}>
      {!t ? (
        isNotFound(q.error) ? (
          <Card><T>The track record arrives with the next price update.</T></Card>
        ) : (
          <Loading error={q.error} onRetry={() => q.refetch()} />
        )
      ) : (
        <>
          {lead ? [liveCard, testedCard] : [testedCard, liveCard]}

          {x?.by ? <ByCall by={x.by} period={x.period} /> : null}

          <Section title="Recent calls">
            {scored.length || pending.length ? (
              <Card style={{ padding: 0, overflow: 'hidden' }}>
                {scored.map((r, i) => (
                  <RunRows key={`${r.to}|${r.cls}`} r={r} window={t.window} tankL={s.tankL} last={i === scored.length - 1 && !pending.length} />
                ))}
                {pending.length ? <PendingRows calls={pending} window={t.window} tankL={s.tankL} /> : null}
              </Card>
            ) : (
              <Card><T>Each morning’s call shows here, and is scored once the week after has played out.</T></Card>
            )}
          </Section>

          {brag && canShare() ? <Button label="Share the track record" kind="secondary" onPress={() => shareText(brag, 'track')} /> : null}

          <Disclosure title="How calls are scored">
            <T kind="small" color={c.fg2}>
              Each day’s first call is kept as it was made, with the Sydney median it was made at. Once the week after is over, it’s checked against the average Sydney median over those {t.window} days. Today is never counted while its prices are still coming in.
            </T>
            <T kind="small" color={c.fg2}>
              Fill: right if prices averaged 1c or more higher, wrong if 1c or more lower. Wait: the reverse. No rush: right if they moved less than 3c, wrong if 5c or more. Anything in between is neutral: prices moved too little to call it either way.
            </T>
            <T kind="small" color={c.fg2}>
              The tested figure applies the same rule to the forecast model’s walk-forward test from 2021: each day predicted only from data before it. It’s compared with the best rule that ignores the forecast (always Fill, always Wait or always No rush), because some of those are right most days on their own.
            </T>
            <T kind="small" color={c.fg2}>
              The dollar figures are what following the call was worth on your tank against filling at the week’s average: filling before a rise, or waiting through a fall. In the averages No rush counts as nothing gained or lost; a wrong No rush shows what the other call would have saved.
            </T>
          </Disclosure>
        </>
      )}
    </Screen>
  );
}

/** Neutral is one grey in the bar, the legend and the row marks (its word in a row is text colour, to stay readable) */
function statusColor(c: ReturnType<typeof useTheme>, s: CallStatus) {
  return s === 'right' ? c.cheap : s === 'wrong' ? c.dear : s === 'close' ? c.calmStrong : c.muted;
}

function Big({ pct, lead }: { pct: number; lead: boolean }) {
  const c = useTheme();
  // Not coloured: the number can be good or bad, and what it beats is on the next line
  return (
    <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: Spacing.two }}>
      <T kind="hero" style={lead ? { fontSize: 44, lineHeight: 50, letterSpacing: -1.2 } : undefined}>{pct}%</T>
      <T color={c.fg} style={{ fontWeight: '700' }}>of calls right</T>
    </View>
  );
}

/** The rule replayed on past prices, against the best rule that ignores the forecast */
function TestedCard({ x, tankL, lead }: { x: Tested; tankL: number; lead: boolean }) {
  const c = useTheme();
  const gain = gainText(x.gain, tankL);
  return (
    <View style={[styles.hero, { backgroundColor: c.surface, borderColor: c.line }]}>
      <T kind="eyebrow">Tested on {x.period}</T>
      <Big pct={x.pct} lead={lead} />
      {x.lift ? <T kind="small" color={c.fg2}>{liftText(x.lift)}</T> : null}
      {gain ? <T kind="small" color={c.fg2}>{gain}</T> : null}
      <T kind="small">
        What Bowser would have said on each of {x.n.toLocaleString('en-AU')} days, using only data from before that day.
        {x.n !== x.all.n ? ` Over ${x.all.years} it was right ${x.all.pct}% of the time.` : ''}
      </T>
    </View>
  );
}

/** The calls Bowser has actually made, as counts (a % of a handful of calls says little), with what they were worth */
function LiveCard({ l, tankL, lead }: { l: LiveTally; tankL: number; lead: boolean }) {
  const c = useTheme();
  const gain = gainText(l.gain, tankL);
  const note = liveNote(l);
  return (
    <View style={[styles.hero, { backgroundColor: c.surface, borderColor: c.line }]}>
      <T kind="eyebrow">Live calls since {nice(l.since!, false)}</T>
      {!l.n ? (
        <T color={c.fg} style={{ fontWeight: '700' }}>No call scored yet</T>
      ) : lead ? (
        <Big pct={Math.round((l.right / l.n) * 100)} lead />
      ) : (
        <T kind="bignum">{l.n} scored · {l.wrong} wrong</T>
      )}
      {l.n ? <Bar t={l} /> : null}
      {gain ? <T kind="small" color={c.fg2}>{gain}</T> : null}
      {note ? <T kind="small" color={c.fg2}>{note}</T> : null}
      {l.pending || !lead ? (
        <T kind="small">
          {l.pending ? `${l.pending} more ${l.pending === 1 ? 'is' : 'are'} awaiting a result: each call is scored once the week after it is over. ` : ''}
          {lead ? '' : `Live results become the headline after ${LIVE_MIN} scored calls that include a Fill and a Wait.`}
        </T>
      ) : null}
    </View>
  );
}

/** Right / neutral / wrong as one stacked bar with counts */
function Bar({ t }: { t: Counts }) {
  const c = useTheme();
  const parts = (['right', 'close', 'wrong'] as const).filter((k) => t[k] > 0);
  return (
    <View style={{ gap: Spacing.two, marginTop: Spacing.one }}>
      <View style={[styles.bar, { backgroundColor: c.sunk }]} accessible accessibilityLabel={countsText(t, ', ')}>
        {parts.map((k) => (
          <View key={k} style={{ flex: t[k], backgroundColor: statusColor(c, k) }} />
        ))}
      </View>
      <View style={styles.legend} importantForAccessibility="no-hide-descendants">
        {(['right', 'close', 'wrong'] as const).map((k) => (
          <T key={k} kind="small" color={c.fg2}>
            <T kind="small" color={statusColor(c, k)} style={{ fontWeight: '800' }}>{MARK[k]} </T>
            {t[k].toLocaleString('en-AU')} {STATUS_WORD[k].toLowerCase()}
          </T>
        ))}
      </View>
    </View>
  );
}

/** How each kind of call has done in testing, over the same period as the headline */
function ByCall({ by, period }: { by: NonNullable<Tested['by']>; period: string }) {
  const c = useTheme();
  const rows = (['up', 'down', 'flat'] as const).flatMap((k) => (by[k]?.n ? [[k, by[k]!] as const] : []));
  if (!rows.length) return null;
  return (
    <Section title="By call">
      <Card style={{ padding: 0, overflow: 'hidden' }}>
        {rows.map(([k, v], i) => {
          const pct = Math.round((v.right / v.n) * 100);
          return (
            <View
              key={k}
              accessible
              accessibilityLabel={`${callWord({ cls: k })}: right ${pct}% of the time, ${v.wrong} wrong of ${v.n} calls`}
              style={[styles.row, i < rows.length - 1 && { borderBottomColor: c.line, borderBottomWidth: StyleSheet.hairlineWidth }]}>
              <View style={{ flex: 1, gap: 2 }}>
                <T color={c.fg} style={{ fontWeight: '700' }}>{callWord({ cls: k })}</T>
                <T kind="small">{v.n.toLocaleString('en-AU')} calls, {v.wrong.toLocaleString('en-AU')} wrong</T>
              </View>
              <T kind="num">{pct}% right</T>
            </View>
          );
        })}
      </Card>
      <T kind="small">Tested on {period}.</T>
    </Section>
  );
}

/** A run of the same call as one line that opens to its days; a single day is just its row */
function RunRows({ r, window, tankL, last }: { r: Run; window: number; tankL: number; last: boolean }) {
  const c = useTheme();
  const [open, setOpen] = useState(false);
  const line = { borderBottomColor: c.line, borderBottomWidth: StyleSheet.hairlineWidth };
  if (r.n === 1) return <CallRow c={r.calls[0]} window={window} tankL={tankL} last={last} />;
  // The mark is the run's most common result (the counts beside it give the rest); a tie reads as neutral
  const top = Math.max(r.right, r.close, r.wrong);
  const worst: CallStatus = [r.right, r.close, r.wrong].filter((v) => v === top).length > 1 ? 'close' : r.right === top ? 'right' : r.wrong === top ? 'wrong' : 'close';
  return (
    <>
      <Pressable
        onPress={() => setOpen(!open)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={`${callWord(r)}, ${rangeText(r.from, r.to)}. ${runText(r)}`}
        style={({ pressed }) => [styles.row, (!last || open) && line, { opacity: pressed ? 0.7 : 1 }]}>
        <Mark status={worst} />
        <View style={{ flex: 1, gap: 2 }}>
          <T color={c.fg} style={{ fontWeight: '700' }} numberOfLines={1}>{callWord(r)} · {rangeText(r.from, r.to)}</T>
          <T kind="small" color={c.fg2}>{runText(r)}</T>
        </View>
        <T color={c.muted}>{open ? '−' : '+'}</T>
      </Pressable>
      {open ? r.calls.map((x, i) => (
        <CallRow key={x.date} c={x} window={window} tankL={tankL} last={last && i === r.calls.length - 1} inset />
      )) : null}
    </>
  );
}

/** The calls whose week isn't over yet, under the scored ones: they say nothing about the record so far */
function PendingRows({ calls, window, tankL }: { calls: Call[]; window: number; tankL: number }) {
  const c = useTheme();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Pressable
        onPress={() => setOpen(!open)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={`Awaiting a result: ${calls.length} call${calls.length === 1 ? '' : 's'}`}
        style={({ pressed }) => [styles.row, open && { borderBottomColor: c.line, borderBottomWidth: StyleSheet.hairlineWidth }, { opacity: pressed ? 0.7 : 1 }]}>
        <Mark status="pending" />
        <View style={{ flex: 1, gap: 2 }}>
          <T color={c.fg} style={{ fontWeight: '700' }} numberOfLines={1}>Awaiting a result · {rangeText(calls[calls.length - 1].date, calls[0].date)}</T>
          <T kind="small" color={c.fg2}>{calls.length} call{calls.length === 1 ? '' : 's'}, scored once the week after each is over</T>
        </View>
        <T color={c.muted}>{open ? '−' : '+'}</T>
      </Pressable>
      {open ? calls.map((x, i) => <CallRow key={x.date} c={x} window={window} tankL={tankL} last={i === calls.length - 1} inset />) : null}
    </>
  );
}

function Mark({ status }: { status: CallStatus }) {
  const c = useTheme();
  const col = statusColor(c, status);
  return (
    <View style={[styles.mark, { borderColor: col, backgroundColor: status === 'pending' ? 'transparent' : col }]}>
      <T style={{ fontWeight: '800', fontSize: 14, lineHeight: 18 }} color={status === 'pending' ? col : c.bg}>{MARK[status]}</T>
    </View>
  );
}

/** One day's call: the headline as it was shown, the median it was made at, and what happened */
function CallRow({ c: x, window, tankL, last, inset }: { c: Call; window: number; tankL: number; last: boolean; inset?: boolean }) {
  const c = useTheme();
  const v = callValue(x, tankL);
  const head = x.head || callWord(x);
  return (
    <View
      style={[styles.row, inset && { backgroundColor: c.sunk }, !last && { borderBottomColor: c.line, borderBottomWidth: StyleSheet.hairlineWidth }]}
      accessible
      accessibilityLabel={`${nice(x.date)}: ${head}, at a median of ${x.now.toFixed(1)} cents. ${outcomeText(x, window)}. ${STATUS_WORD[x.status]}.${v ? ` ${v.text}.` : ''}`}>
      <Mark status={x.status} />
      <View style={{ flex: 1, gap: 2 }}>
        <T color={c.fg} style={{ fontWeight: '700' }} numberOfLines={1}>{nice(x.date, false)} · {head}</T>
        <T kind="small" color={c.fg2}>Median {x.now.toFixed(1)}c. {outcomeText(x, window)}</T>
        {v ? <T kind="small" color={v.good ? c.cheap : c.dear} style={{ fontWeight: '600' }}>{v.text}</T> : null}
      </View>
      {x.status === 'pending' ? null : <T kind="small" color={x.status === 'close' ? c.fg2 : statusColor(c, x.status)} style={{ fontWeight: '700' }}>{STATUS_WORD[x.status]}</T>}
    </View>
  );
}

const styles = StyleSheet.create({
  hero: { borderWidth: StyleSheet.hairlineWidth, borderRadius: 20, padding: Spacing.five, gap: Spacing.two },
  bar: { flexDirection: 'row', height: 10, borderRadius: Radius.chip, overflow: 'hidden' },
  legend: { flexDirection: 'row', flexWrap: 'wrap', columnGap: Spacing.four, rowGap: 2 },
  row: { flexDirection: 'row', alignItems: 'center', gap: Spacing.three, paddingVertical: Spacing.three, paddingHorizontal: Spacing.four },
  mark: { width: 28, height: 28, borderRadius: 14, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
});
