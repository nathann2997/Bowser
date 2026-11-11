"""Daily: fold the latest raw pulls in inbox/ into the store.

inbox/ may contain (any subset; newest of each is used):
  nsw_snapshot_*.json   raw response of GET /FuelPriceCheck/v1/fuel/prices
  AIP_TGP_Data_*.xlsx   AIP historical TGP workbook
  aip_tgp_page.csv      the last five business days of Sydney TGP from the AIP page (fetch.py pull_aip_page)
  brent_audusd_eia_rba.csv  Brent (EIA) and AUD/USD (RBA), under the FRED column ids (fetch.py pull_macro)
  eia_daily_page.csv    the latest Brent and NY Harbor diesel close from EIA's daily page (fetch.py pull_eia_daily)
Writes store/daily.csv (adds/replaces snapshot rows), store/tgp.csv, store/fred.csv, store/stations_today.json,
store/eia_daily.csv (the daily page's readings, kept because the page only shows the latest) and
store/station_feats.csv (snapshot rows; station_feats.py, for the shadow forecast only)
"""
import glob, json, os, re, sys
import numpy as np, pandas as pd

BASE = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX = sys.argv[2] if len(sys.argv) > 2 else f"{BASE}/inbox"
STORE = f"{BASE}/store"
from fuels import FUELS
is_syd = lambda pc: (2000 <= pc <= 2234) or (2555 <= pc <= 2574) or (2740 <= pc <= 2786)
newest = lambda pat: (sorted(glob.glob(f"{INBOX}/{pat}"), key=os.path.getmtime) or [None])[-1]
log = []

# ---- NSW live snapshot -> one daily row per fuel (same definitions as build_history.py)
def snapshot_rows(j, snap):
    """Sydney stations, prices and one daily row per fuel from a raw (or archived) NSW snapshot."""
    st = pd.DataFrame(j["stations"]); pr = pd.DataFrame(j["prices"])
    st["postcode"] = pd.to_numeric(st.address.str.extract(r"NSW\s+(\d{4})\s*$")[0], errors="coerce")
    st["suburb"] = st.address.str.extract(r",\s*([^,]+?)\s+NSW\s+\d{4}\s*$")[0].str.title()
    st = st[st.postcode.fillna(0).astype(int).map(is_syd)]
    pr["code"] = pr.stationcode.astype(str); st["code"] = st.code.astype(str)
    # Station codes become file names downstream (station_api.py, export_api.py): keep NSW's numeric codes only
    pr = pr[pr.code.str.fullmatch(r"\d+")]; st = st[st.code.str.fullmatch(r"\d+")]
    st["key"] = st.address.str.upper().str.replace(",", " ").str.replace(r"\s+", " ", regex=True).str.strip()
    pr = pr.merge(st[["code", "name", "brand", "postcode", "suburb", "location", "key"]], on="code")
    pr = pr[pr.fueltype.isin(FUELS) & pr.price.between(50, 600)].copy()
    pr["ts"] = pd.to_datetime(pr.lastupdated, dayfirst=True, errors="coerce")
    asof = pd.Timestamp(re.search(r"(\d{8})", os.path.basename(snap)).group(1)) if re.search(r"(\d{8})", os.path.basename(snap)) else pr.ts.max().normalize()
    pr["age"] = (asof - pr.ts.dt.normalize()).dt.days
    rows = []
    for f, g in pr.groupby("fueltype"):
        a = g.price.values; rec, old = g[g.age <= 2].price, g[g.age > 7].price
        rows.append(dict(date=asof.date(), fuel=f, n=len(a), median=np.median(a), mean=a.mean(),
                         p10=np.percentile(a, 10), p25=np.percentile(a, 25), p75=np.percentile(a, 75),
                         p90=np.percentile(a, 90), hikes=np.nan, cuts=np.nan,
                         share_upd_1d=(g.age <= 1).mean(), share_upd_3d=(g.age <= 3).mean(), share_upd_7d=(g.age <= 7).mean(),
                         recent_minus_old=(rec.median() - old.median()) if len(rec) > 5 and len(old) > 5 else np.nan,
                         source="snapshot"))
    return st, pr, asof, rows


