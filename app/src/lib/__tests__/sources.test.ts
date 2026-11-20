// Google Play's Misleading Claims policy: the official source is linked and the app says it isn't a government app.
import { describe, expect, it } from '@jest/globals';

import { FUELCHECK_DATA_URL, FUELCHECK_URL, NOT_GOVERNMENT, NOT_GOVERNMENT_SHORT, SOURCE_LINE, SOURCE_NAME } from '../sources';

describe('sources', () => {
  it('links the official NSW Government addresses over https', () => {
    expect(FUELCHECK_URL).toBe('https://www.fuelcheck.nsw.gov.au/');
    expect(new URL(FUELCHECK_DATA_URL).hostname).toBe('data.nsw.gov.au');
  });

  it('says plainly that Bowser is not a government app, next to the source', () => {
    expect(NOT_GOVERNMENT).toMatch(/not a government app/);
    expect(SOURCE_LINE).toMatch(/not a government app/);
    expect(SOURCE_LINE).toBe(`Prices: ${SOURCE_NAME}. ${NOT_GOVERNMENT_SHORT}`);
    expect(SOURCE_NAME).toContain(new URL(FUELCHECK_URL).hostname.replace(/^www\./, ''));
    expect(NOT_GOVERNMENT).toMatch(/any government agency/);
  });
});
