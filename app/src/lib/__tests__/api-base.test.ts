// The API moved when the repo was renamed (FuelForecast -> Bowser): fetches try the new address, then the old one.
import { beforeEach, describe, expect, it, jest } from '@jest/globals';

import { API_BASES, apiFetch, resetApiBase } from '../api';

const res = (status: number) => ({ ok: status >= 200 && status < 300, status }) as Response;
const calls = () => (globalThis.fetch as jest.Mock).mock.calls.map((c) => c[0] as string);

describe('apiFetch', () => {
  beforeEach(resetApiBase);

  it('lists the new address first and the old one second', () => {
    expect(API_BASES).toEqual(['https://nathann2997.github.io/Bowser/api/v1', 'https://nathann2997.github.io/FuelForecast/api/v1']);
  });

  it('before the rename: the new address 404s, the old one answers and is remembered', async () => {
    globalThis.fetch = jest.fn(async (u: string) => res(u.includes('/Bowser/') ? 404 : 200)) as never;
    expect((await apiFetch('meta.json')).ok).toBe(true);
    expect((await apiFetch('forecast.json')).ok).toBe(true);
    expect(calls()).toEqual([`${API_BASES[0]}/meta.json`, `${API_BASES[1]}/meta.json`, `${API_BASES[1]}/forecast.json`]);
  });

  it('after the rename, mid-session: the remembered old address 404s, so the new one is used', async () => {
    let renamed = false;
    globalThis.fetch = jest.fn(async (u: string) => res(u.includes('/Bowser/') === renamed ? 200 : 404)) as never;
    await apiFetch('meta.json');
    renamed = true;
    expect((await apiFetch('meta.json')).ok).toBe(true);
    expect(calls().slice(-2)).toEqual([`${API_BASES[1]}/meta.json`, `${API_BASES[0]}/meta.json`]);
  });

  it('a file missing everywhere is still a 404', async () => {
    globalThis.fetch = jest.fn(async () => res(404)) as never;
    expect((await apiFetch('station/1.json')).status).toBe(404);
  });

  it('offline: throws the network error; one address down: the other answers', async () => {
    globalThis.fetch = jest.fn(async () => { throw new Error('offline'); }) as never;
    await expect(apiFetch('meta.json')).rejects.toThrow('offline');
    globalThis.fetch = jest.fn(async (u: string) => { if (u.includes('/Bowser/')) throw new Error('down'); return res(200); }) as never;
    expect((await apiFetch('meta.json')).ok).toBe(true);
  });
});
