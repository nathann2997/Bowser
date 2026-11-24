"""The fuels the pipeline tracks, in display order. Every pipeline script imports this list. Own copies to change
with it: fetch.py, station_profile.py (petrol list), template.html, share.html, and in app/src: lib/types.ts, format.ts,
settings.ts, fills.ts, components/ui.tsx, app/savings.tsx, app/station/[id].tsx, widget/logic.ts.
E85, LPG and B20 are in the NSW feed but left out (E85: 17 Sydney stations, too few to forecast).

PDL (premium diesel, 2026-11-25) is a station-level fuel only: it is in the station list, the station files and their
charts, but never in Sydney's medians, the regions, the model or the backtest. 7-Eleven, most BP, Metro, Ampol Foodary
and EG Ampol list their only diesel as PDL (about 590 of 850 Sydney diesel stations), so without it most diesel
stations were missing. Its station forecast and advice borrow DL's market (Sydney's PDL-only median tracks DL's at
+3-7c, day by day). The clients show it under Diesel where a station lists no regular diesel, marked premium.
"""
FUELS = ["U91", "E10", "P95", "P98", "DL"]
PDL = "PDL"
STATION_FUELS = FUELS + [PDL]                # what a station's prices (stations.json `p`, station/{id}.json) can hold
MARKET = {PDL: "DL"}                         # a station-level fuel's Sydney market: its forecast and advice come from there
