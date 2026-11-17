import { useQuery } from '@tanstack/react-query';

import type { Forecast, History, Meta, StationDetail, Stations, Track } from './types';

// The API is the repo's GitHub Pages site, on its custom domain checkbowser.app (2026-11). The repo's own Pages address
// redirects there, and is the fallback: if the custom domain is ever taken off (or its DNS breaks), that address serves
// the site directly again. (The pre-rename …/FuelForecast/ address is gone.) EXPO_PUBLIC_API_BASE points a build at
// another copy of the API instead.
const BASES = ['https://checkbowser.app/api/v1', 'https://nathann2997.github.io/Bowser/api/v1'];
export const API_BASES = process.env.EXPO_PUBLIC_API_BASE ? [process.env.EXPO_PUBLIC_API_BASE] : BASES;
/** The address for links people share and for labels; fetches go through apiFetch() */
export const API_BASE = API_BASES[0];

let good = -1;   // the base that last answered OK, tried first
/** Test hook: forget which base answered */
export const resetApiBase = () => { good = -1; };

/**
 * fetch() of an API file, from whichever base serves it. The base that last worked is asked first; if it fails, the
 * others are tried in order. With none OK, the first HTTP response is returned (so a 404 still reads as a 404), or
 * the first network error is thrown.
 */
export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const order = good >= 0 ? [good, ...API_BASES.map((_, i) => i).filter((i) => i !== good)] : API_BASES.map((_, i) => i);
  let bad: Response | undefined;
  let err: unknown;
  for (const i of order) {
    try {
      const r = await fetch(`${API_BASES[i]}/${path}`, init);
      if (r.ok) {
        good = i;
        return r;
      }
      bad ??= r;
    } catch (e) {
      err ??= e;
    }
  }
  if (bad) return bad;
  throw err;
}
const SCHEMA = 1;

/** A non-OK HTTP response; `status` lets callers treat a missing file (404) differently from a network error */
export class HttpError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}
export const isNotFound = (e: unknown) => e instanceof HttpError && e.status === 404;

/** Far above any real file (stations.json is under 1 MB): a bigger declared size isn't parsed */
export const MAX_JSON_BYTES = 25 * 1024 * 1024;
export const tooBig = (r: Response) => Number(r.headers.get('content-length') ?? 0) > MAX_JSON_BYTES;

const str = (v: unknown) => typeof v === 'string';
const rows = (v: unknown, ok: (x: Record<string, unknown>) => boolean) =>
  Array.isArray(v) && v.every((x) => !!x && typeof x === 'object' && ok(x as Record<string, unknown>));
/**
 * The fields every screen relies on, checked before anything is shown or saved on the phone: a damaged or tampered
 * file is an error (the saved copy stays), not a crash or bad data kept for days. Light on purpose: types, not values.
 */
export function shapeOk(name: string, j: Record<string, unknown>): boolean {
  if (name.startsWith('station/')) return str(j.id) && str(j.n);
  switch (name) {
    case 'meta': return str(j.asof);
    case 'forecast': return str(j.asof) && rows(j.live, (r) => str(r.fuel));
    case 'stations': return str(j.asof) && rows(j.stations, (s) => str(s.id) && str(s.n)) && Array.isArray(j.suburbs);
    case 'history': return str(j.start) && !!j.hist && typeof j.hist === 'object';
    case 'track': return str(j.asof);
    default: return true;
  }
}

async function getJson<T extends { schema: number }>(name: string): Promise<T> {
  const r = await apiFetch(`${name}.json`, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new HttpError(`${name}.json: HTTP ${r.status}`, r.status);
  if (tooBig(r)) throw new Error(`${name}.json: too large`);
  const j = (await r.json()) as T;
  if (j.schema !== SCHEMA) throw new Error(`${name}.json: schema ${j.schema}, app expects ${SCHEMA}. Update the app.`);
  if (!shapeOk(name, j as unknown as Record<string, unknown>)) throw new Error(`${name}.json: unexpected shape`);
  return j;
}

// Data changes once a day; the CDN caches for 10 minutes. Refetch on focus at most every 15 minutes.
const opts = { staleTime: 15 * 60 * 1000 };

export const useMeta = () => useQuery({ queryKey: ['meta'], queryFn: () => getJson<Meta>('meta'), ...opts });
export const useForecast = () => useQuery({ queryKey: ['forecast'], queryFn: () => getJson<Forecast>('forecast'), ...opts });
export const useStations = () => useQuery({ queryKey: ['stations'], queryFn: () => getJson<Stations>('stations'), ...opts });
export const useHistory = () => useQuery({ queryKey: ['history'], queryFn: () => getJson<History>('history'), ...opts });
/** The track record; a 404 (an API from before 0.7, or a day track.json failed soft) isn't retried */
export const useTrack = () =>
  useQuery({ queryKey: ['track'], queryFn: () => getJson<Track>('track'), retry: (n, e) => !isNotFound(e) && n < 2, ...opts });
/** NSW station codes are digits; anything else (a mistyped deep link) is never fetched */
export const isStationId = (id: string | undefined): id is string => !!id && /^\d+$/.test(id);

export const useStationDetail = (id: string | undefined) =>
  useQuery({
    queryKey: ['station', id],
    queryFn: () => getJson<StationDetail>(`station/${id}`),
    enabled: isStationId(id),
    // A 404 means the per-station export failed soft today (stations.json still lists it): don't retry that
    retry: (n, e) => !isNotFound(e) && n < 2,
    ...opts,
    // Long enough to reopen a recently visited station offline, short enough that the persisted cache
    // doesn't keep every station ever opened
    gcTime: 6 * 60 * 60 * 1000,
  });
