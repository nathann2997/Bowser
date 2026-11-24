// "Filled up": log a fill in two taps (2026-11-24, user feedback: "logging fuel requires too many steps"). The sheet
// opens ready to save: today's price at this station (less your discount) and a full tank. Litres are one-tap chips
// (full, half, other); the price is only typed when you paid something else. Saving shows a note with Undo instead
// of asking to confirm first. Opened from the station page and from the map's station card.
import { useRef, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { Button, Chip, Sheet, T } from '@/components/ui';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { addFill, removeFill, type Fill } from '@/lib/fills';
import { fuelName, stationName, sydneyToday } from '@/lib/format';
import { loggedText, money } from '@/lib/savings';
import type { Fuel } from '@/lib/types';

export type FillTarget = { id: string; n: string; b: string; s: string };

/** A typed number to 0.1, or null while the text isn't one in range */
const parse = (t: string, lo: number, hi: number) => {
  const v = Math.round(parseFloat(t.replace(',', '.')) * 10) / 10;
  return Number.isFinite(v) && v >= lo && v <= hi ? v : null;
};

export function FillSheet({
  station, fuel, price, pump, median, tankL, onClose, onSaved,
}: {
  station: FillTarget; fuel: Fuel;
  price: number;              // your price today (pump less your discount)
  pump: number;               // the pump price today
  median: number | null;      // today's Sydney median for the fuel (null outside Sydney: the savings are Sydney's)
  tankL: number;
  onClose: () => void;
  onSaved: (note: FillNoteData) => void;
}) {
  const c = useTheme();
  const half = Math.round(tankL / 2);
  const [amount, setAmount] = useState<'full' | 'half' | 'other'>('full');
  const [litresT, setLitresT] = useState(String(tankL));
  const [editPrice, setEditPrice] = useState(false);
  const [paidT, setPaidT] = useState(price.toFixed(1));
  const paid = parse(paidT, 50, 800);
  const litres = amount === 'full' ? tankL : amount === 'half' ? half : parse(litresT, 1, 200);
  const ok = paid != null && litres != null;
  const gap = ok && median != null ? median - paid : null;

  const saved = useRef(false);   // a quick double tap logs one fill, not two
  const save = () => {
    if (!ok || saved.current) return;
    saved.current = true;
    const f = addFill({
      date: sydneyToday(), stationId: station.id || null, name: stationName(station.n), brand: station.b, suburb: station.s,
      fuel, pump, paid, litres, median,
    });
    onSaved(f ? { text: loggedText(f), fill: f } : { text: 'Couldn’t log that fill.' });
    onClose();
  };

  return (
    <Sheet
      title="Filled up"
      visible
      onClose={onClose}
      footer={
        <Button
          label={ok ? `Log ${litres} L at ${paid!.toFixed(1)}c · ${money((paid! * litres!) / 100)}` : 'Check the price and litres'}
          onPress={save}
          disabled={!ok}
        />
      }>
      <T color={c.fg2}>{stationName(station.n)} · {fuelName(fuel)} · today</T>

      <View style={{ gap: Spacing.two }}>
        <T kind="eyebrow">How much</T>
        <View style={styles.chips} accessibilityLabel="How much you filled">
          <Chip label={`Full tank · ${tankL} L`} on={amount === 'full'} onPress={() => setAmount('full')} />
          <Chip label={`Half · ${half} L`} on={amount === 'half'} onPress={() => setAmount('half')} />
          <Chip label="Other" on={amount === 'other'} onPress={() => setAmount('other')} />
        </View>
        {amount === 'other' ? (
          <Field value={litresT} onChange={setLitresT} bad={litres == null} a11y="Litres" suffix="L" autoFocus />
        ) : null}
      </View>

      <View style={{ gap: Spacing.two }}>
        <View style={styles.priceRow}>
          <T kind="eyebrow">Price</T>
          {!editPrice ? (
            <Pressable onPress={() => setEditPrice(true)} accessibilityRole="button" accessibilityLabel={`Paid ${paidT} cents a litre. Change it`} hitSlop={8}>
              <T color={c.fg} style={{ fontWeight: '700' }}>
                {paidT}c/L{'   '}<T color={c.link} style={{ fontWeight: '700' }}>Paid something else?</T>
              </T>
            </Pressable>
          ) : null}
        </View>
        {editPrice ? (
          <Field value={paidT} onChange={setPaidT} bad={paid == null} a11y="Price you paid in cents per litre" suffix="c/L" autoFocus />
        ) : null}
      </View>

      {gap != null ? (
        <T kind="small" color={gap > 0.05 ? c.cheap : gap < -0.05 ? c.dear : c.fg2} style={{ fontWeight: '600' }}>
          {Math.abs(gap) < 0.05
            ? 'Right on the Sydney median today.'
            : `${Math.abs(gap).toFixed(1)}c ${gap > 0 ? 'under' : 'over'} the Sydney median (${median!.toFixed(1)}), ${money(Math.abs((gap * litres!) / 100))} on this fill.`}
        </T>
      ) : null}
      <T kind="small">Your fills stay on this phone.</T>
    </Sheet>
  );
}

function Field({ value, onChange, bad, a11y, suffix, autoFocus }: { value: string; onChange: (t: string) => void; bad: boolean; a11y: string; suffix: string; autoFocus?: boolean }) {
  const c = useTheme();
  return (
    <View style={[styles.field, { borderColor: bad ? c.up : c.line, backgroundColor: c.surface }]}>
      <TextInput
        value={value}
        onChangeText={(t) => onChange(t.replace(/[^0-9.,]/g, ''))}
        keyboardType="decimal-pad"
        selectTextOnFocus
        autoFocus={autoFocus}
        accessibilityLabel={a11y}
        style={[styles.input, { color: c.fg }]}
      />
      <T color={c.muted} style={{ fontWeight: '600' }}>{suffix}</T>
    </View>
  );
}

/** What a save leaves behind: the "Logged…" line, and the fill so it can be undone */
export type FillNoteData = { text: string; fill?: Fill };

/** The note after a fill is logged, with Undo (which removes that fill). The caller clears it after a few seconds. */
export function FillNote({ note, onDone }: { note: FillNoteData; onDone: () => void }) {
  const c = useTheme();
  const [undone, setUndone] = useState(false);
  return (
    <View style={[styles.note, { backgroundColor: c.fg }]} accessibilityLiveRegion="polite">
      <T kind="small" color={c.bg} style={{ fontWeight: '600', flexShrink: 1 }}>{undone ? 'Fill removed.' : note.text}</T>
      {note.fill && !undone ? (
        <Pressable
          onPress={() => { removeFill(note.fill!.id); setUndone(true); setTimeout(onDone, 1500); }}
          accessibilityRole="button"
          accessibilityLabel="Undo, remove this fill"
          hitSlop={10}>
          <T kind="small" color={c.bg} style={{ fontWeight: '800', textDecorationLine: 'underline' }}>Undo</T>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  priceRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: Spacing.two },
  field: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two, borderWidth: 1, borderRadius: Radius.input, paddingHorizontal: Spacing.three },
  input: { flex: 1, paddingVertical: 12, fontSize: 20, fontWeight: '700', fontVariant: ['tabular-nums'] },
  note: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.three, borderRadius: Radius.input,
    paddingVertical: Spacing.two, paddingHorizontal: Spacing.three, alignSelf: 'flex-start', maxWidth: '100%',
  },
});