snap = newest("nsw_snapshot_*.json")
if snap:
    j = json.load(open(snap))
    st, pr, asof, rows = snapshot_rows(j, snap)
    D = pd.read_csv(f"{STORE}/daily.csv", parse_dates=["date"])
    new = pd.DataFrame(rows).round(3); new["date"] = pd.to_datetime(new.date)
    D = pd.concat([D[~((D.date == asof) & (D.source == "snapshot"))], new]).sort_values(["date", "fuel"])
    D = D.drop_duplicates(["date", "fuel"], keep="first")  # history rows win over a snapshot for the same day
    # A fuel added to FUELS later (P95, 2026-10) has no snapshot rows for the days already archived: rebuild those days'
    # missing fuels from archive/ (days after the published history only; the history covers the rest)
    import gzip
    hist_end = D[D.source == "history"].date.max()
    back = []
    for fn in sorted(glob.glob(f"{BASE}/archive/nsw_snapshot_*.json.gz")):
        day = pd.Timestamp(re.search(r"(\d{8})", os.path.basename(fn)).group(1))
        miss = set(FUELS) - set(D[D.date == day].fuel)
        if day <= hist_end or day == asof or not miss: continue
        with gzip.open(fn, "rt") as fh: arch = json.load(fh)
        back += [r for r in snapshot_rows(arch, fn)[3] if r["fuel"] in miss]
    if back:
        b = pd.DataFrame(back).round(3); b["date"] = pd.to_datetime(b.date)
        D = pd.concat([D, b]).sort_values(["date", "fuel"])
        log.append(f"backfilled {len(b)} fuel-day(s) from archive/: {sorted(set(b.fuel))}")
    D.to_csv(f"{STORE}/daily.csv", index=False)
    pr["lat"] = pr.location.map(lambda l: (l or {}).get("latitude")); pr["lon"] = pr.location.map(lambda l: (l or {}).get("longitude"))
    keep = pr[["code", "key", "name", "brand", "postcode", "suburb", "lat", "lon", "fueltype", "price", "age"]]
    json.dump({"asof": str(asof.date()), "rows": keep.to_dict(orient="records")}, open(f"{STORE}/stations_today.json", "w"))
    # station-level archive: today's Sydney stations and prices, gzipped (kept in the repo)
    os.makedirs(f"{BASE}/archive", exist_ok=True)
    codes = set(st.code.astype(str))
    with gzip.open(f"{BASE}/archive/nsw_snapshot_{asof:%Y%m%d}.json.gz", "wt") as fh:
        json.dump({"stations": [s for s in j["stations"] if str(s["code"]) in codes],
                   "prices": [p for p in j["prices"] if str(p["stationcode"]) in codes]}, fh)
    log.append(f"snapshot {asof.date()}: {len(pr)} Sydney prices")
    # ---- station features for the shadow forecast (station_feats.py): today against the archived snapshots of 1, 3 and
    # 7 days ago, plus any day after the published history that has an archived snapshot but no row yet. Never fatal.
    try:
        import station_feats as SF
        fpath = f"{STORE}/station_feats.csv"
        SFd = pd.read_csv(fpath, parse_dates=["date"]) if os.path.exists(fpath) else pd.DataFrame(columns=["date", "fuel"] + SF.COLS + ["source"])
        cache = {asof: pr}
        def prices(day):
            """A day's Sydney price table from archive/ (None if that day wasn't archived)."""
            if day not in cache:
                fn = f"{BASE}/archive/nsw_snapshot_{day:%Y%m%d}.json.gz"; cache[day] = None
                if os.path.exists(fn):
                    with gzip.open(fn, "rt") as fh: cache[day] = snapshot_rows(json.load(fh), fn)[1]
            return cache[day]
        have = set(SFd.date)
        todo = [asof] + [d for d in sorted(pd.Timestamp(re.search(r"(\d{8})", os.path.basename(fn)).group(1))
                                           for fn in glob.glob(f"{BASE}/archive/nsw_snapshot_*.json.gz"))
                         if d > hist_end and d != asof and d not in have]
        srows = []
        for day in todo:
            now = prices(day)
            for f in FUELS:
                one = lambda t: None if t is None else t[t.fueltype == f][["code", "price", "brand"]]
                r = SF.from_snapshots(one(now), {k: one(prices(day - pd.Timedelta(days=k))) for k in (1, 3, 7)})
                srows.append(dict(date=day, fuel=f, **r, source="snapshot"))
        new = pd.DataFrame(srows).round(4)
        SFd = SFd[~(SFd.date.isin(todo) & (SFd.source == "snapshot"))]
        SFd = pd.concat([SFd, new]).sort_values(["date", "fuel"]).drop_duplicates(["date", "fuel"], keep="first")   # history rows win
        SFd.to_csv(fpath, index=False, date_format="%Y-%m-%d")
        if len(todo) > 1: log.append(f"station features: {len(todo)} snapshot days")
    except Exception as e:
        log.append(f"station features skipped ({type(e).__name__}: {str(e)[:120]})")

