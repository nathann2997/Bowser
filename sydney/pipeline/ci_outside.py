"""pipeline-ci only: stand-in stations outside Sydney, so a test run covers them whatever the archived snapshot holds
(the archive is Sydney-only before 2026-11-13). Never used by the daily run.

  python ci_outside.py add INBOX    adds the stand-ins to the newest nsw_snapshot_*.json in INBOX
  python ci_outside.py check SITE   exits 1 unless the exported site lists them the way a station outside Sydney should be
"""
import datetime as dt, glob, json, os, re, sys

BASE_CODE = 9900000   # far above NSW's station codes
# (address, location, days to push `lastupdated` back)
CASES = [
    ("1 Crown St, WOLLONGONG NSW 2500", {"latitude": -34.4250, "longitude": 150.8931}, 0),
    ("2 Mann St, GOSFORD NSW 2250", {"latitude": -33.4250, "longitude": 151.3420}, 0),
    ("3 Hunter St, NEWCASTLE NSW 2300", {"latitude": -32.9270, "longitude": 151.7760}, 0),
    ("4 Northbourne Ave, CANBERRA ACT 2601", {"latitude": -35.2780, "longitude": 149.1290}, 0),   # another state's address
    ("5 Argent St BROKEN HILL", {"latitude": -31.9560, "longitude": 141.4650}, 0),                # no postcode
    ("6 Macquarie St, DUBBO NSW 2830", {"latitude": -32.2450, "longitude": 148.6010}, 30),         # an old price
    ("7 Kendal St, COWRA NSW 2794", None, 0),                                                      # no position: not listed
    ("8 Sheppard St, Hume ACT 2620", {"latitude": -35.3870, "longitude": 149.1660}, 0),            # ACT, in a postcode NSW shares
    ("9 Metford Road, Metford NEW SOUTH WALES 2323", {"latitude": -32.7650, "longitude": 151.6090}, 0),   # the state spelt out
    ("10 Hill Street, Uralla, NSW  2358, AU", {"latitude": -30.6420, "longitude": 151.5010}, 10),  # ", AU"; a price 10+ days old
]
LISTED = [str(BASE_CODE + i) for i, c in enumerate(CASES) if c[1]]


def add(inbox):
    fn = sorted(glob.glob(f"{inbox}/nsw_snapshot_*.json"), key=os.path.getmtime)[-1]
    j = json.load(open(fn))
    by = {}
    for p in j["prices"]: by.setdefault(str(p["stationcode"]), []).append(p)
    # donors: stations with the most prices, so the stand-ins sell several fuels
    donors = sorted((s for s in j["stations"] if str(s["code"]) in by), key=lambda s: -len(by[str(s["code"])]))[:len(CASES)]
    for i, ((addr, loc, back), d) in enumerate(zip(CASES, donors)):
        code = str(BASE_CODE + i)
        j["stations"].append(dict(d, code=code, name=f"CI stand-in {i}", address=addr, location=loc))
        for p in by[str(d["code"])]:
            q = dict(p, stationcode=code)
            if back:
                try: t = dt.datetime.strptime(p["lastupdated"], "%d/%m/%Y %H:%M:%S")
                except (TypeError, ValueError): t = dt.datetime.now()
                q["lastupdated"] = (t - dt.timedelta(days=back)).strftime("%d/%m/%Y %H:%M:%S")
            j["prices"].append(q)
    json.dump(j, open(fn, "w"))
    print(f"ci_outside: added {len(donors)} stand-in stations outside Sydney to {os.path.basename(fn)}")


