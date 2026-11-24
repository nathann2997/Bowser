import { fuelName } from './format';
import type { Fuel, Series, Station, StationDetail, StationForecast, StationPrice, Stations } from './types';

/**
 * Premium diesel (NSW FuelCheck code PDL, 2026-11-25). About 590 of the 850 Sydney stations that sell diesel list it
 * only as PDL: 7-Eleven, most BP, Metro, Ampol Foodary, EG Ampol, Shell Reddy Express. The API carries it under its own
 * key `PDL` (pipeline fuels.py: a station-level fuel, never in Sydney's medians or the model).
 *
 * On load, a station that lists no regular diesel shows its premium diesel as its Diesel, flagged `pd`, so the Diesel
 * list, map, cheapest, pins, drop alerts and the widget all see it. A station that lists both keeps regular diesel as
 * its Diesel and the premium price in `pdl`. Either way `p`, `hist` and `fc` only ever hold the five Fuel keys, so
 * nothing keyed on Fuel meets an unknown one.
 */

const priced = (v: unknown): v is StationPrice => Array.isArray(v) && typeof v[0] === 'number' && Number.isFinite(v[0]);
/** A history whose last day (today) has a price: the station lists that fuel today */
const current = (h: unknown): h is Series => Array.isArray(h) && h.length > 0 && typeof h[h.length - 1] === 'number';

export function premiumDieselStation(s: Station): Station {
  const raw = s.p as Record<string, unknown>;
  if (!('PDL' in raw)) return s;
  const pdl = raw.PDL;
  delete raw.PDL;
  if (!priced(pdl)) return s;
  if (!priced(s.p.DL)) {
    s.p.DL = pdl;
    s.pd = 1;
  } else s.pdl = pdl;
  return s;
}

export function withPremiumDiesel<T extends Stations>(j: T): T {
  if (Array.isArray(j.stations)) for (const s of j.stations) if (s && s.p && typeof s.p === 'object') premiumDieselStation(s);
  return j;
}

/** The station file, by the same rule as its stations.json row. The pipeline says so (`pd`, station_api.py): a DL
 *  history can run on for weeks after a station stops listing DL, so the history alone can't tell. A file without the
 *  field (from before it) falls back to: premium diesel is current and regular diesel isn't. */
export function detailWithPremiumDiesel<T extends StationDetail>(d: T): T {
  const hist = (d.hist ?? {}) as Record<string, Series | undefined>;
  const fc = (d.fc ?? {}) as Record<string, StationForecast | undefined>;
  if (!('PDL' in hist) && !('PDL' in fc)) return d;   // nothing to do, or already done
  const h = hist.PDL, f = fc.PDL;
  delete hist.PDL;
  delete fc.PDL;
  const pd = 'pd' in d ? d.pd === 1 : current(h) && !current(hist.DL);
  if (pd && current(h)) {
    hist.DL = h;
    if (f) fc.DL = f;
    else delete fc.DL;
    d.pd = 1;
    // its profile's typical gap is for the regular diesel it used to list, not this premium price
    if (d.profile?.typ) delete d.profile.typ.DL;
  } else delete d.pd;
  return d;
}

/** Whether the price shown for `fuel` at this station is premium diesel (the only diesel it lists) */
export const isPremium = (s: { pd?: 1 } | null | undefined, fuel: Fuel) => fuel === 'DL' && s?.pd === 1;

/** The fuel's name at this station: "Premium diesel" where that is its only diesel, else the usual name */
export const fuelLabel = (s: { pd?: 1 } | null | undefined, fuel: Fuel) => (isPremium(s, fuel) ? 'Premium diesel' : fuelName(fuel));