# ---- AIP TGP. The workbook is the record but only gains its rows on Fridays; the AIP page (fetch.py pull_aip_page) has
# the business days since (today's once AIP has collated it). So: the workbook, then page rows for the days after it, then the rows
# already stored for days after both (an earlier run's page rows). Without a workbook today, the stored file stands in.
tpath = f"{STORE}/tgp.csv"
try:
    T_old = pd.read_csv(tpath, parse_dates=["date"]).set_index("date")[["tgp_ulp", "tgp_dl"]]
    if T_old.empty: T_old = None
except Exception:
    T_old = None          # missing or damaged: the workbook rebuilds it, as it always did
x = newest("AIP_TGP_Data_*.xlsx"); T = T_old
if x:
    out = {}
    for sheet, col in [("Petrol TGP", "tgp_ulp"), ("Diesel TGP", "tgp_dl")]:
        s = pd.read_excel(x, sheet_name=sheet, header=0)
        s = s.iloc[:, :2]; s.columns = ["date", col]
        s["date"] = pd.to_datetime(s.date, errors="coerce"); out[col] = s.dropna().set_index("date")[col]
    T = pd.concat(out, axis=1).sort_index()
    if T_old is not None: T = pd.concat([T, T_old[T_old.index > T.index.max()]])
pg = newest("aip_tgp_page*.csv")
if pg and T is not None and len(T):
    try:
        Pg = pd.read_csv(pg, parse_dates=["date"]).set_index("date")[["tgp_ulp", "tgp_dl"]].dropna().sort_index()
        wb_last = T.index.max() if not x else pd.concat(out, axis=1).index.max()
        Pg = Pg[Pg.index > wb_last]
        # a wrong row or a misread table would show as a jump: TGP's largest one-day move since 2004 is 24c (1 Apr 2026).
        # Each page row is checked against the newest earlier value of each fuel (a stored page row if the workbook is old)
        ok = []
        for d, r in Pg.iterrows():
            before = pd.concat([T[T.index < d], Pg.loc[ok]]).sort_index()
            ref = pd.Series({c: before[c].dropna().iloc[-1] if before[c].notna().any() else np.nan for c in ["tgp_ulp", "tgp_dl"]})
            if ref.isna().any() or (r - ref).abs().max() > 40: log.append(f"tgp page {d.date()} ignored ({r.tgp_ulp:g}/{r.tgp_dl:g} vs {ref.tgp_ulp:g}/{ref.tgp_dl:g})"); break
            ok.append(d)
        if ok: T = pd.concat([T[~T.index.isin(ok)], Pg.loc[ok]]).sort_index()
    except Exception as e:
        log.append(f"tgp page skipped ({type(e).__name__}: {str(e)[:120]})")
