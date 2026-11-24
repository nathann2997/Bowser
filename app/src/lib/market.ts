// The median a station's price is compared with (2026-11-24): its own market. A Sydney station is compared with the
// Sydney median (the verdict card's number); a station outside Sydney with its regional centre's median, e.g. Canberra
// (stations.json `regions`, 8+ current prices, pipeline local_median.py); a station in no region gets no comparison.
// Before this, outside Sydney showed either nothing or, earlier, the Sydney median, which told a Canberra driver a
// Belconnen station was "14.5c dearer" when it was cheaper than most of Canberra.
import type { Fuel, Region, Station } from './types';

export type Market = { med: number; name: string; n?: number };

export function marketFor(
  s: Pick<Station, 'out' | 'rg'> | null | undefined,
  fuel: Fuel | null | undefined,
  sydney: number | null | undefined,
  regions: Record<string, Region> | undefined,
): Market | null {
  if (!s || !fuel) return null;
  if (!s.out) return sydney != null ? { med: sydney, name: 'Sydney' } : null;
  const r = s.rg ? regions?.[s.rg] : undefined;
  const f = r?.f[fuel];
  return r && f ? { med: f[0], name: r.name, n: f[1] } : null;
}

/** "5.0c cheaper" / "At the Canberra median" lead words; the caller adds " than the X median (219.8c)" */
export function gapWords(gap: number, m: Market): { lead: string; rest: string } {
  if (Math.abs(gap) < 0.05) return { lead: `At the ${m.name} median`, rest: ` (${m.med.toFixed(1)}c)` };
  return { lead: `${Math.abs(gap).toFixed(1)}c ${gap < 0 ? 'cheaper' : 'dearer'}`, rest: ` than the ${m.name} median (${m.med.toFixed(1)}c)` };
}
