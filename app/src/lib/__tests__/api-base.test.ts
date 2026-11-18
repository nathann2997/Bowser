// The API is on checkbowser.app only (the GitHub Pages fallback address was taken out on 2026-11-18, so nothing in the
// app points at the source). The fallback logic stays, tested here over two stand-in addresses.
import { beforeEach, describe, expect, it, jest } from '@jest/globals';

import { API_BASES, apiFetch, baseFetcher, resetApiBase } from '../api';

const res = (status: number) => ({ ok: status >= 200 && status < 300, status }) as Response;
const calls = () => (globalThis.fetch as jest.Mock).mock.calls.map((c) => c[0] as string);
const A = 'https://a.example/api/v1';
const B = 'https://b.example/api/v1';

describe('API_BASES', () => {
  it('is checkbowser.app alone: no GitHub address anywhere in the app', () => {
    expect(API_BASES).toEqual(['https://checkbowser.app/api/v1']);
    expect(API_BASES.join(' ')).not.toMatch(/github/i);
  });

  it('apiFetch asks checkbowser.app', async () => {
    resetApiBase();
    globalThis.fetch = jest.fn(async () => res(200)) as never;
    expect((await apiFetch('meta.json')).ok).toBe(true);
    expect(calls()).toEqual(['https://checkbowser.app/api/v1/meta.json']);
  });
});

describe('baseFetcher', () => {
  let f: ReturnType<typeof baseFetcher>;
  beforeEach(() => {
    f = baseFetcher([A, B]);
  });

  it('first address not serving: the second answers and is remembered', async () => {
    globalThis.fetch = jest.fn(async (u: string) => res(u.startsWith(A) ? 404 : 200)) as never;
    expect((await f.get('meta.json')).ok).toBe(true);
    expect((await f.get('forecast.json')).ok).toBe(true);
    expect(calls()).toEqual([`${A}/meta.json`, `${B}/meta.json`, `${B}/forecast.json`]);
  });

  it('first address back, mid-session: the remembered one 404s, so the first is used', async () => {
    let live = false;
    globalThis.fetch = jest.fn(async (u: string) => res(u.startsWith(A) === live ? 200 : 404)) as never;
    await f.get('meta.json');
    live = true;
    expect((await f.get('meta.json')).ok).toBe(true);
    expect(calls().slice(-2)).toEqual([`${B}/meta.json`, `${A}/meta.json`]);
  });

  it('a file missing everywhere is still a 404', async () => {
    globalThis.fetch = jest.fn(async () => res(404)) as never;
    expect((await f.get('station/1.json')).status).toBe(404);
  });

  it('offline: throws the network error; one address down: the other answers', async () => {
    globalThis.fetch = jest.fn(async () => { throw new Error('offline'); }) as never;
    await expect(f.get('meta.json')).rejects.toThrow('offline');
    globalThis.fetch = jest.fn(async (u: string) => { if (u.startsWith(A)) throw new Error('down'); return res(200); }) as never;
    expect((await f.get('meta.json')).ok).toBe(true);
  });
});
