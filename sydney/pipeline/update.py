"""Daily: fold the latest raw pulls in inbox/ into the store.

inbox/ may contain (any subset; newest of each is used):
  nsw_snapshot_*.json   raw response of GET /FuelPriceCheck/v1/fuel/prices
  AIP_TGP_Data_*.xlsx   AIP historical TGP workbook
  aip_tgp_page.html     AIP's daily TGP page (aip_daily.py): fills the days after the weekly workbook's last
  brent_audusd_eia_rba.csv  Brent (EIA) and AUD/USD (RBA), under the FRED column ids (fetch.py pull_macro)
Writes store/daily.csv (adds/replaces snapshot rows; Sydney stations only), store/tgp.csv, store/tgp_daily.csv, store/fred.csv and
store/stations_today.json (every NSW FuelCheck station, with `syd` true for the Sydney ones the forecast is about)
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
    """Sydney stations, Sydney prices, the date and one daily row per fuel (Sydney prices only: the model's input)
    from a raw (or archived) NSW snapshot; then the prices of every station in the feed, Sydney or not (`syd`), for
    the station list."""
    st = pd.DataFrame(j["stations"]); pr = pd.DataFrame(j["prices"])
    addr = st.address.astype(str)
    # Sydney is decided exactly as before ("NSW <postcode>" at the end of the address, postcode in is_syd), so the
    # daily rows don't change. Stations elsewhere also take a looser reading (any state, e.g. "ACT 2600").
    pc = pd.to_numeric(addr.str.extract(r"NSW\s+(\d{4})\s*$")[0], errors="coerce")
    st["syd"] = pc.fillna(0).astype(int).map(is_syd).astype(bool)
    st["postcode"] = pc.fillna(pd.to_numeric(addr.str.extract(r"\b[A-Za-z]{2,3}\s+(\d{4})\s*$")[0], errors="coerce"))
    st["suburb"] = addr.str.extract(r",\s*([^,]+?)\s+NSW\s+\d{4}\s*$")[0].fillna(
        addr.str.extract(r",\s*([^,]+?)\s+[A-Za-z]{2,3}\s+\d{4}\s*$")[0]).str.title()
    pr["code"] = pr.stationcode.astype(str); st["code"] = st.code.astype(str)
    # Station codes become file names downstream (station_api.py, export_api.py): keep NSW's numeric codes only
    pr = pr[pr.code.str.fullmatch(r"\d+")]; st = st[st.code.str.fullmatch(r"\d+")]
    st["key"] = st.address.str.upper().str.replace(",", " ").str.replace(r"\s+", " ", regex=True).str.strip()
    pr = pr.merge(st[["code", "name", "brand", "postcode", "suburb", "location", "key", "syd"]], on="code")
    pr = pr[pr.fueltype.isin(FUELS) & pr.price.between(50, 600)].copy()
    pr["ts"] = pd.to_datetime(pr.lastupdated, dayfirst=True, errors="coerce")
    asof = pd.Timestamp(re.search(r"(\d{8})", os.path.basename(snap)).group(1)) if re.search(r"(\d{8})", os.path.basename(snap)) else pr[pr.syd].ts.max().normalize()
    pr["age"] = (asof - pr.ts.dt.normalize()).dt.days
    allpr = pr; st, pr = st[st.syd], pr[pr.syd].drop(columns="syd")
    rows = []
    for f, g in pr.groupby("fueltype"):
        a = g.price.values; rec, old = g[g.age <= 2].price, g[g.age > 7].price
        rows.append(dict(date=asof.date(), fuel=f, n=len(a), median=np.median(a), mean=a.mean(),
                         p10=np.percentile(a, 10), p25=np.percentile(a, 25), p75=np.percentile(a, 75),
                         p90=np.percentile(a, 90), hikes=np.nan, cuts=np.nan,
                         share_upd_1d=(g.age <= 1).mean(), share_upd_3d=(g.age <= 3).mean(), share_upd_7d=(g.age <= 7).mean(),
                         recent_minus_old=(rec.median() - old.median()) if len(rec) > 5 and len(old) > 5 else np.nan,
                         source="snapshot"))
    return st, pr, asof, rows, allpr


snap = newest("nsw_snapshot_*.json")
if snap:
    j = json.load(open(snap))
    st, pr, asof, rows, allpr = snapshot_rows(j, snap)
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
    # Today's station list: every station in the feed. Sydney's rows come first and are the same rows as before.
    allpr = pd.concat([allpr[allpr.syd], allpr[~allpr.syd]]).copy()
    loc = lambda k: allpr.location.map(lambda l: l.get(k) if isinstance(l, dict) else None)
    allpr["lat"] = loc("latitude"); allpr["lon"] = loc("longitude")
    keep = allpr[["code", "key", "name", "brand", "postcode", "suburb", "lat", "lon", "fueltype", "price", "age", "syd"]]
    json.dump({"asof": str(asof.date()), "rows": keep.to_dict(orient="records")}, open(f"{STORE}/stations_today.json", "w"))
    # station-level archive: today's stations and prices (all of NSW since 2026-11-13, Sydney only before), gzipped,
    # kept in the repo. A station outside Sydney has no other price history: station_api.py builds its chart from these.
    os.makedirs(f"{BASE}/archive", exist_ok=True)
    codes = {str(s["code"]) for s in j["stations"] if re.fullmatch(r"\d+", str(s.get("code")))}
    with gzip.open(f"{BASE}/archive/nsw_snapshot_{asof:%Y%m%d}.json.gz", "wt") as fh:
        json.dump({"stations": [s for s in j["stations"] if str(s["code"]) in codes],
                   "prices": [p for p in j["prices"] if str(p["stationcode"]) in codes]}, fh)
    log.append(f"snapshot {asof.date()}: {len(pr)} Sydney prices, {len(allpr) - len(pr)} elsewhere in NSW "
               f"({allpr.code.nunique()} stations in all)")

# ---- AIP TGP
x = newest("AIP_TGP_Data_*.xlsx")
if x:
    out = {}
    for sheet, col in [("Petrol TGP", "tgp_ulp"), ("Diesel TGP", "tgp_dl")]:
        s = pd.read_excel(x, sheet_name=sheet, header=0)
        s = s.iloc[:, :2]; s.columns = ["date", col]
        s["date"] = pd.to_datetime(s.date, errors="coerce"); out[col] = s.dropna().set_index("date")[col]
    T = pd.concat(out, axis=1).sort_index()
    T.to_csv(f"{STORE}/tgp.csv", index_label="date")
    log.append(f"tgp to {T.index.max().date()}")

# ---- AIP daily page: Sydney TGP for the days the weekly workbook doesn't have yet. Every page read is kept in
# store/tgp_daily.csv (newest read wins); tgp.csv gets only the days after its last date, so the workbook always wins.
# Without a workbook this run, tgp.csv is last run's, and only days after its last date are added.
import aip_daily
dpath, page = f"{STORE}/tgp_daily.csv", f"{INBOX}/aip_tgp_page.html"
Dd = pd.DataFrame(columns=["tgp_ulp", "tgp_dl"])
if os.path.exists(page):
    try:
        if os.path.exists(dpath): Dd = pd.read_csv(dpath, parse_dates=["date"]).set_index("date")[["tgp_ulp", "tgp_dl"]].dropna()
        new = aip_daily.parse(open(page, encoding="utf-8").read())
        Dd = new.combine_first(Dd).sort_index() if len(Dd) else new
        Dd.to_csv(dpath, index_label="date")
    except Exception as e:   # a changed page must not stop the run: the workbook is still there. export_api warns
        log.append(f"aip daily: FAILED {type(e).__name__}: {str(e)[:120]}")   # (tgp_last) once TGP is 6+ days old
if len(Dd) and os.path.exists(f"{STORE}/tgp.csv"):
    T0 = pd.read_csv(f"{STORE}/tgp.csv", parse_dates=["date"]).set_index("date")
    T1 = aip_daily.merge(T0, Dd)
    if len(T1) > len(T0):
        T1.to_csv(f"{STORE}/tgp.csv", index_label="date")
        log.append(f"tgp to {T1.index.max().date()} with the AIP daily page")

# ---- Brent (US EIA) and AUD/USD (RBA) from fetch.py pull_macro, in place of FRED. Each file
# holds the full history from 2018-06, so it replaces store/fred.csv outright and no FRED values are kept. The file
# name and the FRED-id column names stay, so model.py is unchanged.
er = newest("brent_audusd_eia_rba*.csv")
if er:
    Fr = pd.read_csv(er, parse_dates=["date"]).set_index("date")
    Fr = Fr[[c for c in ["DCOILBRENTEU", "DEXUSAL", "ULSD_NYH"] if c in Fr]].sort_index()   # ULSD_NYH: diesel crack, optional
    Fr.to_csv(f"{STORE}/fred.csv", index_label="date")
    log.append(f"brent/aud (EIA/RBA) to {Fr[['DCOILBRENTEU', 'DEXUSAL']].dropna().index.max().date()}")

print("; ".join(log) or "nothing in inbox")