def check(site):
    api = f"{site}/api/v1"
    st = json.load(open(f"{api}/stations.json"))
    meta = json.load(open(f"{api}/meta.json"))
    # The stand-ins carry Sydney prices; against a real median for the rest of NSW the quarantine may hide some
    hidden = any(w.startswith("implausible prices hidden") for w in meta.get("warnings", []))
    by = {s["id"]: s for s in st["stations"]}
    errs = []
    for code in LISTED:
        s = by.get(code)
        if s is None: errs.append(f"{code}: not in stations.json"); continue
        if s.get("out") != 1: errs.append(f"{code}: out = {s.get('out')!r}")
        if not s["p"] and not hidden: errs.append(f"{code}: no prices")
        for f, p in s["p"].items():
            if len(p) != 5 or p[2] not in ("na", "chk"): errs.append(f"{code} {f}: {p}")
        path = f"{api}/station/{code}.json"
        if not os.path.exists(path): errs.append(f"{code}: no station file"); continue
        d = json.load(open(path))
        if d["fc"] != {} or d.get("out") != 1 or d["profile"] is not None: errs.append(f"{code}: station file fc/out/profile")
        for f, p in s["p"].items():
            if (d["hist"].get(f) or [None])[-1] != p[0]: errs.append(f"{code} {f}: history doesn't end at today's price")
    unlisted = str(BASE_CODE + next(i for i, c in enumerate(CASES) if not c[1]))
    if unlisted in by: errs.append(f"{unlisted}: listed without a position")
    old = by.get(str(BASE_CODE + 5), {}).get("p", {})
    if old and any(p[2] != "chk" for p in old.values()): errs.append(f"old price isn't Check price: {old}")
    if by.get(str(BASE_CODE + 4), {}).get("pc") != 0: errs.append("no-postcode station: pc should be 0")
    if by.get(str(BASE_CODE + 3), {}).get("pc") != 2601: errs.append("ACT station: pc should be 2601")
    if by.get(str(BASE_CODE + 3), {}).get("st") != "ACT": errs.append("ACT station: st should be ACT")
    hume = by.get(str(BASE_CODE + 7), {})
    if (hume.get("pc"), hume.get("st")) != (2620, "ACT"): errs.append(f"Hume ACT 2620: pc/st {hume.get('pc')}/{hume.get('st')}")
    met = by.get(str(BASE_CODE + 8), {})
    if (met.get("pc"), met.get("s"), met.get("st")) != (2323, "Metford", None): errs.append(f"Metford NEW SOUTH WALES 2323: {met.get('pc')}/{met.get('s')}/{met.get('st')}")
    ura = by.get(str(BASE_CODE + 9), {})
    if (ura.get("pc"), ura.get("s")) != (2358, "Uralla"): errs.append(f"Uralla, NSW 2358, AU: {ura.get('pc')}/{ura.get('s')}")
    # outside Sydney a price is "Check price" only from day 21 (build.py OUT_STALE): 10 days old (plus the donor's own age) is still "Price only"
    if any(p[2] != "na" for p in ura.get("p", {}).values() if p[1] is not None and p[1] <= 20): errs.append(f"price outside Sydney under 21 days isn't Price only: {ura.get('p')}")
    subs = {(x["s"], x["pc"]) for x in st["suburbs"]}
    if ("Wollongong", 2500) not in subs: errs.append("Wollongong 2500 isn't a suburb to search for")
    if any(not pc for _, pc in subs): errs.append("a suburb with no postcode")
    # Sydney stations are untouched: no flag, a forecast advice code, and (when station files were built) a 7-day price
    syd = [s for s in st["stations"] if not s.get("out")]
    if len(syd) < 500: errs.append(f"only {len(syd)} Sydney stations")
    station_files = os.path.isdir(f"{api}/station")
    for s in syd:
        if any(p[2] == "na" or len(p) != (6 if station_files else 5) for p in s["p"].values()):
            errs.append(f"Sydney station {s['id']}: {s['p']}"); break
        if re.fullmatch(r"99\d{5}", s["id"]): errs.append(f"stand-in {s['id']} counted as Sydney")
    if any(w.startswith("station files unavailable") for w in meta.get("warnings", [])): errs.append(f"meta.warnings: {meta['warnings']}")
    print("ci_outside: " + ("OK" if not errs else "FAILED\n  " + "\n  ".join(errs[:20]))
          + f" ({len(st['stations']) - len(syd)} outside Sydney, {len(syd)} in Sydney)")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    {"add": add, "check": check}[sys.argv[1]](sys.argv[2])
