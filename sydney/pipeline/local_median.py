"""The local median a station outside Sydney is compared with (2026-11-24).

A Sydney station is compared with the Sydney median (forecast.json's `live[].now`, the verdict card's number). Until
now a station outside Sydney had no comparison at all, and before that it was wrongly compared with Sydney: a Canberra
driver saw "14.5c dearer than the Sydney median" on a Belconnen station. Here each station outside Sydney gets its own
market: the regional centre it belongs to (seo_pages.REGIONS, the same rule and the same names as the region pages,
so the Canberra page and the app quote the same median).

The median is of current prices (the region pages' rule: up to OUT_STALE days old outside Sydney), members-only sites
left out, and only where at least MIN_N stations report the fuel. With fewer, one station moves the median by several
cents and "dearer than the median" says more about which stations happened to report than about the market. A station
in no region, or in a region without enough prices for that fuel, gets no comparison.
"""
import statistics

from seo_pages import OUT_STALE, REGION_TITLE, REGIONS, km

MIN_N = 8


def region_of(st):
    """The name of the regional centre a station outside Sydney belongs to (seo_pages.Site's rule), or None."""
    if not st.get("out") or not isinstance(st.get("la"), (int, float)) or not isinstance(st.get("lo"), (int, float)):
        return None
    d, name = min((km((st["la"], st["lo"]), (la, lo)) / r, n) for n, la, lo, r in REGIONS)
    return name if d <= 1 else None


def current(pr):
    """True for a price entry [price, days, ...] that is a number and no older than OUT_STALE days."""
    return bool(pr) and isinstance(pr[0], (int, float)) and not (isinstance(pr[1], (int, float)) and pr[1] > OUT_STALE)


def add(stations, fuels):
    """Sets `rg` on each station outside Sydney that belongs to a region; returns {region: {"name", "f": {fuel: [median, n]}}}
    for the regions with at least one fuel of MIN_N+ current prices. Stations whose region has none lose their `rg`."""
    pools = {}
    for st in stations:
        st.pop("rg", None)
        rg = region_of(st)
        if rg: st["rg"] = rg; pools.setdefault(rg, []).append(st)
    out = {}
    for rg, pool in pools.items():
        f = {}
        for fu in fuels:
            ps = [st["p"][fu][0] for st in pool if not st.get("m") and current(st["p"].get(fu))]
            if len(ps) >= MIN_N: f[fu] = [round(statistics.median(ps), 1), len(ps)]
        if f: out[rg] = {"name": REGION_TITLE.get(rg, rg), "f": f}
    for st in stations:
        if st.get("rg") and st["rg"] not in out: del st["rg"]
    return out
