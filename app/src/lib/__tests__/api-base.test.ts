// The API is on checkbowser.app, with the repo's Pages address as the fallback: fetches try the domain, then the old address.
import { beforeEach, describe, expect, it, jest } from '@jest/globals';

import { API_BASES, apiFetch, resetApiBase } from '../api';

const res = (status: number) => ({ ok: status >= 200 && status < 300, status }) as Response;
const calls = () => (globalThis.fetch as jest.Mock).mock.calls.map((c) => c[0] as string);

describe('apiFetch', () => {
  beforeEach(resetApiBase);

  it('lists the custom domain first and the Pages address second', () => {
    expect(API_BASES).toEqual(['https://checkbowser.app/api/v1', 'https://nathann2997.github.io/Bowser/api/v1']);
  });

  it('domain not serving the site (custom domain removed): the Pages address answers and is remembered', async () => {
    globalThis.fetch = jest.fn(async (u: string) => res(u.includes('checkbowser.app') ? 404 : 200)) as never;
    expect((await apiFetch('meta.json')).ok).toBe(true);
    expect((await apiFetch('forecast.json')).ok).toBe(true);
    expect(calls()).toEqual([`${API_BASES[0]}/meta.json`, `${API_BASES[1]}/meta.json`, `${API_BASES[1]}/forecast.json`]);
  });

  it('domain back, mid-session: the remembered Pages address 404s, so the domain is used', async () => {
    let live = false;
    globalThis.fetch = jest.fn(async (u: string) => res(u.includes('checkbowser.app') === live ? 200 : 404)) as never;
    await apiFetch('meta.json');
    live = true;
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
    globalThis.fetch = jest.fn(async (u: string) => { if (u.includes('checkbowser.app')) throw new Error('down'); return res(200); }) as never;
    expect((await apiFetch('meta.json')).ok).toBe(true);
  });
});
