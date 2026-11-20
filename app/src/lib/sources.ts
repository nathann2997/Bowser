// Where Bowser's prices come from, and the line saying Bowser isn't a government app.
//
// Google Play's Misleading Claims policy (rejection of 2026-11-20): an app that shows government information (NSW
// FuelCheck prices) must link the official source and say clearly that it doesn't represent a government. These are
// shown on the welcome screen, Today, Stations (list), each station's page and More → About, and the same wording is in
// the Play description (docs/PLAY_STORE.md) and on the website (seo_pages.py SOURCES, template.html footer). Keep them
// in step.
export const FUELCHECK_URL = 'https://www.fuelcheck.nsw.gov.au/';
export const FUELCHECK_DATA_URL = 'https://data.nsw.gov.au/data/dataset/fuel-check';

export const NOT_GOVERNMENT =
  'Bowser is an independent app, not a government app. It is not affiliated with, endorsed by or representing the NSW Government or any government agency.';

/** The parts of the line under prices (components/source-line.tsx renders them, the source name as a link) */
export const SOURCE_NAME = 'NSW Government FuelCheck, fuelcheck.nsw.gov.au';
export const NOT_GOVERNMENT_SHORT = 'Bowser is not a government app.';
export const SOURCE_LINE = `Prices: ${SOURCE_NAME}. ${NOT_GOVERNMENT_SHORT}`;