if T is not None and (x or pg):
    T = T[~T.index.duplicated(keep="last")].sort_index()
    T.to_csv(tpath, index_label="date")
    log.append(f"tgp to {T.index.max().date()}" + ("" if x else " (no workbook today)"))

# ---- Brent (US EIA) and AUD/USD (RBA) from fetch.py pull_macro, in place of FRED. Each file
# holds the full history from 2018-06, so it replaces store/fred.csv outright and no FRED values are kept. The file
# name and the FRED-id column names stay, so model.py is unchanged.
# EIA's history files only gain their rows on Wednesdays (US); its daily prices page (fetch.py pull_eia_daily) has the
# previous close each US weekday. The page shows one day, so its readings are kept in store/eia_daily.csv, and fill
# Brent and ULSD_NYH for the days after each column's last value in the weekly file. The weekly file wins where it has one.
fpath, epath = f"{STORE}/fred.csv", f"{STORE}/eia_daily.csv"
er = newest("brent_audusd_eia_rba*.csv"); pg = newest("eia_daily_page*.csv")
Fr = None
if er:
    Fr = pd.read_csv(er, parse_dates=["date"]).set_index("date")
    Fr = Fr[[c for c in ["DCOILBRENTEU", "DEXUSAL", "ULSD_NYH"] if c in Fr]].sort_index()   # ULSD_NYH: diesel crack, optional
elif pg and os.path.exists(fpath):
    try:
        Fr = pd.read_csv(fpath, parse_dates=["date"]).set_index("date")  # no weekly file today: the stored one stands in
        if Fr.empty or not {"DCOILBRENTEU", "DEXUSAL"} <= set(Fr.columns): Fr = None
    except Exception:
        Fr = None         # damaged: leave it for the next weekly file, as before
if Fr is not None:
    try:
        Ed = pd.read_csv(epath, parse_dates=["date"]).set_index("date") if os.path.exists(epath) else None
        if pg:
            one = pd.read_csv(pg, parse_dates=["date"]).set_index("date")[["DCOILBRENTEU", "ULSD_NYH"]]
            # the new reading wins cell by cell: a later one with diesel blank doesn't erase an earlier diesel value
            Ed = one if Ed is None or Ed.empty else one.combine_first(Ed[~Ed.index.duplicated(keep="last")])
            Ed = Ed[["DCOILBRENTEU", "ULSD_NYH"]].sort_index().tail(60)          # two months is plenty: the files catch up weekly
            Ed.to_csv(epath, index_label="date")
        filled = []
        for col in ["DCOILBRENTEU", "ULSD_NYH"]:
            if col not in Fr or not Fr[col].notna().any(): continue
            last = Fr[col].last_valid_index(); ref = Fr[col].loc[last]
            for d, v in ([] if Ed is None else Ed[col].dropna()[lambda q: q.index > last].items()):
                # a misread cell would show as a jump. Since 2018 Brent has moved over 35% in a day three times, all in April 2020
                # (under US$25); a real move that large is only held back until the weekly file has it
                if abs(v / ref - 1) > 0.35: log.append(f"eia page {col} {d.date()} ignored ({v:g} vs {ref:g})"); break
                Fr.loc[d, col] = v; ref = v; filled.append(d)
        Fr = Fr.sort_index()
        if filled: log.append(f"eia daily page filled to {max(filled).date()}")
    except Exception as e:
        log.append(f"eia daily page skipped ({type(e).__name__}: {str(e)[:120]})")
    Fr.to_csv(fpath, index_label="date")
    log.append(f"brent/aud (EIA/RBA) to {Fr[['DCOILBRENTEU', 'DEXUSAL']].dropna().index.max().date()}")

print("; ".join(log) or "nothing in inbox")
