"""Search pages: plain HTML that a search engine can read without running the dashboard's script.

Called from export_api.py with the dicts it has just published (stations.json, forecast.json, history.json, track.json
and the per-station files), so every number here is one the API also carries. Standard library only, no pandas: the
tests (test_seo_pages.py) run it on small made-up dicts. docs/SEO.md has the keyword map and the launch checklist.

  OUT/fuel-prices/                    hub: Sydney prices by fuel, the cheapest stations, every suburb A-Z
  OUT/fuel-prices/{fuel}/             one per fuel (unleaded-91, e10, premium-95, premium-98, diesel)
  OUT/fuel-prices/{suburb}-{pc}/      one per suburb: its stations, the cheapest nearby, fill or wait
  OUT/fuel-prices/{region}/           one per regional centre outside Sydney (REGIONS): prices only, no forecast
  OUT/station/                        every station, by suburb
  OUT/station/{name}-{id}/            one per station: prices, 90-day history, forecast, nearby alternatives
  OUT/brands/, OUT/brands/{brand}/    brands with 3+ stations
  OUT/fuel-price-forecast/            guide: this week's outlook and how the forecast is made and tested
  OUT/fuel-price-forecast/accuracy/   the forecast's track record: replayed and live calls, error against "no change"
  OUT/petrol-price-cycle/             guide: the Sydney price cycle, where it is now, the recent jumps
  OUT/best-day-to-buy-petrol/         guide: the weekday myth with Bowser's own numbers, and what to watch instead
  OUT/petrol-prices-christmas/        guide: what Sydney prices did over each Christmas since 2019, and this year's outlook
  OUT/petrol-deals-sydney/            guide: fuel discounts (DEALS) beside today's price at the stations that take them
  OUT/7-eleven-fuel-price-lock/       guide: whether to lock today (the forecast), how the lock works, today's 7-Eleven prices
  OUT/woolworths-fuel-discount/, OUT/coles-fuel-docket/   a supermarket docket each: where it works, today's prices before and after
  OUT/nsw-fuelcheck/                  guide: what NSW FuelCheck is and how Bowser uses it
  OUT/about/, OUT/privacy/            who runs the site, what is counted
  OUT/404.html, OUT/robots.txt, OUT/sitemap.xml, OUT/llms.txt (a plain summary for AI assistants)

Links between pages are relative (../), so the site also works under a sub-path; canonical, Open Graph and sitemap
addresses use SITE. Each page carries a hash Content-Security-Policy for its one style block and one script (the
anonymous visit counter, the same rule as share.html). Wholesale (AIP) figures are left out on purpose: see DATA-LICENSE.md.
A station outside Sydney (`out: 1`: the rest of NSW and the ACT) gets its prices but no forecast wording, and its price counts
as current for longer (OUT_STALE: prices there change less often).
"""
import base64, datetime as dt, hashlib, html, json, math, os, re, shutil, statistics

SITE = "https://checkbowser.app"
FUELS = ["U91", "E10", "P95", "P98", "DL"]          # fuels.py order; the pages' own copy so this file has no imports
NAME = {"U91": "Unleaded 91", "E10": "E10", "P95": "Premium 95", "P98": "Premium 98", "DL": "Diesel"}
WCALL = {"up": "fill now", "down": "wait", "flat": "no rush"}   # the call types, as the accuracy page says them
SHORT = {"U91": "U91", "E10": "E10", "P95": "95", "P98": "98", "DL": "Diesel"}
FSLUG = {"U91": "unleaded-91", "E10": "e10", "P95": "premium-95", "P98": "premium-98", "DL": "diesel"}
TONE = {"now": "act", "by": "act", "wait": "wait", "hi": "wait", "up": "act", "down": "wait"}   # anything else: calm
OWN = ["fuel-prices", "station", "brands", "fuel-price-forecast", "petrol-price-cycle", "best-day-to-buy-petrol", "petrol-prices-christmas",
       "petrol-deals-sydney", "7-eleven-fuel-price-lock", "woolworths-fuel-discount", "coles-fuel-docket", "nsw-fuelcheck", "about", "privacy", "badge"]
DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
STATIC = ["favicon.svg", "apple-touch-icon.png", "og.png"]
TANK = 50                                           # litres, for "a fill costs"
NEAR_KM, STALE = 5.0, 7                             # "nearby" radius; a price older than this many days is flagged
# Outside Sydney (`out`) prices change less often (no weekly cycle; Canberra's can sit for weeks), so a price there is
# flagged, and left out of top lists, only from day 21. The same rule as build.py, template.html and the app (2026-11-24).
OUT_STALE = 20
BRAND_MIN = 3
DEAD = 30                                           # every price older than this: the page stays, but out of search (noindex)
PUBLISHED = "2026-11-17"                            # when the guides first went up (Article datePublished)
# IndexNow (Bing, Yandex, Seznam, Naver; Bing feeds ChatGPT search and Copilot): the key is public by design, served at
# /{key}.txt to prove the site is ours. indexnow.py submits the pages whose sitemap date changed after each deploy.
JUMP_LIKELY = 0.35                                  # U91 p_jump7 from which the cycle stage is "A jump looks likely soon"
INDEXNOW_KEY = "e102a05131cbd86e3a6af62c8547639e"
LOCAL_KM = 25                                       # "nearby" for a station outside Sydney and its regions: its local median
# On the day of a cycle jump (8c+), the share of Sydney stations that had raised their price by each time of day, 2025-26.
# From the analysis behind daily.yml's run times (its schedule comment); refresh both together.
JUMP_BY_TIME = [("6 am", 0.07), ("noon", 0.55), ("6 pm", 0.89)]
# Fuel discounts on /petrol-deals-sydney/ and their own pages, each from the program's own terms page (`terms`). Offers
# change: re-check each against its terms every few months and update `checked` (docs/SEO.md). `brands`: the feed's brand
# names (stations.json `b`) whose Sydney stations take it; `cut`: c/L off, None when it isn't a fixed discount; `fuel`: the
# fuel the hub compares on; `until`: the last day it runs (the offer disappears after it); `page`: its own page, if any.
DEALS = [
    dict(key="woolworths", name="Woolworths Everyday Rewards docket", brands=["Ampol Foodary", "EG Ampol", "U-Go"], cut=4, page="woolworths-fuel-discount/",
         how="Spend $30 or more in one shop at Woolworths, then scan your Everyday Rewards card at a participating Ampol Foodary, EG Ampol or U-GO site within 28 days. "
             "Up to 150 L, though Woolworths’ U-GO page says the first 75 L at U-GO.",
         terms="https://www.everydayrewards.com.au/terms", checked="2026-11-22"),
    dict(key="coles", name="Coles docket (Flybuys)", brands=["Reddy Express"], cut=4, page="coles-fuel-docket/",
         how="Spend $30 or more in one shop at Coles. The docket is in the Flybuys app, lasts 4 weeks and covers up to 150 L at participating Shell Reddy Express sites.",
         terms="https://reddyexpress.com.au/terms-and-conditions/coles-supermarkets-fuel-docket-discount", checked="2026-11-22"),
    dict(key="reddy", name="Reddy Express in-store offer", brands=["Reddy Express"], cut=10, page="coles-fuel-docket/",
         how="Spend $20 or more in the Shell Reddy Express shop (not on fuel, tobacco, gift cards or lottery) in the same transaction as your fuel, up to 150 L. "
             "Its terms say it’s valid with the Coles docket: 4c plus 10c a litre.",
         terms="https://www.reddyexpress.com.au/terms-and-conditions/spend-20-get-10-cents-per-litre-fuel-discount", checked="2026-11-22"),
    dict(key="nrma", name="NRMA member discount", brands=["Ampol Foodary"], cut=4,
         how="Show the My NRMA app at participating Ampol Foodary sites (not EG Ampol): 4c a litre on regular fuels and 5c on premium, up to 150 L, once every 24 hours. "
             "NRMA says it combines with the Woolworths docket.",
         terms="https://www.mynrma.com.au/benefits/ampol", checked="2026-11-22"),
    dict(key="lock", name="7-Eleven Fuel Price Lock", brands=["7-Eleven"], cut=None, page="7-eleven-fuel-price-lock/",
         how="In the My 7-Eleven app, lock the lowest price at nearby 7-Elevens for 7 days, up to 150 L, with the saving capped at 25c a litre. "
             "If the pump price is lower when you fill, you pay that. One lock at a time, no fee.",
         terms="https://www.7eleven.com.au/fuel-price-lock-terms", checked="2026-11-22"),
    dict(key="codes", name="7-Eleven partner codes", brands=["7-Eleven"], cut=6,
         how="Some businesses give their customers a 6c a litre barcode for 7-Eleven. Linkt’s, for example, covers up to 120 L, twice in 24 hours, "
             "and can’t be used with the Fuel Price Lock. Other partners’ limits differ: check yours.",
         terms="https://www.linkt.com.au/legal/rewards/7-eleven", checked="2026-11-22"),
    dict(key="yello", name="CommBank Yello at BP", brands=["BP"], cut=9, until="2026-12-31",
         how="Eligible CommBank Yello customers: 9c a litre at participating BP sites until 31 December 2026, depending on their Yello tier.",
         terms="https://www.commbank.com.au/articles/newsroom/2026/10/Yello_fuel_discount.html", checked="2026-11-22"),
    dict(key="seniors", name="NSW Seniors Card at United", brands=["United"], cut=4,
         how="NSW Seniors Card and Senior Savers Card holders: 4c a litre at participating United sites.",
         terms="https://www.unitedpetroleum.com.au/nsw-seniors/", checked="2026-11-22"),
    dict(key="costco", name="Costco fuel", brands=["Costco"], cut=None, fuel="E10", page="brands/costco/",
         how="No discount as such: Costco’s own pump prices, for members only (Gold Star membership is $65 a year). Sydney’s are at Auburn, Casula and Marsden Park, "
             "with another at Lake Macquarie; they sell E10 and Premium 98 but not Unleaded 91, so the table compares their E10.",
         terms="https://www.costco.com.au/fuel-station", checked="2026-11-22"),
]
COSTCO_FEE = 65                                     # dollars a year, Gold Star (costco.com.au/membership, checked 2026-11-22)

# Regional centres outside Sydney: a station joins the nearest one within its radius (km). Each gets a page.
REGIONS = [("Newcastle", -32.93, 151.75, 32), ("Central Coast", -33.36, 151.38, 28), ("Wollongong", -34.45, 150.87, 30),
           ("Southern Highlands", -34.48, 150.42, 18), ("Taree and Forster", -32.02, 152.48, 25), ("Lithgow", -33.48, 150.15, 12),
           ("Hunter Valley", -32.75, 151.45, 20), ("Canberra and Queanbeyan", -35.30, 149.13, 25), ("Coffs Harbour", -30.30, 153.11, 20),
           ("Port Macquarie", -31.43, 152.91, 20), ("Northern Rivers", -28.81, 153.35, 35), ("Tweed Heads", -28.20, 153.53, 25),
           ("Tamworth", -31.09, 150.93, 20), ("Armidale", -30.51, 151.67, 15), ("Wagga Wagga", -35.12, 147.37, 20), ("Albury", -36.07, 146.92, 20),
           ("Dubbo", -32.25, 148.60, 20), ("Orange", -33.28, 149.10, 20), ("Bathurst", -33.42, 149.58, 20), ("Nowra and Shoalhaven", -34.88, 150.60, 22),
           ("Goulburn", -34.75, 149.72, 15), ("Griffith", -34.29, 146.05, 15), ("Broken Hill", -31.95, 141.45, 15)]
REGION_MIN = 5
# The one page that owns "canberra petrol prices" (docs/MARKETING_NSW_ACT.md A2): the Canberra and Queanbeyan region,
# kept at its address since 17 Nov. Its title leads with the name people search ("Canberra"); its H1 keeps the full name.
CANBERRA = "Canberra and Queanbeyan"
REGION_TITLE = {CANBERRA: "Canberra"}
# Canberra districts by postcode, for the Canberra page's district sections (ACT stations only; the NSW side of the
# region is "Queanbeyan and surrounds"). Hume ACT shares 2620 with Queanbeyan and sits with Fyshwick in the
# Jerrabomberra district, so it joins Fyshwick. Not regions: a station keeps its Canberra region and median.
DISTRICTS = [("Belconnen", (2614, 2615, 2616, 2617, 2618)), ("Gungahlin", (2911, 2912, 2913, 2914)), ("Inner North", (2601, 2602, 2612)),
             ("Inner South", (2600, 2603, 2604)), ("Fyshwick, Hume and the airport", (2609, 2620)), ("Woden", (2605, 2606, 2607)),
             ("Weston Creek and Molonglo", (2611,)), ("Tuggeranong", (2900, 2901, 2902, 2903, 2904, 2905, 2906))]
NSW_SIDE, ACT_OTHER = "Queanbeyan and surrounds (NSW)", "Elsewhere in the ACT"
NO_CBR_FORECAST = ("No. Bowser’s forecast is built on Sydney prices and covers Sydney only. For Canberra, Bowser shows today’s prices "
                   "so you can compare stations.")
STATES = [{"@type": "State", "name": "New South Wales"}, {"@type": "State", "name": "Australian Capital Territory"}]   # schema.org areaServed
# Crawlers named so their owners' own "is this site open to us" checks pass; the rules are the same for everyone.
AI_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User", "PerplexityBot", "Perplexity-User",
           "Google-Extended", "Applebot-Extended", "Amazonbot", "meta-externalagent", "CCBot", "Bingbot", "DuckAssistBot"]
def state_of(pc, st=None):
    """The state for a postcode: the address's own state (stations.json `st`, given when it isn't NSW) when known, else
    by postcode range. 2620 is NSW by range (Queanbeyan shares it with Hume ACT), so Hume needs `st`."""
    if st in ("ACT", "NSW", "VIC", "QLD", "SA"): return st
    return "ACT" if isinstance(pc, int) and (2600 <= pc <= 2618 or 2900 <= pc <= 2920) else "NSW"
# The privacy and support address shown on /privacy/ and /about/ (Google Play requires a contact in the privacy policy).
# The owner's choice (2026-11-18). No page links to the code repository: the owner wants the source kept private.
CONTACT_EMAIL = "checkbowser@gmail.com"
CONTACT = f'<a href="mailto:{html.escape(CONTACT_EMAIL, quote=True)}">{html.escape(CONTACT_EMAIL)}</a>'

esc = lambda v: html.escape(str(v), quote=True)
lc = lambda s: s[:1].lower() + s[1:]                # "The Sydney median…" inside a sentence
num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v
c1 = lambda v: f"{v:.1f}"
pct0 = lambda x: f"{math.floor(x * 100 + 0.5):.0f}%"   # as the app's Math.round: a .5 rounds up (Python's :.0% rounds to even)
def isodate(s):
    try: dt.date.fromisoformat(s); return True
    except (TypeError, ValueError): return False
cents = lambda v: f"{abs(v):.1f}c" if abs(v) < 10 else f"{abs(v):.0f}c"


def slug(s):
    """Lower-case words joined by hyphens, at most 80 characters (it becomes a folder name)."""
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower().replace("&", " and ").replace("'", "").replace("’", "")).strip("-")[:80].strip("-")


def clip(text, n=158):
    """A description cut at a word to fit a search result (about 160 characters)."""
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[:n - 1].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


ACRONYMS = {"BP", "EG", "APW", "NRMA", "NSW", "LPG", "RD", "ST", "MT", "CVRO", "IGA", "U-GO"}
def station_name(n):
    """As title() in share.html and stationName() in the app: an ALL-CAPS name in title case, known acronyms kept."""
    n = re.sub(r"\s+", " ", re.sub(r"\s*\(members only\)", "", str(n), flags=re.I)).strip()
    if re.search(r"[a-z]", n) or not re.search(r"[A-Z]{4}", n): return n
    # a capital after - or (, and after an apostrophe only in O'Connell-style names (not "Yogi's")
    cap = lambda w: re.sub(r"^([A-Z]['’])([a-z])", lambda m: m.group(1) + m.group(2).upper(),
                           re.sub(r"(^|[-(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), w.lower()))
    return " ".join(w if w in ACRONYMS else cap(w) for w in n.split(" "))


brand_name = lambda b: re.sub(r"\s+logo$", "", str(b or "Independent"), flags=re.I).strip() or "Independent"


def long_date(iso):
    d = dt.date.fromisoformat(iso); return f"{d.strftime('%A')} {d.day} {d.strftime('%B %Y')}"
def short_date(iso):
    d = dt.date.fromisoformat(iso); return f"{d.day} {d.strftime('%b')}"


def km(a, b):
    """Distance between two (lat, lon) points; flat-earth is within a few metres at these ranges."""
    x = math.radians(b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2)); y = math.radians(b[0] - a[0])
    return 6371.0 * math.hypot(x, y)


def clean_suburbs(stations):
    """{station id: (suburb, postcode) or None}. FuelCheck's suburb field sometimes holds part of the address
    ("1190 Miami Street Glenwood"): such a name becomes the known suburb it ends with. A station with no usable
    suburb ("Postcode 2143") gets None: it has its own page but no suburb page."""
    odd = lambda s: bool(re.search(r"\d", s)) or s.strip().lower() in ("", "nsw", "act")
    known = sorted({re.sub(r"\s+", " ", s["s"]).strip() for s in stations if isinstance(s.get("s"), str) and not odd(s["s"])},
                   key=len, reverse=True)
    out = {}
    for s in stations:
        raw = re.sub(r"\s+", " ", str(s.get("s") or "")).strip(); pc = s.get("pc")
        if not isinstance(pc, int) or not 1000 <= pc <= 9999: out[s.get("id")] = None; continue
        if odd(raw):
            raw = next((k for k in known if re.search(r"(^|\s)" + re.escape(k) + r"$", raw, flags=re.I)), "")
        out[s.get("id")] = (raw, pc) if raw else None
    return out


def usable(s):
    """A station the pages can show: a numeric id, coordinates and at least one price. Returns its prices, or None."""
    if not isinstance(s, dict) or not re.fullmatch(r"\d{1,12}", str(s.get("id") or "")) or not (num(s.get("la")) and num(s.get("lo"))): return None
    p = {}
    for f, v in (s.get("p") or {}).items():
        if f in FUELS and isinstance(v, list) and len(v) >= 5 and num(v[0]):
            p[f] = [v[0], v[1] if num(v[1]) else None, str(v[2] or ""), str(v[3] or ""), str(v[4] or "")] + list(v[5:])
    # Premium diesel (PDL, fuels.py): where a station lists no regular diesel, its premium diesel is its diesel (as in
    # the app and on the dashboard). 7-Eleven, most BP, Metro and Ampol Foodary list only PDL. premium() names it.
    v = (s.get("p") or {}).get("PDL")
    if "DL" not in p and isinstance(v, list) and len(v) >= 5 and num(v[0]):
        p["DL"] = [v[0], v[1] if num(v[1]) else None, str(v[2] or ""), str(v[3] or ""), str(v[4] or "")] + list(v[5:])
    return p or None


def premium(s):
    """Whether the station's diesel on the pages is premium diesel (usable() moved it there). From the raw row."""
    raw = s.get("p") or {}
    return "PDL" in raw and not (isinstance(raw.get("DL"), list) and raw["DL"] and num(raw["DL"][0]))


# ---- the look: the dashboard's tokens (template.html), one style block shared by every page
CSS = """:root{--bg:#f7f5f0;--surface:#fff;--sunk:#efece5;--line:#e3dfd6;--fg:#141618;--fg2:#44474b;--muted:#686b6f;--link:#8a5a00;--focus:#141618;--chip:#ffb22e;--cheap:#0f7a52;--dear:#b4461a;--retail:#b87800;--median:#868a8e;--band:rgba(255,178,46,.22);--act-bg:#ffb22e;--act-fg:#141618;--wait-bg:#141618;--wait-fg:#f4f1ea;--calm-bg:#efece5;--calm-fg:#33373a;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#141618;--surface:#1d2023;--sunk:#191b1e;--line:#2e3236;--fg:#f4f1ea;--fg2:#c9c4ba;--muted:#9a958c;--link:#ffb22e;--focus:#ffb22e;--cheap:#3cc28f;--dear:#f08a5d;--retail:#ffb22e;--median:#9a958c;--band:rgba(255,178,46,.16);--act-bg:#2a2112;--act-fg:#ffcf7a;--wait-bg:#23272b;--wait-fg:#f4f1ea;--calm-bg:#1d2023;--calm-fg:#c9c4ba}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg2);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--link)}a:hover{text-decoration-thickness:2px}:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
h1,h2,h3{color:var(--fg);margin:0;text-wrap:balance}h1{font-size:30px;line-height:1.15;letter-spacing:-.5px}h2{font-size:21px;letter-spacing:-.2px;margin-top:8px}h3{font-size:16px}
p{margin:0;max-width:72ch}ul{margin:0;padding-left:20px;max-width:72ch}li{margin:4px 0}
.wrap{max-width:960px;margin:0 auto;padding:16px 16px 56px;display:flex;flex-direction:column;gap:20px}main{display:flex;flex-direction:column;gap:16px;min-width:0}.wrap>*,main>*{min-width:0;max-width:100%}body{overflow-wrap:break-word}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.logo{display:flex;align-items:center;gap:8px;font-weight:800;font-size:22px;color:var(--fg);text-decoration:none;letter-spacing:-.3px}.logo svg{width:24px;height:24px}
nav{display:flex;gap:4px 16px;flex-wrap:wrap;font-size:14px;font-weight:600}nav a{text-decoration:none}nav a:hover{text-decoration:underline}
.crumbs{font-size:13px;color:var(--muted)}.crumbs a{color:var(--muted)}
.lead{font-size:18px;color:var(--fg)}.badge img{max-width:100%;height:auto}pre{white-space:pre-wrap;word-break:break-all;background:var(--sunk);border:1px solid var(--line);border-radius:8px;padding:12px;font-size:13px;line-height:1.5}code{font-size:13px;word-break:break-all}.small{font-size:13px;line-height:1.45;color:var(--muted)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:16px;display:flex;flex-direction:column;gap:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
.eyebrow{font-size:11px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--muted)}
.big{font-size:30px;font-weight:800;color:var(--fg);letter-spacing:-.6px;line-height:1.05;font-variant-numeric:tabular-nums}.big small{font-size:13px;font-weight:600;color:var(--muted);letter-spacing:0;margin-left:3px}
.chip{display:inline-block;border-radius:999px;padding:2px 10px;font-size:13px;font-weight:700;white-space:nowrap}
.card .chip{align-self:flex-start}a.card{text-decoration:none;color:inherit}.act{background:var(--act-bg);color:var(--act-fg)}.wait{background:var(--wait-bg);color:var(--wait-fg)}.calm{background:var(--calm-bg);color:var(--calm-fg)}
.verdict{border-radius:16px;padding:16px;display:flex;flex-direction:column;gap:6px}.verdict b{font-size:22px;letter-spacing:-.3px}
.cheap{color:var(--cheap);font-weight:700}.dear{color:var(--dear);font-weight:700}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:16px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}tr:last-child td{border-bottom:0}
th{font-size:11px;letter-spacing:.6px;text-transform:uppercase;color:var(--muted);white-space:nowrap}
td.n,th.n{text-align:right;white-space:nowrap}td.best{color:var(--cheap);font-weight:800}td.old{color:var(--muted)}td a{font-weight:600}
.cols{columns:3 180px;column-gap:24px;padding:0;list-style:none;max-width:none}.cols li{break-inside:avoid;margin:0 0 6px;font-size:14px}
.az{display:flex;flex-wrap:wrap;gap:6px;font-weight:700}.az a{padding:2px 8px;border-radius:8px;background:var(--sunk);text-decoration:none}
.btn{display:inline-block;align-self:flex-start;background:var(--fg);color:var(--bg);font-weight:700;text-decoration:none;border-radius:12px;padding:10px 16px}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
svg.chart{width:100%;height:auto;display:block}.chart .st{fill:none;stroke:var(--retail);stroke-width:2.5;stroke-linejoin:round}.chart .md{fill:none;stroke:var(--median);stroke-width:1.5;stroke-dasharray:4 4}.chart .bd{fill:var(--band);stroke:none}.chart .ax{stroke:var(--line);stroke-width:1}.chart text{fill:var(--muted);font-size:11px;font-family:inherit}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--muted)}.legend i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:6px;vertical-align:middle}.legend .a{background:var(--retail)}.legend .b{background:var(--median)}
footer{border-top:1px solid var(--line);padding-top:16px;display:flex;flex-direction:column;gap:10px;font-size:13px;line-height:1.45;color:var(--muted)}footer nav{font-weight:500}
@media (max-width:520px){h1{font-size:25px}.lead{font-size:16px}th,td{padding:8px}}"""

# The visit counter: the tracker in share.html, cut down to one pageview and the two link clicks (keep the rules in
# step: only on the published site, off with Global Privacy Control or Do Not Track, no cookie, no IP-derived place).
# The address sent is the page TYPE's pattern (data-pattern, "/fuel-prices/:suburb/"), never the suburb or station
# itself, so the footer's promise ("never your area") holds on these pages too.
JS = """(function () {
  'use strict';
  // Not inside another site's frame (clickjacking): the host can't send X-Frame-Options or frame-ancestors
  if (window.top !== window.self) { document.documentElement.style.display = 'none'; try { window.top.location.replace(location.href); } catch (e) {} }
  var on = false, id = null, internal = false, sess = null, root = document.documentElement;
  var get = function (k, d) { try { var v = localStorage.getItem('bowser.' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } };
  var set = function (k, v) { try { localStorage.setItem('bowser.' + k, JSON.stringify(v)); } catch (e) {} };
  var uuid7 = function () {
    var b = crypto.getRandomValues(new Uint8Array(16)), t = Date.now(), h = '', i;
    for (i = 5; i >= 0; i--) { b[i] = t % 256; t = Math.floor(t / 256); }
    b[6] = 0x70 | (b[6] & 15); b[8] = 0x80 | (b[8] & 63);
    for (i = 0; i < 16; i++) h += (b[i] < 16 ? '0' : '') + b[i].toString(16);
    return h.slice(0, 8) + '-' + h.slice(8, 12) + '-' + h.slice(12, 16) + '-' + h.slice(16, 20) + '-' + h.slice(20);
  };
  try {
    on = /^(www\\.)?checkbowser\\.app$/.test(location.hostname) && !navigator.globalPrivacyControl && navigator.doNotTrack !== '1' && navigator.doNotTrack !== 'yes' && window.doNotTrack !== '1' && !!window.fetch;
    internal = get('internal', false) === true;
    id = get('anon', null);
    if (typeof id !== 'string') { id = uuid7(); set('anon', id); }
  } catch (e) { on = false; }
  var track = function (event, props) {
    if (!on) return;
    try {
      var now = Date.now(), s = sess || get('session', null), p = props || {}, pat = root.getAttribute('data-pattern') || '/';
      sess = s && typeof s.id === 'string' && now - s.t < 30 * 60e3 ? { id: s.id, t: now } : { id: uuid7(), t: now };
      set('session', sess);
      p.page = root.getAttribute('data-page'); p.internal = internal; p.$lib = 'bowser-web'; p.$session_id = sess.id;
      p.$current_url = location.origin + pat; p.$host = location.host; p.$pathname = pat;
      p.$device_type = matchMedia('(pointer: coarse)').matches ? 'Mobile' : 'Desktop';
      p.$process_person_profile = false; p.$geoip_disable = true;
      fetch('https://us.i.posthog.com/i/v0/e/', {
        method: 'POST', headers: { 'Content-Type': 'text/plain' }, credentials: 'omit', keepalive: true,
        body: JSON.stringify({ api_key: 'phc_soNtCQQTfbqiWoJYeDCVp8dkd7xwbnr6n7rD6NSPEkXW', event: event, distinct_id: id, properties: p })
      }).catch(function () {});
    } catch (e) {}
  };
  var ref = null;
  try { ref = document.referrer ? new URL(document.referrer).hostname : null; } catch (e) {}
  track('$pageview', { $referring_domain: ref });
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[data-cta]') : null;
    if (a) track('seo.cta', { cta: a.getAttribute('data-cta') });
  });
  addEventListener('pagehide', function () { track('$pageleave'); }, { once: true });
})();"""

_h = lambda t: base64.b64encode(hashlib.sha256(t.encode()).digest()).decode()
CSP = (f"default-src 'none'; script-src 'sha256-{_h(JS)}'; style-src 'sha256-{_h(CSS)}'; img-src 'self' data:; "
       "connect-src https://us.i.posthog.com; base-uri 'none'; form-action 'none'; object-src 'none'")
MARK = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="9 9 82 82" aria-hidden="true"><path d="M50 10C58 22 78 40 78 62A28 28 0 0 1 22 62C22 40 42 22 '
        '50 10ZM45.5 42A4.5 4.5 0 0 1 54.5 42V63.14L59.82 57.82A4.5 4.5 0 0 1 66.18 64.18L53.18 77.18A4.5 4.5 0 0 1 46.82 77.18L33.82 '
        '64.18A4.5 4.5 0 0 1 40.18 57.82L45.5 63.14Z" fill="#F0A000" fill-rule="evenodd"/></svg>')
# The source is linked and the disclaimer is plain: Google Play's Misleading Claims policy asks the same of the app
# (app/src/lib/sources.ts), and the wording stays in step with it
SOURCES = ('Prices: <a href="https://www.fuelcheck.nsw.gov.au/" rel="noopener">NSW Government FuelCheck</a> (© State of New South Wales, '
           "NSW Fair Trading, CC BY-SA 3.0 AU), adapted, with forecasts added by Bowser. Bowser is independent, not a government "
           "service, and is not affiliated with the NSW Government or any fuel retailer.")


def jsonld(obj):
    """A JSON-LD block. "<" is escaped so a station name can't close the script element."""
    return '<script type="application/ld+json">' + json.dumps(obj, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c") + "</script>"


def chart(series, lo, hi, labels, alt, band=None):
    """A small line chart as inline SVG (no script). series: [(css class, [values or None])], all the same length;
    band: (low values, high values) drawn as a shaded range. Classes only: the CSP allows no style attributes."""
    W, H, L, R, T, B = 640, 200, 40, 8, 10, 22
    n = max(len(v) for _, v in series)
    if n < 2 or hi <= lo: return ""
    x = lambda i: L + (W - L - R) * i / (n - 1)
    y = lambda v: T + (H - T - B) * (hi - v) / (hi - lo)
    out = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(alt)}">']
    for v in (lo, (lo + hi) / 2, hi):
        out.append(f'<line class="ax" x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/><text x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v:.0f}</text>')
    if band:
        pts = [(i, a, b) for i, (a, b) in enumerate(zip(*band)) if num(a) and num(b)]
        if len(pts) > 1:
            out.append('<polygon class="bd" points="' + " ".join(f"{x(i):.1f},{y(b):.1f}" for i, _, b in pts) + " "
                       + " ".join(f"{x(i):.1f},{y(a):.1f}" for i, a, _ in reversed(pts)) + '"/>')
    for cls, vals in series:
        run = []
        for i, v in enumerate(list(vals) + [None]):      # a gap (None) ends the line; it restarts at the next price
            if num(v): run.append(f"{x(i):.1f},{y(v):.1f}")
            else:
                if len(run) > 1: out.append(f'<polyline class="{cls}" points="{" ".join(run)}"/>')
                run = []
    out.append(f'<text x="{L}" y="{H - 5}">{esc(labels[0])}</text><text x="{W - R}" y="{H - 5}" text-anchor="end">{esc(labels[1])}</text></svg>')
    return "".join(out)


def cycle_stage(stats, fc_asof, live):
    """Where Sydney is in its price cycle: (days since the last jump, the usual gap, a short label, its tone, a sentence), or
    None. The cycle page, the forecast page, the badge (badge_svg) and the news-pitch trigger (docs/OUTREACH.md) all use it."""
    S = stats or {}; last, gap = S.get("last_restore"), S.get("cycle_gap_calm")
    if not isinstance(last, str) or not num(gap) or gap <= 0: return None
    try: since = (dt.date.fromisoformat(fc_asof) - dt.date.fromisoformat(last)).days
    except (TypeError, ValueError): return None
    if since < 0: return None
    pj = ((live or {}).get("U91") or {}).get("p_jump7")
    quiet = num(pj) and pj < 0.2
    if num(pj) and pj >= JUMP_LIKELY:
        head, tone, txt = "A jump looks likely soon", "act", f"the forecast puts the chance of a 5c-plus jump within a week at about {pj:.0%}, so fill up before it comes"
    elif since <= 7:
        head, tone, txt = "Near the top", "act", "a jump has just happened, so prices are near the top of the cycle; buy as little as you can and wait for them to ease"
    elif since < 0.75 * gap:
        head, tone, txt = "Falling", "wait", "prices are in the slow slide that follows a jump, which usually rewards waiting"
    elif since <= 1.25 * gap:
        head, tone, txt = "Late in the cycle", "calm", "a jump is due by the usual timing" + (", but the forecast sees little sign of one this week" if quiet else "")
    else:
        head, tone, txt = "Running long", "calm", ("this cycle has lasted longer than usual" +
                                                   (", and the forecast still sees little sign of a jump this week" if quiet else ", so a jump could come at any time"))
    return since, gap, head, tone, txt


# ---- The embeddable badge (docs/OUTREACH.md): an image other sites show, linking to the cycle page. Its address never
# changes and never 404s: export_api.py writes it after the pages, apart from them, and writes BADGE_FALLBACK if it fails.
BADGE_PATH = "badge/sydney.svg"
BADGE_W, BADGE_H = 360, 104
BADGE_TONE = {"act": ("#ffb22e", "#141618", "#141618"), "wait": ("#141618", "#f4f1ea", "#ffb22e"), "calm": ("#efece5", "#33373a", "#7d8185")}   # brand tones (2026-11-24)
BADGE_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def _badge(head, line, tone, title):
    """The badge's SVG: fixed colours (it sits on other sites' pages, light or dark), system fonts, every text escaped,
    no script, no links, nothing fetched. A long head is narrowed to fit rather than run off the edge."""
    bg, fg, bar = BADGE_TONE.get(tone, BADGE_TONE["calm"])
    head, line, title = (re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(v)) for v in (head, line, title))   # not allowed in XML
    x, room = 66, BADGE_W - 66 - 12
    fs = 21
    while fs > 14 and len(head) * fs * 0.58 > room: fs -= 1
    fit = f' textLength="{room}" lengthAdjust="spacingAndGlyphs"' if len(head) * fs * 0.58 > room else ""
    mark = MARK.replace('viewBox="9 9 82 82" aria-hidden="true"', 'x="14" y="26" width="40" height="40" viewBox="9 9 82 82"')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{BADGE_W}" height="{BADGE_H}" viewBox="0 0 {BADGE_W} {BADGE_H}" role="img" aria-label="{esc(title)}">'
            f"<title>{esc(title)}</title>"
            f'<rect x=".5" y=".5" width="{BADGE_W - 1}" height="{BADGE_H - 1}" rx="10" fill="#ffffff" stroke="#e2e3df"/>'
            f'<rect x="1" y="1" width="6" height="{BADGE_H - 2}" rx="3" fill="{bar}"/>'
            f'<rect x="10" y="22" width="48" height="48" rx="10" fill="{bg}"/>{mark}'
            f'<g font-family="{BADGE_FONT}">'
            f'<text x="{x}" y="24" font-size="11" font-weight="600" letter-spacing=".6" fill="#6f7479">SYDNEY PETROL PRICE CYCLE</text>'
            f'<text x="{x}" y="50" font-size="{fs}" font-weight="700" fill="{fg}"{fit}>{esc(head)}</text>'
            f'<text x="{x}" y="70" font-size="12.5" fill="#45494d">{esc(line)}</text>'
            f'<text x="{x}" y="92" font-size="10.5" fill="#6f7479"><tspan font-weight="700" fill="#141618">Bowser</tspan> · checkbowser.app · Data: NSW FuelCheck</text>'
            "</g></svg>")


BADGE_FALLBACK = _badge("See today’s cycle stage", "Updated several times a day", "calm", "Sydney petrol price cycle, from Bowser")


def badge_svg(forecast):
    """Today's badge from forecast.json: the cycle stage (cycle_stage, as on the cycle page) and the day it is for, so a
    stalled feed shows its own age. Without a stage, Bowser's U91 call; without either, BADGE_FALLBACK."""
    live = {r["fuel"]: r for r in forecast.get("live") or [] if isinstance(r, dict) and r.get("fuel")}
    fa = forecast.get("asof")
    day = short_date(fa) if isinstance(fa, str) and fa else None
    st = cycle_stage(forecast.get("stats") if isinstance(forecast.get("stats"), dict) else {}, fa, live)
    if st and day:
        since, gap, head, tone, _ = st
        when = "A jump began today" if since == 0 else f"Day {since} since the last jump"
        return _badge(head, f"{when} · {day}", tone, f"Sydney petrol price cycle, {day}: {head}. {when}. From Bowser.")
    v = (live.get("U91") or {}).get("verdict") or {}
    if day and isinstance(v.get("head"), str) and v["head"].strip():
        head = v["head"].strip()
        if len(head) > 40: head = head[:39].rsplit(" ", 1)[0] + "…"
        return _badge(head, f"Bowser’s call for Unleaded 91 · {day}", TONE.get(v.get("cls"), "calm"), f"Bowser’s call for Sydney Unleaded 91, {day}: {head}.")
    return BADGE_FALLBACK


def write_badge(out, forecast):
    """Write OUT/badge/sydney.svg: today's badge, or BADGE_FALLBACK if anything about today's goes wrong. Never raises
    for bad data; returns True for today's, False for the fallback."""
    try: svg, ok = badge_svg(forecast), True
    except Exception as e:
        print(f"seo_pages: WARNING badge fallback: {type(e).__name__}: {e}")
        svg, ok = BADGE_FALLBACK, False
    dest = os.path.join(out, BADGE_PATH)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh: fh.write(svg)
    return ok and svg != BADGE_FALLBACK


class Site:
    def __init__(self, out, stations, forecast, history=None, details=None, track=None, site=SITE, weekly=None):
        self.out, self.site = out, site.rstrip("/")
        # weekly.py's scored snapshots, oldest first (none: no weekly pages)
        self.weeks = [w for w in (weekly or []) if isinstance(w, dict) and isodate(w.get("week")) and isodate(w.get("asof")) and isinstance(w.get("score"), dict) and w.get("live")]
        self.asof = stations["asof"]; self.day, self.sday = long_date(self.asof), short_date(self.asof)
        self.live = {r["fuel"]: r for r in forecast["live"]}
        self.stats, self.fc_asof = forecast.get("stats") or {}, forecast.get("asof") or self.asof
        self.history, self.details = history or {}, dict(details or {})   # a copy: premium diesel rewrites some entries below
        # track.json as track_api.py writes it; any other shape counts as no record rather than stopping the build
        self.track = {k: v for k, v in track.items() if isinstance(v, dict)} if isinstance(track, dict) else {}
        for part in ("replay", "live"):
            if part in self.track: self.track[part] = {f: v for f, v in self.track[part].items() if isinstance(v, dict)}
        self.bt = forecast.get("bt") if isinstance(forecast.get("bt"), dict) else {}
        # Pages that need data the feed may lack are built, and linked to, only when it is there
        dow = self.stats.get("dow")
        self.has_best = isinstance(dow, list) and len(dow) == 7 and all(num(x) for x in dow) and max(dow) > min(dow)
        sm = self.bt.get("summary") if isinstance(self.bt.get("summary"), dict) else {}
        rp = (self.track.get("replay") or {}).get("U91") if isinstance(self.track.get("replay"), dict) else None
        self.has_acc = bool((isinstance(rp, dict) and rp.get("n")) or isinstance(sm.get("U91|7"), dict))
        self.xmas = self.xmas_rows()
        self.urls = []                                    # (path, sitemap priority, lastmod)
        rows = [s for s in stations["stations"] if usable(s)]
        sub = clean_suburbs(rows)
        # Two spellings of one suburb or brand ("ST MARYS", "St Marys") are one page: the first spelling seen names it
        sub_name, brand_of = {}, {}
        self.st = []
        for s in rows:
            p = usable(s); name = station_name(s.get("n") or "Station") or "Station"
            k = sub.get(s["id"])
            if k: k = (sub_name.setdefault((slug(k[0]), k[1]), station_name(k[0])), k[1]) if slug(k[0]) else None
            b = brand_name(s.get("b")); b = brand_of.setdefault(slug(b) or "independent", b if slug(b) else "Independent")
            self.st.append(dict(s, id=str(s["id"]), name=name, brand=b, sub=k, p=p, pd=premium(s), s=str(s.get("s") or s.get("st") or "NSW"),
                                url=f"station/{slug(name) or 'station'}-{s['id']}/", main=next(f for f in FUELS if f in p)))
        # A station whose diesel is premium diesel: its file's chart and forecast for it are under PDL (new dicts: the
        # station files export_api.py writes are untouched)
        for s in self.st:
            d = self.details.get(s["id"])
            if s["pd"] and isinstance(d, dict):
                hist, fc = dict(d.get("hist") or {}), dict(d.get("fc") or {})
                hist.pop("DL", None); fc.pop("DL", None)
                if "PDL" in hist: hist["DL"] = hist["PDL"]
                if "PDL" in fc: fc["DL"] = fc["PDL"]
                self.details[s["id"]] = dict(d, hist=hist, fc=fc)
        # A name two stations share ("7-Eleven Blacktown") gets its street in titles, so no two pages have the same title
        seen = {}
        for s in self.st: seen[s["name"].lower()] = seen.get(s["name"].lower(), 0) + 1
        for s in self.st:
            a = (self.details.get(s["id"]) or {}).get("addr")
            street = re.sub(r"^[\d\s/&-]+", "", a.split(",")[0]).strip() if isinstance(a, str) and a.strip() else ""
            s["label"] = s["name"] if seen[s["name"].lower()] == 1 else f"{s['name']} ({street or 'no. ' + s['id']})"
        dup = {}
        for s in self.st: dup[s["label"].lower()] = dup.get(s["label"].lower(), 0) + 1
        for s in self.st:
            if dup[s["label"].lower()] > 1: s["label"] = f"{s['name']} (no. {s['id']})"
        self.by_id = {s["id"]: s for s in self.st}
        self.subs = {}
        for s in self.st:
            if s["sub"]: self.subs.setdefault(s["sub"], []).append(s)
        self.sub_url = {k: f"fuel-prices/{slug(k[0])}-{k[1]}/" for k in self.subs}
        names = {}
        for k in self.subs: names[k[0]] = names.get(k[0], 0) + 1
        # A suburb gets its postcode in its title and heading when another suburb has its name (South Hurstville has two
        # postcodes) or a region page does (Bathurst 2795 beside the Bathurst region): no two pages share a title
        regs = {n.lower() for n, *_ in REGIONS} | {t.lower() for t in REGION_TITLE.values()}   # a "Canberra" suburb gets its postcode
        self.sub_label = {k: k[0] if names[k[0]] == 1 and k[0].lower() not in regs else f"{k[0]} {k[1]}" for k in self.subs}
        self.sub_at = {k: (sum(s["la"] for s in v) / len(v), sum(s["lo"] for s in v) / len(v)) for k, v in self.subs.items()}
        self.brands = {}
        for s in self.st: self.brands.setdefault(s["brand"], []).append(s)
        self.grid = {}
        for s in self.st: self.grid.setdefault(self._cell(s["la"], s["lo"]), []).append(s)
        # A brand page needs 3+ stations and a current price to lead with (else nothing links to it)
        # A brand page leads with the first fuel any of its stations has a price for (U91 nearly always), except when none of its
        # Sydney stations sells U91: then the fuel most of them sell (Sydney's Costcos sell E10 and 98; one in Canberra sells U91)
        def lead(v):
            syd = [s for s in v if not s.get("out")]
            n = {f: len(self.cheapest(syd, f, members=True)) for f in FUELS}
            if syd and not n["U91"] and max(n.values()): return next(f for f in FUELS if n[f] == max(n.values()))
            return next((f for f in FUELS if self.cheapest(v, f, 1, members=True)), None)
        self.brand_f0 = {b: lead(v) for b, v in self.brands.items()}
        self.brand_url = {b: f"brands/{slug(b)}/" for b, v in self.brands.items() if len(v) >= BRAND_MIN and slug(b) and self.brand_f0[b]}
        self.regions = {}
        for s in self.st:
            if not s.get("out"): continue
            d, name = min((km((s["la"], s["lo"]), (la, lo)) / r, n) for n, la, lo, r in REGIONS)
            s["region"] = name if d <= 1 else None
            if s["region"]: self.regions.setdefault(name, []).append(s)
        # a region page needs 5+ stations and a current price to lead with (else nothing links to it)
        self.regions = {n: v for n, v in self.regions.items() if len(v) >= REGION_MIN and any(self.cheapest(v, f, 1) for f in FUELS)}
        for s in self.st:
            if s.get("region") not in self.regions: s["region"] = None
        self.region_url = {n: f"fuel-prices/{slug(n)}/" for n in self.regions}
        self.any_out = any(s.get("out") for s in self.st)
        self.act = [s for s in self.st if s.get("out") and state_of(s.get("pc"), s.get("st")) == "ACT"]
        self.n_syd = sum(not s.get("out") for s in self.st)

    # ---- small helpers
    _cell = staticmethod(lambda la, lo: (int(math.floor(la / 0.06)), int(math.floor(lo / 0.06))))   # cells of about 6 km
    fresh = staticmethod(lambda s, f: f in s["p"] and not (num(s["p"][f][1]) and s["p"][f][1] > (OUT_STALE if s.get("out") else STALE)))

    def since(self, age):
        """'12 Nov': the day a price `age` days old was reported (the site's short date), or '' if unknown."""
        if not num(age) or age < 0: return ""
        return short_date((dt.date.fromisoformat(self.asof) - dt.timedelta(days=int(age))).isoformat())

    def held(self, s, f):
        """True for a price outside Sydney that is over a week old but still current there (8 to 20 days): it is shown as
        'unchanged since 12 Nov', not as old."""
        p = s["p"].get(f)
        return bool(p and s.get("out") and num(p[1]) and STALE < p[1] <= OUT_STALE)
    dead = staticmethod(lambda s: all(num(p[1]) and p[1] > DEAD for p in s["p"].values()))   # nothing reported for a month

    def changed(self, pool):
        """The day the newest price among `pool` was reported (asof less its age in days): a sitemap lastmod for pages
        outside Sydney, whose content moves only with their prices. Sydney pages carry the day's forecast call, so they keep asof."""
        ages = [p[1] for s in pool for p in s["p"].values() if num(p[1]) and p[1] >= 0]
        if not ages: return self.asof
        return (dt.date.fromisoformat(self.asof) - dt.timedelta(days=int(min(ages)))).isoformat()

    # Premium diesel shown as a station's diesel (usable(), `pd`) stays out of every average: medians and brand figures
    # are of regular diesel, as the app's and dashboard's are. It is still listed and still counts for "cheapest".
    reg = staticmethod(lambda s, f: not (f == "DL" and s.get("pd")))

    def median(self, pool, f):
        """The middle fresh price for fuel f among `pool` (members-only sites and premium diesel left out), or None under 3 prices."""
        ps = [s["p"][f][0] for s in pool if self.fresh(s, f) and not s.get("m") and self.reg(s, f)]
        return statistics.median(ps) if len(ps) >= 3 else None

    @staticmethod
    def faq(items):
        """Questions with short answers: (html, FAQPage JSON-LD). items: [(question, answer as plain text)]."""
        htm = "<h2>Quick answers</h2>" + "".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in items)
        return htm, {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in items]}

    def near(self, at, radius=NEAR_KM):
        """Stations within `radius` km of a (lat, lon), nearest first, as (km, station)."""
        a, b = self._cell(*at); k = max(1, math.ceil(radius / 5.0))   # a cell is at least 5 km wide anywhere in NSW
        hits = [(km(at, (s["la"], s["lo"])), s) for i in range(a - k, a + k + 1) for j in range(b - k, b + k + 1) for s in self.grid.get((i, j), [])]
        return sorted(((d, s) for d, s in hits if d <= radius), key=lambda t: t[0])

    def cheapest(self, pool, f, n=None, members=False):
        """`pool` sorted by today's price for fuel f: fresh prices only, and no members-only sites unless asked."""
        got = sorted((s for s in pool if self.fresh(s, f) and (members or not s.get("m"))), key=lambda s: (s["p"][f][0], s["name"]))
        return got if n is None else got[:n]

    def vs_median(self, s, f):
        """'3.2c under the Sydney median' as HTML, or '' outside Sydney."""
        r = self.live.get(f)
        if s.get("out") or not r or not num(r.get("now")): return ""
        g = s["p"][f][0] - r["now"]
        if abs(g) < 0.05: return "at the Sydney median"
        return f'<span class="{"cheap" if g < 0 else "dear"}">{cents(g)} {"under" if g < 0 else "over"}</span> the Sydney median'

    def advice(self, s, f):
        p = s["p"][f]
        if (s.get("out") and p[2] == "na") or not p[3]: return ""
        return f'<span class="chip {TONE.get(p[2], "calm")}">{esc(p[3])}</span>'

    @staticmethod
    def reason(text):
        """The API's reason ("Sydney U91 expected about 8c lower by Tue 24 Nov") with the fuel's name spelled out."""
        return re.sub(r"\b(U91|P95|P98|DL)\b", lambda m: NAME[m.group(1)] if m.group(1) != "DL" else "diesel", str(text or "")).rstrip(".")

    def outlook(self, f, where="Sydney"):
        """One sentence on the week ahead for a fuel's Sydney median."""
        r = self.live[f]; d7 = r["d7"]; lo, hi = r["now"] + r["lo7"], r["now"] + r["hi7"]
        move = "to be little changed" if abs(d7) < 1 else f"to be about {cents(d7)} {'higher' if d7 > 0 else 'lower'}"
        return (f"The {where} median for {NAME[f]} is {c1(r['now'])}c/L and Bowser expects it {move} in a week "
                f"(likely range {lo:.0f}c to {hi:.0f}c).")

    def tested(self, f):
        """The replayed record for fuel f as the app shows it (app/src/lib/track.ts tested()): the last year of the replay
        when it holds 300+ days, else the whole replay. (period, % right, % right for the best fixed rule and its call,
        c/L saved a call against filling up the day you check, or None), or None."""
        r = (self.track.get("replay") or {}).get(f) if isinstance(self.track.get("replay"), dict) else None
        ok = lambda d: (isinstance(d, dict) and all(num(d.get(k)) and math.isfinite(d[k]) for k in ("n", "right")) and 0 <= d["right"] <= d["n"]
                        and d["n"] > 0)
        if not ok(r) or not (isodate(r.get("from")) and isodate(r.get("to"))): return None
        rc = r.get("recent")
        lead = rc if ok(rc) and rc["n"] >= 300 and isodate(rc.get("to")) else r
        try:
            period = (f"the year to {short_date(lead['to'])}" if lead is not r else
                      f"{r['from'][:4]}–{r['to'][:4]} prices")
        except (KeyError, TypeError, ValueError): return None
        b = lead.get("base") if isinstance(lead.get("base"), dict) else {}
        word = {"up": "fill now", "down": "wait", "flat": "no rush"}.get(b.get("cls"))
        sv = lead.get("save")
        return (period, lead["right"] / lead["n"], b["right"] / lead["n"] if num(b.get("right")) and 0 <= b["right"] <= lead["n"] and word else None, word,
                sv if num(sv) and math.isfinite(sv) else None)

    def proof(self, f, up):
        """One line of evidence beside a call: what following it saved and how often it was right, tested; '' without a record."""
        x = self.tested(f)
        if not x: return ""
        period, pct, base, word, save = x
        # the saving as the app words it (worth() in track.ts): under 50c a tank isn't worth a sentence; a loss is said, not hidden
        tank = TANK * save / 100 if save is not None else 0
        money = (f"on average, following it would have {'saved' if tank > 0 else 'cost'} about ${abs(tank):.2f} a {TANK} L tank against filling up the day you check, and it was "
                 if abs(tank) >= 0.5 else "")
        txt = (f"Bowser’s Sydney {NAME[f]} call, tested on {period}: " + money
               + f"right on {pct0(pct)} of days" + (f" (always “{word}”: {pct0(base)})" if base is not None else "") + ".")
        return esc(txt) + (f' <a href="{up}fuel-price-forecast/accuracy/">How it’s scored</a>' if self.has_acc else "")

    def verdict_card(self, f, up=None):
        r = self.live[f]; v = r.get("verdict") or {}
        pr = self.proof(f, up) if up is not None else ""
        return (f'<div class="verdict {TONE.get(v.get("cls"), "calm")}"><span class="eyebrow">Bowser’s call for Sydney {esc(NAME[f])}, {esc(self.sday)}</span>'
                f'<b>{esc(v.get("head", "No call today"))}</b><span>{esc(self.outlook(f))}</span>'
                + (f'<span class="small">{pr}</span>' if pr else "") + "</div>")

    @staticmethod
    def path(r, key, days):
        """The forecast for `days` ahead (0..14) read off the API's 1/3/7/14-day points, straight lines between them.
        key: "d" (the expected move), "lo" or "hi" (the likely range). None if a point is missing."""
        xs, ys = [0, 1, 3, 7, 14], [0] + [r.get(f"{key}{h}") for h in (1, 3, 7, 14)]
        if not all(num(y) for y in ys): return None
        for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
            if x0 <= days <= x1: return y0 + (y1 - y0) * (days - x0) / (x1 - x0)
        return None

    def med_series(self, f):
        """(first day, [Sydney median per day]) from history.json, or (None, [])."""
        H = (self.history.get("hist") or {}).get(f) or {}; med = H.get("med") or []
        if not isinstance(self.history.get("start"), str) or not isinstance(med, list) or not med: return None, []
        try: return dt.date.fromisoformat(self.history["start"]), med
        except ValueError: return None, []

    def stage(self):
        """Where Sydney is in its price cycle: (days since the last jump, the usual gap, a short label, its tone, a sentence), or None."""
        return cycle_stage(self.stats, self.fc_asof, self.live)

    def stage_card(self):
        st = self.stage()
        if not st: return ""
        since, gap, head, tone, txt = st
        return (f'<div class="verdict {tone}"><span class="eyebrow">Where Sydney is in the petrol price cycle, {esc(self.sday)}</span><b>{esc(head)}</b>'
                f"<span>Day {since} since the last price jump; in normal years jumps come about every {gap:.0f} days. In short: {esc(txt)}.</span></div>")

    def jumps(self):
        """build.py's latest price jumps (stats.recent_jumps), oldest first, the well-formed ones only."""
        out = []
        for j in self.stats.get("recent_jumps") or []:
            if not (isinstance(j, dict) and isinstance(j.get("date"), str) and num(j.get("amp"))): continue
            try: dt.date.fromisoformat(j["date"])
            except ValueError: continue
            out.append(j)
        return out

    def cycle_status(self):
        """A plain-text answer to "is the Sydney price cycle still running?" from the last 12 months of jumps, or ''."""
        amp = self.stats.get("cycle_amp_calm"); today = dt.date.fromisoformat(self.fc_asof)
        recent = [j for j in self.jumps() if 0 <= (today - dt.date.fromisoformat(j["date"])).days <= 365]
        if not recent or not num(amp): return ""
        m = statistics.median(j["amp"] for j in recent); gap = self.stats.get("cycle_gap_calm")
        few = num(gap) and gap > 0 and len(recent) < 0.6 * 365 / gap            # normal years: 365 / gap jumps
        small = m < 0.75 * amp
        txt = (f"In the last 12 months Sydney had {len(recent)} price jump{'s' if len(recent) != 1 else ''}, typically {m:.0f}c a litre, against about {amp:.0f}c"
               + (f" and {365 / gap:.0f} a year" if few else "") + " in normal years"
               + (", so the cycle has been weaker than usual: fewer and smaller jumps." if few and small else
                  ", so the cycle has been weaker than usual: fewer jumps." if few else
                  ", so the cycle is still there but its jumps have been smaller than usual." if small else ", so the cycle is running much as usual."))
        st = self.stage()
        return txt + (f" Today is day {st[0]} since the last jump." if st else "")

    def xmas_rows(self):
        """What the Sydney U91 median did from 10 December to 10 January in each year history.json covers in full."""
        s0, med = self.med_series("U91")
        if not s0: return []
        end = s0 + dt.timedelta(days=len(med) - 1)
        at = lambda d: med[(d - s0).days] if 0 <= (d - s0).days < len(med) and num(med[(d - s0).days]) else None
        rows = []
        for y in range(s0.year, end.year + 1):
            a, b = dt.date(y, 12, 10), dt.date(y + 1, 1, 10)
            if a < s0 or b > end: continue
            win = [(a + dt.timedelta(days=i), at(a + dt.timedelta(days=i))) for i in range((b - a).days + 1)]
            got = [(d, v) for d, v in win if v is not None]
            if len(got) < 25 or None in (win[0][1], at(dt.date(y, 12, 24)), win[-1][1]): continue
            # a jump: 8c or more in three days, the rule build.py counts the cycle with
            rise = lambda d: (v := at(d)) is not None and (b3 := at(d - dt.timedelta(days=3))) is not None and v - b3 >= 8
            jump = next((d for d, _ in win if rise(d) and not rise(d - dt.timedelta(days=1))), None)
            hi_d, hi = max(got, key=lambda t: t[1]); lo_d, lo = min(got, key=lambda t: t[1])
            rows.append(dict(year=y, start=win[0][1], eve=at(dt.date(y, 12, 24)), end=win[-1][1], hi=hi, hi_d=hi_d, lo=lo, lo_d=lo_d, jump=jump))
        return rows if len(rows) >= 3 else []

    def forecast_chart(self, f, days=60):
        """The last `days` of the Sydney median and the 14-day forecast after it, with its likely range shaded."""
        r = self.live.get(f); s0, med = self.med_series(f)
        if not r or not s0: return ""
        end = s0 + dt.timedelta(days=len(med) - 1); today = dt.date.fromisoformat(self.fc_asof)
        past = [v if num(v) else None for v in med[-days:]]
        if end > today:
            if (end - today).days >= len(past): return ""
            past = past[:len(past) - (end - today).days]
        if sum(v is not None for v in past) < 20: return ""
        gap = max((today - end).days, 0)
        i0 = len(past) - 1 + gap                       # today's position on the chart
        n = i0 + 15
        line = past + [None] * (n - len(past))
        fc, lo, hi = [None] * n, [None] * n, [None] * n
        for k in range(15):
            d, a, b = self.path(r, "d", k), self.path(r, "lo", k), self.path(r, "hi", k)
            if d is None: return ""
            fc[i0 + k] = r["now"] + d
            if a is not None and b is not None: lo[i0 + k], hi[i0 + k] = r["now"] + a, r["now"] + b
        allv = [v for v in line + fc + lo + hi if num(v)]
        first = today - dt.timedelta(days=i0)
        svg = chart([("st", line), ("md", fc)], math.floor(min(allv) / 10) * 10, math.ceil(max(allv) / 10) * 10,
                    (short_date(str(first)), short_date(str(today + dt.timedelta(days=14)))),
                    f"Sydney median {NAME[f]} price for the last {days} days and Bowser’s forecast for the next 14 days: about "
                    f"{c1(r['now'] + r['d14'])} cents a litre in 14 days", band=(lo, hi))
        return (f'<div class="card"><div class="legend"><span><i class="a"></i>Sydney median</span><span><i class="b"></i>Forecast, next 14 days</span>'
                f"<span>Shaded: the likely range</span></div>{svg}</div>")

    # ---- the page shell
    def page(self, path, kind, pattern, title, desc, body, crumbs=(), ld=(), priority=0.5, index=True, root=None, lastmod=None):
        """Write OUT/path/index.html (path '' is not ours: the dashboard). crumbs: [(label, path)] below Home."""
        depth = path.strip("/").count("/") + 1 if path else 0
        up = ("../" * depth or "./") if root is None else root
        url = f"{self.site}/{path}"
        trail = [("Home", "")] + list(crumbs)
        crumb_html = " › ".join(f'<a href="{up}{esc(p)}">{esc(l)}</a>' for l, p in trail)
        blocks = list(ld)
        if crumbs:
            blocks.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": l, "item": f"{self.site}/{p}"} for i, (l, p) in enumerate(trail)]})
        nav = (f'<a href="{up}fuel-prices/">Prices by suburb</a><a href="{up}fuel-price-forecast/">Forecast</a>'
               f'<a href="{up}petrol-price-cycle/">Price cycle</a><a href="{up}brands/">Brands</a><a href="{up}" data-cta="nav-map">Live map</a>')
        fuels = "".join(f'<a href="{up}fuel-prices/{FSLUG[f]}/">{NAME[f]} prices</a>' for f in FUELS if f in self.live)
        guides = (f'<a href="{up}fuel-price-forecast/">Fuel price forecast</a>'
                  + (f'<a href="{up}fuel-price-forecast/accuracy/">Forecast accuracy</a>' if self.has_acc else "")
                  + f'<a href="{up}petrol-price-cycle/">Sydney petrol price cycle</a>'
                  + (f'<a href="{up}best-day-to-buy-petrol/">Best day to buy petrol</a>' if self.has_best else "")
                  + (f'<a href="{up}petrol-prices-christmas/">Petrol prices at Christmas</a>' if self.xmas else "")
                  + f'<a href="{up}petrol-deals-sydney/">Fuel discounts</a>' + (f'<a href="{up}7-eleven-fuel-price-lock/">7-Eleven Fuel Price Lock</a>' if self.built("lock") else ""))
        doc = f"""<!doctype html>
<html lang="en-AU" data-page="{esc(kind)}" data-pattern="{esc(pattern)}">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{'<link rel="canonical" href="' + esc(url) + '">' if index else '<meta name="robots" content="noindex">'}
<meta property="og:type" content="website">
<meta property="og:site_name" content="Bowser">
<meta property="og:locale" content="en_AU">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(url)}">
<meta property="og:image" content="{self.site}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Bowser: fill up now, or wait? Fuel prices for NSW and the ACT at checkbowser.app">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#f7f5f0" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#141618" media="(prefers-color-scheme: dark)">
<link rel="icon" href="{up}favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{up}apple-touch-icon.png">
{"".join(jsonld(b) for b in blocks)}
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header><a class="logo" href="{up}" data-cta="logo">{MARK}Bowser</a><nav aria-label="Main">{nav}</nav></header>
{'<div class="crumbs">' + crumb_html + '</div>' if crumbs else ''}
<main>
{body}
</main>
<footer>
<nav aria-label="Fuels">{fuels}</nav>
<nav aria-label="Guides">{guides}</nav>
<nav aria-label="More"><a href="{up}fuel-prices/">{"NSW and ACT" if self.any_out else "Sydney"} fuel prices</a><a href="{up}station/">All stations</a><a href="{up}nsw-fuelcheck/">About NSW FuelCheck</a><a href="{up}badge/">Free badge for your site</a><a href="{up}about/">About Bowser</a><a href="{up}privacy/">Privacy</a></nav>
<div>{SOURCES}</div>
<div>Prices as reported to FuelCheck for {esc(self.day)}; a station can change its price at any time, so check the board before you fill. Forecasts are estimates for planning, not financial advice.</div>
<div>Visits are counted anonymously: no cookies, and never your location, your area or your IP address.</div>
</footer>
</div>
<script>{JS}</script>
</body>
</html>
"""
        dest = os.path.join(self.out, path, "index.html") if not path.endswith(".html") else os.path.join(self.out, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh: fh.write(doc)
        if index: self.urls.append((path, priority, lastmod or self.asof))

    # ---- shared pieces
    def price_table(self, pool, fuels=FUELS, sort=None, limit=None, where=True, up=""):
        """Stations x fuels. The cheapest fresh price in each column is marked; an old price is greyed with its age."""
        sort = sort or next((f for f in fuels if any(f in s["p"] for s in pool)), fuels[0])
        rows = sorted(pool, key=lambda s: (f"{s['p'][sort][0]:07.1f}" if sort in s["p"] else "9", s["name"]))
        if limit: rows = rows[:limit]
        cols = [f for f in fuels if any(f in s["p"] for s in rows)]
        best = {f: min((s["p"][f][0] for s in rows if self.fresh(s, f)), default=None) for f in cols}
        out = ['<div class="scroll"><table><thead><tr><th>Station</th>' + "".join(f'<th class="n">{SHORT[f]}</th>' for f in cols)
               + "<th>Bowser says</th></tr></thead><tbody>"]
        for s in rows:
            sub = f'<br><span class="small">{esc(s["sub"][0] if s["sub"] else s["s"])}{" · Members only" if s.get("m") else ""}</span>' if where else \
                  ('<br><span class="small">Members only</span>' if s.get("m") else "")
            tds = []
            for f in cols:
                if f not in s["p"]: tds.append('<td class="n">–</td>'); continue
                p = s["p"][f]; old = not self.fresh(s, f)
                cls = "n old" if old else "n best" if p[0] == best[f] else "n"
                note = f"<br><span class=small>{p[1]} days old</span>" if old else \
                       f"<br><span class=small>unchanged since {self.since(p[1])}</span>" if self.held(s, f) else ""
                tds.append(f'<td class="{cls}">{c1(p[0])}{note}</td>')
            f0 = sort if sort in s["p"] else s["main"]
            tds.append(f"<td>{self.advice(s, f0)}</td>")
            out.append(f'<tr><td><a href="{up}{esc(s["url"])}">{esc(s["name"])}</a>{sub}</td>{"".join(tds)}</tr>')
        out.append("</tbody></table></div>")
        return "".join(out)

    def fuel_cards(self, pool, up, scope):
        """One card per fuel: the cheapest fresh price in `pool` and where."""
        out = []
        for f in FUELS:
            top = self.cheapest(pool, f, 1) or self.cheapest(pool, f, 1, members=True)
            if not top: continue
            s = top[0]
            out.append(f'<div class="card"><span class="eyebrow">Cheapest {esc(NAME[f])}</span><span class="big">{c1(s["p"][f][0])}<small>c/L</small></span>'
                       f'<span class="small"><a href="{up}{esc(s["url"])}">{esc(s["name"])}</a>{"" if scope else ", " + esc(s["sub"][0] if s["sub"] else s["s"])}</span></div>')
        return '<div class="grid">' + "".join(out) + "</div>" if out else ""

    def sources_p(self):
        return ('<p class="small">Prices are the ones each station reported to NSW FuelCheck, refreshed by Bowser several times a day. '
                f'This page was last updated on {esc(self.day)}.</p>')

    # ---- pages
    def suburb(self, key):
        name, pc = key; pool = self.subs[key]; path = self.sub_url[key]; up = "../../"
        out_syd = all(s.get("out") for s in pool)
        state = state_of(pc, next((s.get("st") for s in pool if s.get("st")), None))
        f0 = next((f for f in FUELS if self.cheapest(pool, f, 1)), None) or next(f for f in FUELS if any(f in s["p"] for s in pool))
        top = (self.cheapest(pool, f0, 1) or self.cheapest(pool, f0, 1, members=True) or [min((s for s in pool if f0 in s["p"]), key=lambda s: s["p"][f0][0])])[0]
        n = len(pool); stations_n = f"{n} station{'s' if n != 1 else ''}"; label = self.sub_label[key]
        old = not self.fresh(top, f0)                     # every price for this fuel here is over a week old
        title = f"{label} fuel prices today: {SHORT[f0] if f0 != 'DL' else 'diesel'} from {c1(top['p'][f0][0])}c | Bowser"
        if len(title) > 62 or old: title = f"{label} fuel prices today | Bowser"
        others = [f"{NAME[f]} {c1(t[0]['p'][f][0])}c" for f in FUELS if f != f0 and (t := self.cheapest(pool, f, 1))]
        body_ = (f" {state} {pc} for {self.sday}: {NAME[f0]} {'last listed at' if old else 'from'} {c1(top['p'][f0][0])}c/L at {top['name']}"
                 + (f", {', '.join(others[:2])}" if others else "") + f". Compare {stations_n}" + ("." if out_syd else " and see whether to fill up or wait."))
        cbr_desc = re.sub(r"\s+", " ", f"Petrol prices in {name}, Canberra{body_}").strip()   # "Canberra" for an ACT suburb, only when it fits whole
        desc = cbr_desc if state == "ACT" and name.lower() != "canberra" and len(cbr_desc) <= 155 else clip(f"Petrol prices in {name}{body_}")
        link = f'<a href="{up}{esc(top["url"])}">{esc(top["name"])}</a>'
        vm = self.vs_median(top, f0)
        if old:
            lead = (f"The lowest listed {NAME[f0]} price in {esc(name)} is <b>{c1(top['p'][f0][0])}c/L</b> at {link}, but it was last updated "
                    f"{top['p'][f0][1]} days ago, so check it before you drive there.")
        else:
            lead = f"The cheapest {NAME[f0]} in {esc(name)} today is <b>{c1(top['p'][f0][0])}c/L</b> at {link}" + (" (members only)" if top.get("m") else "") + (f", {vm}." if vm else ".")
            if self.held(top, f0): lead = lead[:-1] + f" (unchanged since {esc(self.since(top['p'][f0][1]))})."
        lead += f" {esc(name)} has {stations_n} reporting prices to NSW FuelCheck." if n > 1 else ""
        body = [f"<h1>{esc(label)} fuel prices today</h1>", f'<p class="lead">{lead}</p>', self.fuel_cards(pool, up, True)]
        if not out_syd: body.append(self.verdict_card(f0 if f0 in self.live else "U91", up))
        body += [f"<h2>Petrol and diesel prices in {esc(name)} {pc}</h2>", self.price_table(pool, where=False, up=up)]
        at = self.sub_at[key]
        nearby = [s for d, s in self.near(at) if s["sub"] != key]
        if nearby:
            pick = self.cheapest(nearby, f0, 8)
            if pick:
                body += [f"<h2>Cheapest {esc(NAME[f0])} near {esc(name)}</h2>",
                         f"<p>Stations within {NEAR_KM:.0f} km of {esc(name)}, cheapest first. A short drive can beat the local price.</p>",
                         self.price_table(pick, sort=f0, up=up)]
        close = [k for d, k in sorted((km(at, self.sub_at[k]), k) for k in self.subs if k != key)[:10] if d <= 15]
        if close:
            body += ["<h2>Nearby suburbs</h2>", '<ul class="cols">' + "".join(
                f'<li><a href="{up}{esc(self.sub_url[k])}">{esc(self.sub_label[k])} fuel prices</a></li>' for k in close) + "</ul>"]
        body.append(f"<h2>Should you fill up in {esc(name)} today?</h2>")
        if out_syd:
            reg = next((s["region"] for s in pool if s.get("region") in self.regions), None)
            # an ACT suburb on the Canberra page links to its district's section there, when that section was built
            dist = next((self.district(s) for s in pool if s.get("region") == CANBERRA and self.is_act(s)), None) if reg == CANBERRA else None
            more = (f' See <a href="{up}{esc(self.region_url[reg])}#{slug(dist)}">{esc(dist)} on the Canberra page</a>, or <a href="{up}{esc(self.region_url[reg])}">all {esc(reg)} fuel prices</a>.'
                    if dist and dist in self.cbr_districts()[1] else
                    f' See <a href="{up}{esc(self.region_url[reg])}">all {esc(reg)} fuel prices</a>.' if reg else "")
            body.append(f"<p>Bowser’s forecast is fitted on Sydney prices, so for {esc(name)} this page shows today’s prices only. "
                        "Without a forecast, the saving is in comparing stations rather than picking the day." + more + "</p>")
        else:
            r = self.live[f0 if f0 in self.live else "U91"]; v = (r.get("verdict") or {}).get("head", "")
            body.append(f"<p>{esc(self.outlook(f0 if f0 in self.live else 'U91'))} Bowser’s call today is <b>{esc(v.lower())}</b>. "
                        f"Each station also gets its own call in the table above, based on how it usually prices against the rest of Sydney. "
                        f'See the <a href="{up}fuel-price-forecast/">Sydney fuel price forecast</a> for the 14-day outlook, '
                        f'or <a href="{up}" data-cta="suburb-map">open the live map</a> to compare stations around you.</p>')
        if state == "ACT":
            src = (f'<p>From <a href="{up}nsw-fuelcheck/">NSW FuelCheck</a>, which also lists prices for ACT service stations that report to it. '
                   "Bowser reads those prices several times a day. Canberra prices change less often than Sydney’s, so a price several days old is often still current.</p>")
        else:
            src = (f'<p>From <a href="{up}nsw-fuelcheck/">NSW FuelCheck</a>: every NSW service station must report its prices to the NSW Government when they change. '
                   + ("Bowser reads those prices several times a day and adds a forecast.</p>" if not out_syd else
                      "Bowser reads those prices several times a day. Its fill-or-wait forecast covers Sydney only, so here you get today’s prices.</p>"))
        body += [f"<h3>Where do these {esc(name)} prices come from?</h3>", src, self.sources_p()]
        ld = [{"@context": "https://schema.org", "@type": "ItemList", "name": f"Service stations in {name} {state} {pc}", "numberOfItems": n,
               "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": s["name"], "url": f"{self.site}/{s['url']}"}
                                   for i, s in enumerate(sorted(pool, key=lambda s: s["name"]))]}]
        self.page(path, "suburb", "/fuel-prices/:suburb/", title, desc, "\n".join(b for b in body if b),
                  crumbs=[("Fuel prices", "fuel-prices/"), (label, path)], ld=ld, priority=0.7, index=not all(self.dead(s) for s in pool),
                  lastmod=self.changed(pool) if out_syd else None)

    def station_chart(self, s, f):
        """90 days of this station's price for fuel f against the Sydney median, plus a sentence on the range."""
        d = self.details.get(s["id"]) or {}
        h = (d.get("hist") or {}).get(f)
        if not isinstance(h, list) or not d.get("start"): return ""
        days = 90; mine = h[-days:]
        vals = [v for v in mine if num(v)]
        if len(vals) < 20: return ""
        end = dt.date.fromisoformat(d["start"]) + dt.timedelta(days=len(h) - 1)
        med = [None] * len(mine)
        hh = ((self.history.get("hist") or {}).get(f) or {}).get("med")
        if isinstance(hh, list) and self.history.get("start") and not s.get("out"):
            h0 = dt.date.fromisoformat(self.history["start"])
            for i in range(len(mine)):
                j = (end - dt.timedelta(days=len(mine) - 1 - i) - h0).days
                if 0 <= j < len(hh) and num(hh[j]): med[i] = hh[j]
        # A price far from the day's Sydney median is a slip in the station's history (a fuel stuck at an old price for
        # weeks): left out of the chart and the range, by the bounds export_api.py quarantines today's prices with
        mine = [None if num(v) and num(m) and not -45 <= v - m <= 80 else v for v, m in zip(mine, med)]
        vals = [v for v in mine if num(v)]
        if len(vals) < 20: return ""
        allv = vals + [v for v in med if num(v)]
        lo, hi = math.floor(min(allv) / 10) * 10, math.ceil(max(allv) / 10) * 10
        first = end - dt.timedelta(days=len(mine) - 1)
        svg = chart([("md", med), ("st", mine)], lo, hi, (short_date(str(first)), short_date(str(end))),
                    f"{s['name']} {NAME[f]} price over {len(mine)} days: between {min(vals):.1f} and {max(vals):.1f} cents a litre")
        now = s["p"][f][0]; below = sum(v > now for v in vals) / len(vals)
        above = sum(v < now for v in vals) / len(vals)
        rank = ("" if max(vals) == min(vals) else f"Today’s {c1(now)}c is lower than on {below:.0%} of those days." if below >= 0.5
                else f"Today’s {c1(now)}c is higher than on {above:.0%} of those days." if above >= 0.05 else "")
        legend = (f'<div class="legend"><span><i class="a"></i>{esc(s["name"])}</span>'
                  + ('<span><i class="b"></i>Sydney median</span>' if any(num(v) for v in med) else "") + "</div>")
        return (f"<h2>{esc(NAME[f])} price history at {esc(s['name'])}</h2>"
                f'<div class="card">{legend}{svg}</div>'
                f"<p>Over the last {len(mine)} days {esc(NAME[f])} here has ranged from <b>{min(vals):.1f}c</b> to <b>{max(vals):.1f}c</b> a litre, "
                f"averaging {sum(vals) / len(vals):.1f}c. {rank}</p>")

    def station_recent(self, s, f):
        """For a station outside Sydney until it has the 20 days the chart needs (all-NSW prices began in mid-November 2026):
        one sentence on its price since it was first seen. '' under 3 days."""
        d = self.details.get(s["id"]) or {}
        h = (d.get("hist") or {}).get(f)
        if not isinstance(h, list) or not isodate(d.get("start")): return ""
        got = [(i, v) for i, v in enumerate(h[-90:]) if num(v) and 50 <= v <= 500]
        if len(got) < 3: return ""
        # The history is each day's last price, carried forward from the day it was reported: equal days are one price
        day = lambda i: short_date(str(dt.date.fromisoformat(d["start"]) + dt.timedelta(days=len(h) - len(h[-90:]) + i)))
        vals = [v for _, v in got]
        if max(vals) - min(vals) < 0.05:
            txt = f"{esc(NAME[f])} at {esc(s['name'])} has held at <b>{vals[-1]:.1f}c</b> since {esc(day(got[0][0]))}."
        else:
            last = max((k for k in range(1, len(got)) if abs(got[k][1] - got[k - 1][1]) >= 0.05), default=len(got) - 1)
            txt = (f"Since {esc(day(got[0][0]))}, {esc(NAME[f])} at {esc(s['name'])} has ranged from <b>{min(vals):.1f}c</b> to <b>{max(vals):.1f}c</b> a litre; "
                   f"it last changed on {esc(day(got[last][0]))}, to {got[last][1]:.1f}c.")
        return f"<p>{txt} A price history chart appears here once there are 20 days.</p>"

    def station(self, s):
        up = "../../"; f0 = s["main"]; p0 = s["p"][f0]; d = self.details.get(s["id"]) or {}
        where = s["sub"][0] if s["sub"] else s["s"]
        title = f"{s['label']} fuel prices today: {SHORT[f0] if f0 != 'DL' else 'diesel'} {c1(p0[0])}c | Bowser"
        if len(title) > 65: title = f"{s['label']} fuel prices today | Bowser"
        if len(title) > 70:   # too long with the street: the station number keeps it unique where a cut street name wouldn't
            short = s["label"] if s["label"] == s["name"] else f"{s['name']} (no. {s['id']})"
            title = f"{short} fuel prices | Bowser" if len(short) <= 48 else f"{s['name'][:36].rstrip()}… no. {s['id']} fuel prices | Bowser"
        listed = ", ".join(f"{SHORT[f] if f != 'DL' else 'premium diesel' if s.get('pd') else 'diesel'} {c1(s['p'][f][0])}c" for f in FUELS if f in s["p"])
        call = "" if s.get("out") or not p0[3] else f" Bowser says: {p0[3].lower()}."
        desc = clip(f"{s['label']} fuel prices for {self.sday}: {listed}.{call}" + (" Today’s prices as reported to NSW FuelCheck." if s.get("out") else " With price history and a 7-day forecast."))
        addr = d.get("addr") if isinstance(d.get("addr"), str) else None
        sub_link = f'<a href="{up}{esc(self.sub_url[s["sub"]])}">{esc(self.sub_label[s["sub"]])}</a>' if s["sub"] else esc(where)
        brand_link = f'<a href="{up}{esc(self.brand_url[s["brand"]])}">{esc(s["brand"])}</a>' if s["brand"] in self.brand_url else esc(s["brand"])
        vm = self.vs_median(s, f0)
        lead = f"{esc(NAME[f0])} is <b>{c1(p0[0])}c/L</b> at {esc(s['name'])} today" + (f", {vm}." if vm else ".")
        if not self.fresh(s, f0): lead += f" This price was last updated {p0[1]} days ago, so check it before you drive there."
        elif self.held(s, f0): lead += f" It has been unchanged since {esc(self.since(p0[1]))}: prices outside Sydney change less often."
        body = [f"<h1>{esc(s['name'])}</h1>",
                f'<p class="small">{brand_link} · {esc(addr) if addr else sub_link}{" · Members only" if s.get("m") else ""}</p>',
                f'<p class="lead">{lead}</p>']
        cards = []
        for f in FUELS:
            if f not in s["p"]: continue
            p = s["p"][f]; g = self.vs_median(s, f)
            wk = f'<span class="small">In 7 days: about {c1(p[5])}c</span>' if len(p) > 5 and num(p[5]) and not s.get("out") else ""
            old = f'<span class="small">Updated {p[1]} days ago</span>' if not self.fresh(s, f) else \
                  f'<span class="small">Unchanged since {esc(self.since(p[1]))}</span>' if self.held(s, f) else ""
            cards.append(f'<div class="card"><span class="eyebrow">{"Premium diesel" if f == "DL" and s.get("pd") else esc(NAME[f])}</span><span class="big">{c1(p[0])}<small>c/L</small></span>'
                         f'{self.advice(s, f)}{f"<span class=small>{g}</span>" if g else ""}{wk}{old}</div>')
        body.append('<div class="grid">' + "".join(cards) + "</div>")
        dirs = f"https://www.google.com/maps/dir/?api=1&destination={s['la']:.5f},{s['lo']:.5f}"
        body.append(f'<div class="row"><a class="btn" href="{esc(dirs)}" rel="noopener" data-cta="directions">Directions</a>'
                    f'<a href="{up}" data-cta="station-map">Compare on the live map</a></div>')
        body.append(f"<h2>Should you fill up at {esc(s['name'])} today?</h2>")
        if s.get("out"):
            reg = s.get("region") if s.get("region") in self.regions else None; rm = self.median(self.regions[reg], f0) if reg else None
            # no region (or too few prices in it): the stations within LOCAL_KM stand in, so the page still says where it sits
            local = None if rm is not None else [t for _, t in self.near((s["la"], s["lo"]), LOCAL_KM) if t["id"] != s["id"]]
            lm = self.median(local, f0) if local is not None else None
            txt = "This station is outside Sydney, where Bowser has no forecast, so this page shows its prices only."
            if self.fresh(s, f0):
                ago = p0[1] if num(p0[1]) else None
                if ago is not None and not self.held(s, f0):
                    txt += f" It last reported its {esc(NAME[f0])} price to NSW FuelCheck " + ("today." if ago < 1 else "yesterday." if ago < 2 else f"{ago:.0f} days ago.")
                if rm is not None or lm is not None:
                    g = p0[0] - (rm if rm is not None else lm)
                    than = (f"the {esc(reg)} median of {c1(rm)}c" if rm is not None else
                            f"the median of the {sum(self.fresh(t, f0) and not t.get('m') for t in local)} stations within {LOCAL_KM} km ({c1(lm)}c)")
                    txt += (f" Its {esc(NAME[f0])} price is " + ("about the same as" if abs(g) < 0.5 else f"{cents(g)} {'under' if g < 0 else 'over'}")
                            + f" {than} today.")
                txt += f" A {TANK} L fill costs about ${TANK * p0[0] / 100:.2f}."
            body.append(f"<p>{txt}</p>")
        else:
            fc = (d.get("fc") or {}).get(f0) or {}
            say = esc((p0[3] or "no call today").lower()); why = ": " + esc(self.reason(p0[4])) if p0[4] else ""
            txt = f"Bowser’s call for {esc(NAME[f0])} here is <b>{say}</b>{why}."
            if num(fc.get("d7")) and num(fc.get("lo7")) and num(fc.get("hi7")):
                txt += (f" In a week Bowser expects about {c1(p0[0] + fc['d7'])}c here (likely range {p0[0] + fc['lo7']:.0f}c to {p0[0] + fc['hi7']:.0f}c).")
            if fc.get("rise"): txt += f" The next price rise is likely around {esc(short_date(fc['rise']))}."
            fill = TANK * p0[0] / 100; r = self.live.get(f0)
            txt += f" A {TANK} L fill costs about ${fill:.2f} today"
            if r and num(r.get("now")) and abs(p0[0] - r["now"]) >= 0.5:
                g = TANK * (p0[0] - r["now"]) / 100
                txt += f", ${abs(g):.2f} {'less' if g < 0 else 'more'} than at the Sydney median price"
            body.append(f"<p>{txt}.</p>")
            pr = d.get("profile") or {}
            notes = []
            typ = (pr.get("typ") or {}).get(f0)
            if num(typ) and pr.get("n", 0) >= 5:
                notes.append(f"usually prices {esc(NAME[f0])} about {cents(typ)} {'under' if typ < 0 else 'over'} the Sydney median" if abs(typ) >= 1
                             else f"usually prices {esc(NAME[f0])} close to the Sydney median")
            if pr.get("n", 0) >= 5 and num(pr.get("part")):
                notes.append("rarely joins Sydney’s price jumps, so its price stays steadier than most" if pr["part"] < 0.25
                             else "follows most of Sydney’s price jumps" if pr["part"] >= 0.7 else "joins some of Sydney’s price jumps")
            if notes: body.append(f"<p>From its price history, this station {' and '.join(notes)}.</p>")
        body.append(self.station_chart(s, f0) or (self.station_recent(s, f0) if s.get("out") else ""))
        # 4 km in Sydney; in the country, wider until three stations have a price to compare (or 25 km)
        at = (s["la"], s["lo"]); rad = 4
        for rad in ((4, 10, LOCAL_KM) if s.get("out") else (4,)):
            near = [(dist, t) for dist, t in self.near(at, rad) if t["id"] != s["id"]]
            if len(self.cheapest([t for _, t in near], f0)) >= 3: break
        pick = self.cheapest([t for _, t in near], f0, 6)
        if pick:
            n_cheaper = sum(t["p"][f0][0] < p0[0] for t in pick)
            nc = next(((dist, t) for dist, t in near if self.fresh(t, f0) and not t.get("m") and t["p"][f0][0] <= p0[0] - 1), None) if self.fresh(s, f0) else None
            closest = (f' The nearest cheaper one is <a href="{up}{esc(nc[1]["url"])}">{esc(nc[1]["name"])}</a>, {nc[0]:.1f} km away, at {c1(nc[1]["p"][f0][0])}c '
                       f"({cents(p0[0] - nc[1]['p'][f0][0])} less, ${TANK * (p0[0] - nc[1]['p'][f0][0]) / 100:.2f} on a {TANK} L fill).") if nc else ""
            body += [f"<h2>Cheaper {esc(NAME[f0])} near {esc(s['name'])}?</h2>",
                     f"<p>The cheapest {esc(NAME[f0])} within {rad} km" + (f": {n_cheaper} of these {'is' if n_cheaper == 1 else 'are'} cheaper than here today." if n_cheaper else ". None of them beats this station today.") + closest + "</p>",
                     self.price_table(pick, sort=f0, up=up)]
        more = []
        if s["sub"]: more.append(f'<li><a href="{up}{esc(self.sub_url[s["sub"]])}">All fuel prices in {esc(self.sub_label[s["sub"]])}</a></li>')
        if s["brand"] in self.brand_url: more.append(f'<li><a href="{up}{esc(self.brand_url[s["brand"]])}">{esc(s["brand"])} fuel prices</a></li>')
        # An ACT or Queanbeyan station's "cheapest" link is Canberra's page, not Sydney's (an ACT station beyond the region's
        # radius too); with no Canberra page built, an ACT station gets no "cheapest" link rather than Sydney's
        cbr = s.get("region") == CANBERRA or (s.get("out") and state_of(s.get("pc"), s.get("st")) == "ACT")
        if cbr and CANBERRA in self.regions:
            more.append(f'<li><a href="{up}{esc(self.region_url[CANBERRA])}">Cheapest {esc(NAME[f0])} in Canberra today</a></li>')
        elif s.get("region") in self.regions: more.append(f'<li><a href="{up}{esc(self.region_url[s["region"]])}">{esc(s["region"])} fuel prices</a></li>')
        if f0 in self.live and not cbr: more.append(f'<li><a href="{up}fuel-prices/{FSLUG[f0]}/">Cheapest {esc(NAME[f0])} in Sydney today</a></li>')
        if not s.get("out"): more.append(f'<li><a href="{up}fuel-price-forecast/">Sydney fuel price forecast: will prices go up or down?</a></li>')
        body += ["<h2>More prices</h2>", "<ul>" + "".join(more) + "</ul>", self.sources_p()]
        # the address as the feed has it, tidied as update.py does ("NEW SOUTH WALES", a trailing ", AU", a comma before the state)
        tidy = re.sub(r"\s+", " ", re.sub(r",\s*([A-Za-z]{2,3})\s+(\d{4})\s*$", r" \1 \2", re.sub(r"\bNEW SOUTH WALES\b", "NSW",
                      re.sub(r",?\s*\bAU\s*$", "", addr or ""), flags=re.I))).strip()
        m = re.match(r"^(.*?),\s*(.+?)\s+(NSW|ACT)\s+(\d{4})$", tidy)
        ld = {"@context": "https://schema.org", "@type": "GasStation", "name": s["name"], "url": f"{self.site}/{s['url']}",
              "brand": {"@type": "Brand", "name": s["brand"]},
              "geo": {"@type": "GeoCoordinates", "latitude": s["la"], "longitude": s["lo"]},
              "address": {"@type": "PostalAddress", **({"streetAddress": m.group(1)} if m else {}), "addressLocality": where,
                          "addressRegion": state_of(s.get("pc"), s.get("st") or (m.group(3) if m else None)), **({"postalCode": str(s["pc"])} if s.get("pc") else {}), "addressCountry": "AU"}}
        crumbs = [("Fuel prices", "fuel-prices/")] + ([(REGION_TITLE[CANBERRA], self.region_url[CANBERRA])] if cbr and CANBERRA in self.regions else []) \
                 + ([(self.sub_label[s["sub"]], self.sub_url[s["sub"]])] if s["sub"] else [("Stations", "station/")]) + [(s["name"], s["url"])]
        self.page(s["url"], "station", "/station/:station/", title, desc, "\n".join(b for b in body if b), crumbs=crumbs, ld=[ld], priority=0.5,
                  index=not self.dead(s), lastmod=self.changed([s]) if s.get("out") else None)

    def fuel(self, f):
        up = "../../"; r = self.live[f]; nm = NAME[f]; path = f"fuel-prices/{FSLUG[f]}/"
        syd = [s for s in self.st if not s.get("out")]
        top = self.cheapest(syd, f, 25)                 # may be empty on a broken day: the page then has no ranking
        v = (r.get("verdict") or {}).get("head", "")
        title = f"{nm} price in Sydney today: {c1(r['now'])}c/L | Bowser"
        desc = (f"The Sydney median {nm} price is {c1(r['now'])}c/L on {self.sday}"
                + (f"; the cheapest is {c1(top[0]['p'][f][0])}c at {top[0]['name']}" if top else "")
                + f". Bowser’s call: {v.lower()}. See the 25 cheapest stations and the 7-day forecast.")
        body = [f"<h1>{esc(nm)} prices in Sydney today</h1>",
                f'<p class="lead">The median {esc(nm)} price across Sydney is <b>{c1(r["now"])}c/L</b> on {esc(self.day)}.'
                + (f' The cheapest is <b>{c1(top[0]["p"][f][0])}c</b> at <a href="{up}{esc(top[0]["url"])}">{esc(top[0]["name"])}</a>.' if top else "") + "</p>",
                self.verdict_card(f, up)]
        if num(r.get("p10")) and num(r.get("p90")):
            body.append(f"<p>Most Sydney stations charge between {c1(r['p10'])}c and {c1(r['p90'])}c for {esc(nm)} today, so on a {TANK} L tank the gap between "
                        f"a cheap station and a dear one is about ${TANK * (r['p90'] - r['p10']) / 100:.0f}.</p>")
        if top:
            body += [f"<h2>The {len(top) if len(top) < 25 else 25} cheapest {esc(nm)} stations in Sydney</h2>", self.price_table(top, fuels=[f], sort=f, up=up),
                     '<p class="small">Members-only sites and prices not updated for over a week are left out of this list.</p>']
        H = (self.history.get("hist") or {}).get(f) or {}
        med = [v for v in (H.get("med") or [])][-90:]
        if sum(num(v) for v in med) > 20 and self.history.get("start"):
            lo_b, hi_b = (H.get("p10") or [])[-90:], (H.get("p90") or [])[-90:]
            allv = [v for v in med + lo_b + hi_b if num(v)]
            end = dt.date.fromisoformat(self.history["start"]) + dt.timedelta(days=len(H["med"]) - 1)
            svg = chart([("st", med)], math.floor(min(allv) / 10) * 10, math.ceil(max(allv) / 10) * 10,
                        (short_date(str(end - dt.timedelta(days=len(med) - 1))), short_date(str(end))),
                        f"Sydney median {nm} price over 90 days", band=(lo_b, hi_b) if len(lo_b) == len(med) == len(hi_b) else None)
            mv = [v for v in med if num(v)]
            body += [f"<h2>Sydney {esc(nm)} price over the last 90 days</h2>",
                     f'<div class="card"><div class="legend"><span><i class="a"></i>Sydney median</span><span>Shaded: the middle 80% of stations</span></div>{svg}</div>',
                     f"<p>In the last 90 days the Sydney median for {esc(nm)} has been as low as {min(mv):.1f}c and as high as {max(mv):.1f}c a litre.</p>"]
        rows = []
        for b, pool in self.brands.items():
            ps = [s["p"][f][0] for s in pool if not s.get("out") and self.fresh(s, f) and not s.get("m") and self.reg(s, f)]
            if len(ps) >= 5: rows.append((sum(ps) / len(ps), b, len(ps)))
        if rows:
            rows.sort()
            body += [f"<h2>{esc(nm)} price by brand</h2>", "<p>The average price today at each brand with five or more Sydney stations selling this fuel.</p>",
                     '<div class="scroll"><table><thead><tr><th>Brand</th><th class="n">Average</th><th class="n">vs median</th><th class="n">Stations</th></tr></thead><tbody>'
                     + "".join(f'<tr><td>{f"<a href={chr(34)}{up}{esc(self.brand_url[b])}{chr(34)}>{esc(b)}</a>" if b in self.brand_url else esc(b)}</td><td class="n">{a:.1f}</td>'
                               f'<td class="n"><span class="{"cheap" if a < r["now"] else "dear"}">{"−" if a < r["now"] else "+"}{abs(a - r["now"]):.1f}</span></td><td class="n">{k}</td></tr>'
                               for a, b, k in rows) + "</tbody></table></div>"]
        subs = []
        for k, pool in self.subs.items():
            t = self.cheapest([s for s in pool if not s.get("out")], f, 1)
            if t: subs.append((t[0]["p"][f][0], k))
        subs.sort()
        if subs:
            body += [f"<h2>Cheapest suburbs for {esc(nm)} today</h2>", '<ul class="cols">' + "".join(
                f'<li><a href="{up}{esc(self.sub_url[k])}">{esc(self.sub_label[k])}</a> from {c1(p)}c</li>' for p, k in subs[:30]) + "</ul>"]
        rows = sorted((m, n) for n, pool in self.regions.items() if (m := self.median(pool, f)) is not None)
        if rows:
            body += [f"<h2>{esc(nm)} prices outside Sydney{' (NSW and ACT)' if self.act else ''}</h2>",
                     f"<p>The middle {esc(nm)} price today in each region outside Sydney that Bowser tracks. Bowser’s forecast covers Sydney only.</p>",
                     '<div class="scroll"><table><thead><tr><th>Region</th><th class="n">Median</th><th class="n">Cheapest</th><th class="n">vs Sydney</th></tr></thead><tbody>'
                     + "".join(f'<tr><td><a href="{up}{esc(self.region_url[n])}">{esc(n)}</a></td><td class="n">{c1(m)}</td><td class="n">{c1(self.cheapest(self.regions[n], f, 1)[0]["p"][f][0])}</td>'
                               f'<td class="n"><span class="{"cheap" if m < r["now"] else "dear"}">{"−" if m < r["now"] else "+"}{abs(m - r["now"]):.1f}</span></td></tr>' for m, n in rows)
                     + "</tbody></table></div>"]
        body.append(f"<h2>About {esc(nm)}</h2>")
        body.append("<p>" + FUEL_NOTE[f](self.stats) + "</p>")
        body.append("<p>" + " · ".join(f'<a href="{up}fuel-prices/{FSLUG[g]}/">{NAME[g]} prices</a>' for g in FUELS if g != f and g in self.live) + "</p>")
        body.append(self.sources_p())
        self.page(path, "fuel", f"/{path}", title, desc, "\n".join(body), crumbs=[("Fuel prices", "fuel-prices/"), (nm, path)], priority=0.9)

    def hub(self):
        up = "../"; syd = [s for s in self.st if not s.get("out")]
        r = self.live.get("U91") or next(iter(self.live.values()))
        f0 = r["fuel"]; v = (r.get("verdict") or {}).get("head", ""); nsw = self.any_out
        place = "NSW and ACT" if nsw else "Sydney"
        # "Check" leads: people search "nsw fuel price check" (Search Console, Nov 2026), and the brand is Check Bowser.
        # Never "FuelCheck" first: that is the government's service (docs/SEO.md)
        # "today" gives way to "and ACT" so the title stays at 65 (docs/MARKETING_NSW_ACT.md A1); the median and call stay Sydney's
        title = f"Check NSW and ACT fuel prices: cheapest petrol by suburb | Bowser" if nsw else "Check Sydney fuel prices today: cheapest petrol by suburb | Bowser"
        desc = (f"{place} petrol prices for {self.sday}: Sydney {NAME[f0]} median {c1(r['now'])}c/L, Bowser’s Sydney call: {(v or 'no call today').lower()}. "
                f"Cheapest fuel in {len(self.subs):,} suburbs.")
        desc = desc + " From NSW FuelCheck." if len(desc) <= 135 else clip(desc, 155)
        body = [f"<h1>{place} fuel prices today</h1>",
                f'<p class="lead">On {esc(self.day)} the median price of {esc(NAME[f0])} in Sydney is <b>{c1(r["now"])}c/L</b>. '
                f"Bowser tracks {len(self.st):,} service stations in {len(self.subs):,} suburbs{' across NSW and the ACT' if nsw else ''} using NSW FuelCheck prices, "
                "and for Sydney tells you whether to fill up now or wait.</p>",
                self.verdict_card(f0, up)]
        cards = []
        for f in FUELS:
            if f not in self.live: continue
            x = self.live[f]; d7 = x["d7"]
            trend = "steady this week" if abs(d7) < 1 else f"{'up' if d7 > 0 else 'down'} about {cents(d7)} in a week"
            cards.append(f'<a class="card" href="{FSLUG[f]}/"><span class="eyebrow">{esc(NAME[f])}</span><span class="big">{c1(x["now"])}<small>c/L</small></span>'
                         f'<span class="small">Sydney median · expected {trend}</span></a>')
        body += ["<h2>Today’s Sydney price for each fuel</h2>", '<div class="grid">' + "".join(cards) + "</div>"]
        top = self.cheapest(syd, f0, 15)
        if top:
            body += ["<h2>Cheapest petrol in Sydney today</h2>", f"<p>The 15 cheapest {esc(NAME[f0])} prices in Sydney right now, with every other fuel each station sells.</p>",
                     self.price_table(top, sort=f0, up=up)]
        body.append(f'<div class="row"><a class="btn" href="{up}" data-cta="hub-map">Open the live map</a><a href="{up}fuel-price-forecast/">See the 14-day forecast</a></div>')
        if self.regions:
            rows = []
            for n in sorted(self.regions):
                pool = self.regions[n]; m = self.median(pool, f0); c = self.cheapest(pool, f0, 1)
                rows.append(f'<tr><td><a href="{up}{esc(self.region_url[n])}">{esc(n)}</a></td><td class="n">{len(pool)}</td><td class="n">{c1(m) if m is not None else "–"}</td>'
                            f'<td class="n">{c1(c[0]["p"][f0][0]) if c else "–"}</td></tr>')
            body += self.canberra_block(f0, up)
            body += ["<h2>Fuel prices outside Sydney (NSW and ACT)</h2>" if self.act else "<h2>Fuel prices by region</h2>",
                     f"<p>Today’s {esc(NAME[f0])} price in the main centres outside Sydney. Bowser’s forecast is built from Sydney prices and covers Sydney only, so these are today’s prices without a call.</p>",
                     '<div class="scroll"><table><thead><tr><th>Region</th><th class="n">Stations</th><th class="n">Median U91</th><th class="n">Cheapest U91</th></tr></thead><tbody>'
                     + "".join(rows) + "</tbody></table></div>"]
        qa = []
        if top:
            where = top[0]["sub"][0] if top[0]["sub"] else top[0]["s"]
            qa.append(("What is the cheapest petrol in Sydney today?",
                       f"On {self.day} the cheapest {NAME[f0]} in Sydney is {c1(top[0]['p'][f0][0])} cents a litre at {top[0]['name']} in {where}, "
                       f"{cents(r['now'] - top[0]['p'][f0][0])} under the Sydney median of {c1(r['now'])} cents. Members-only sites and prices over a week old are not counted."))
        qa.append(("Will petrol prices in Sydney go up or down this week?", f"{self.outlook(f0)} Bowser’s call today is: {(v or 'no call').lower()}."))
        if CANBERRA in self.regions:
            qa.append(("Does Bowser forecast Canberra prices?", NO_CBR_FORECAST))
        qa.append(("Where do these fuel prices come from?",
                   "From NSW FuelCheck, the NSW Government’s fuel price service. Every NSW service station must report its prices to it, and it also lists "
                   "ACT service stations that report to it. Bowser reads those prices several times a day and adds a forecast for Sydney. "
                   "Bowser is independent and not part of the NSW Government."))
        fq, fq_ld = self.faq(qa); body.append(fq)
        letters = {}
        for k in sorted(self.subs): letters.setdefault(k[0][0].upper() if k[0][0].isascii() and k[0][0].isalpha() else "#", []).append(k)
        body += ["<h2>Fuel prices by suburb</h2>", '<div class="az">' + "".join(f'<a href="#az-{slug(l) or "other"}">{esc(l)}</a>' for l in letters) + "</div>"]
        for l, ks in letters.items():
            body.append(f'<h3 id="az-{slug(l) or "other"}">{esc(l)}</h3><ul class="cols">' + "".join(
                f'<li><a href="{up}{esc(self.sub_url[k])}">{esc(k[0])}</a> <span class="small">{k[1]}</span></li>' for k in ks) + "</ul>")
        body.append(self.sources_p())
        ld = [{"@context": "https://schema.org", "@type": "Dataset", "name": f"{place} service station fuel prices and Sydney price forecast",
               "description": f"Daily fuel prices for {place} service stations from NSW FuelCheck, with Bowser’s 14-day forecast of the Sydney median price for five fuels.",
               "url": f"{self.site}/fuel-prices/", "license": "https://creativecommons.org/licenses/by-sa/3.0/au/", "isAccessibleForFree": True,
               "dateModified": self.asof, "spatialCoverage": "New South Wales and the Australian Capital Territory, Australia" if nsw else "Sydney, New South Wales, Australia",
               "creator": {"@type": "Organization", "name": "Bowser", "url": self.site + "/", **({"areaServed": STATES} if self.act else {})},
               "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{self.site}/api/v1/stations.json"}]}, fq_ld]
        self.page("fuel-prices/", "hub", "/fuel-prices/", title, desc, "\n".join(body), crumbs=[("Fuel prices", "fuel-prices/")], ld=ld, priority=1.0)

    def is_act(self, s):
        return state_of(s.get("pc"), s.get("st")) == "ACT"

    def district(self, s):
        """The Canberra page's section for a station of the Canberra region: its ACT district by postcode, or the NSW side."""
        if not self.is_act(s): return NSW_SIDE
        return next((n for n, pcs in DISTRICTS if s.get("pc") in pcs), ACT_OTHER)

    def cbr_districts(self):
        """(the Canberra page's lead fuel, {district: (its 5 cheapest, its station count)}) for the sections that page builds."""
        if not hasattr(self, "_cbr"):
            pool = self.regions.get(CANBERRA) or []
            f0 = next((f for f in FUELS if self.cheapest(pool, f, 1)), None); groups = {}
            for s in pool: groups.setdefault(self.district(s), []).append(s)
            secs = {}
            for d in [n for n, _ in DISTRICTS] + [ACT_OTHER, NSW_SIDE]:
                five = self.cheapest(groups.get(d, []), f0, 5) if f0 else []
                if five: secs[d] = (five, len(groups[d]))
            self._cbr = (f0, secs)
        return self._cbr

    def canberra_block(self, f0, up):
        """The hub's Canberra section (id="canberra", for "act fuel prices"): median, cheapest, the gap to Sydney, the link."""
        pool = self.regions.get(CANBERRA)
        if not pool: return []
        top = self.cheapest(pool, f0, 1); m = self.median(pool, f0); r = self.live.get(f0)
        if not top: return []
        t = top[0]; where = t["sub"][0] if t["sub"] else t["s"]
        txt = (f"The cheapest {esc(NAME[f0])} in Canberra and Queanbeyan today is <b>{c1(t['p'][f0][0])}c/L</b> at "
               f'<a href="{up}{esc(t["url"])}">{esc(t["name"])}</a> in {esc(where)}.')
        if m is not None:
            txt += f" The median there is {c1(m)}c"
            if r and num(r.get("now")):
                g = m - r["now"]
                txt += ", about the same as Sydney" if abs(g) < 0.5 else f", {cents(g)} {'under' if g < 0 else 'over'} Sydney’s {c1(r['now'])}c"
            txt += "."
        txt += (" These are ACT stations that report to NSW FuelCheck, plus Queanbeyan. Bowser’s forecast covers Sydney only, so for Canberra you get today’s prices. "
                f'<a href="{up}{esc(self.region_url[CANBERRA])}">See every Canberra and Queanbeyan station by district</a>.')
        return ['<h2 id="canberra">Canberra and ACT fuel prices</h2>', f"<p>{txt}</p>"]

    def region(self, name):
        """A regional centre outside Sydney: its median, its cheapest stations and its suburbs. Prices only, no forecast."""
        up = "../../"; pool = self.regions[name]; path = self.region_url[name]
        f0 = next((f for f in FUELS if self.cheapest(pool, f, 1)), None)
        if not f0: return
        top = self.cheapest(pool, f0, 20); m = self.median(pool, f0); syd = self.live.get(f0)
        cbr = name == CANBERRA; tn = REGION_TITLE.get(name, name)
        title = f"{tn} fuel prices today: {SHORT[f0] if f0 != 'DL' else 'diesel'} from {c1(top[0]['p'][f0][0])}c | Bowser"
        if len(title) > 65: title = f"{tn} fuel prices today | Bowser"
        if cbr:   # leads with "Canberra", says how it sits against Sydney, and what is compared (ACT stations that report, and Queanbeyan)
            vs = ""
            if m is not None and syd and num(syd.get("now")):
                g = m - syd["now"]; vs = " (about Sydney’s)" if abs(g) < 0.5 else f" ({cents(g)} {'under' if g < 0 else 'over'} Sydney)"
            tail = (f", median {c1(m)}c{vs}" if m is not None else "") + f". {len(pool)} ACT and Queanbeyan stations compared."
            lead = lambda fuel: f"Canberra petrol prices for {self.sday}: {fuel} from {c1(top[0]['p'][f0][0])}c"
            # the full fuel name, then the short one ("U91"), then without the station; the end is cut only as a last resort
            desc = next((d for d in (f"{lead(NAME[f0])} at {top[0]['name']}{tail}", f"{lead(SHORT[f0])} at {top[0]['name']}{tail}") if len(d) <= 155),
                        clip(lead(NAME[f0]) + tail, 155))
        else:
            desc = clip(f"Petrol prices in {name} for {self.sday}: {NAME[f0]} from {c1(top[0]['p'][f0][0])}c/L at {top[0]['name']}"
                        + (f", median {c1(m)}c" if m is not None else "") + f". Compare {len(pool)} stations, from NSW FuelCheck data.")
        lead = (f"The cheapest {esc(NAME[f0])} in {esc(name)} today is <b>{c1(top[0]['p'][f0][0])}c/L</b> at "
                f'<a href="{up}{esc(top[0]["url"])}">{esc(top[0]["name"])}</a>'
                + (f" (unchanged since {esc(self.since(top[0]['p'][f0][1]))})." if self.held(top[0], f0) else "."))
        if m is not None:
            priced = sum(self.fresh(s, f0) and not s.get("m") for s in pool)
            lead += f" The median across {priced} stations with a current price is {c1(m)}c"
            if syd and num(syd.get("now")):
                g = m - syd["now"]
                lead += ", about the same as Sydney" if abs(g) < 0.5 else f", {cents(g)} {'under' if g < 0 else 'over'} Sydney’s {c1(syd['now'])}c"
            lead += "."
        body = [f"<h1>{esc(name)} fuel prices today</h1>", f'<p class="lead">{lead}</p>', self.fuel_cards(pool, up, False),
                f"<h2>The {len(top)} cheapest {esc(NAME[f0])} stations in {esc(name)}</h2>", self.price_table(top, sort=f0, up=up),
                '<p class="small">Members-only sites and prices not updated for three weeks or more are left out of this list. Prices outside Sydney change less often, '
                "so a price a week or two old is often still current.</p>"]
        if m is not None and len(top) > 1:
            body.append(f"<p>On a {TANK} L tank, filling at the cheapest station instead of a typical one saves about ${TANK * (m - top[0]['p'][f0][0]) / 100:.2f} today.</p>")
        ld, qa = [], []
        if cbr:
            act = [s for s in pool if self.is_act(s)]; nsw = [s for s in pool if not self.is_act(s)]
            ma, mn = self.median(act, f0), self.median(nsw, f0)
            if ma is not None and mn is not None:
                g = mn - ma
                body.append(f"<p>ACT stations’ median {esc(NAME[f0])} today is {c1(ma)}c; across the border in Queanbeyan and surrounds (NSW) it is {c1(mn)}c, "
                            + ("about the same." if abs(g) < 0.5 else f"{cents(g)} {'less' if g < 0 else 'more'} (${TANK * abs(g) / 100:.2f} on a {TANK} L tank).") + "</p>")
            secs = []
            for d, (five, n) in self.cbr_districts()[1].items():
                secs += [f'<h3 id="{slug(d)}">{esc(d)}</h3>',
                         f'<p class="small">The {len(five)} cheapest {esc(NAME[f0])} prices of {n} station{"s" if n != 1 else ""}.</p>',
                         self.price_table(five, sort=f0, up=up)]
            if secs:
                body += [f"<h2>Cheapest {esc(NAME[f0])} by Canberra district</h2>"] + secs
            where = top[0]["sub"][0] if top[0]["sub"] else top[0]["s"]
            qa = [("What is the cheapest petrol in Canberra today?",
                   f"On {self.day} the cheapest {NAME[f0]} in Canberra and Queanbeyan is {c1(top[0]['p'][f0][0])} cents a litre at {top[0]['name']} in {where}"
                   + (f", {cents(m - top[0]['p'][f0][0])} under the median of {c1(m)} cents" if m is not None and m - top[0]['p'][f0][0] >= 0.05 else "")
                   + ". Members-only sites and prices not updated for three weeks or more are not counted."),
                  ("Does Bowser forecast Canberra prices?", NO_CBR_FORECAST),
                  ("Where do Canberra fuel prices come from?",
                   "From NSW FuelCheck, the NSW Government’s fuel price service. It lists the ACT service stations that report to it, so a Canberra station that "
                   "doesn’t report isn’t shown. Bowser reads those prices several times a day.")]
            ld.append({"@context": "https://schema.org", "@type": "ItemList", "name": "Service stations in Canberra and Queanbeyan", "numberOfItems": len(pool),
                       "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": s["name"], "url": f"{self.site}/{s['url']}"}
                                           for i, s in enumerate(sorted(pool, key=lambda s: s["name"]))]})
        subs = sorted({s["sub"] for s in pool if s["sub"]})
        if subs:
            body += [f"<h2>Fuel prices by suburb in {esc(name)}</h2>", '<ul class="cols">' + "".join(
                f'<li><a href="{up}{esc(self.sub_url[k])}">{esc(self.sub_label[k])}</a></li>' for k in subs) + "</ul>"]
        body += [f"<h2>Should you fill up in {esc(name)} today?</h2>",
                 f"<p>Bowser’s fill-or-wait forecast is fitted on Sydney prices and doesn’t cover {esc(name)}, so this page shows today’s prices without a call. "
                 "Without a forecast, the saving is in comparing stations rather than picking the day. "
                 f'For Sydney, see the <a href="{up}fuel-price-forecast/">fuel price forecast</a>.</p>']
        if qa:
            fq, fq_ld = self.faq(qa); body.append(fq); ld.append(fq_ld)
        body.append(self.sources_p())
        self.page(path, "region", "/fuel-prices/:region/", title, desc, "\n".join(x for x in body if x),
                  crumbs=[("Fuel prices", "fuel-prices/"), (name, path)], ld=ld, priority=0.9 if cbr else 0.8)

    def station_index(self):
        up = "../"
        groups = {}
        for s in self.st: groups.setdefault(s["sub"][0] if s["sub"] else "Other", []).append(s)
        place = "NSW and ACT" if self.any_out else "Sydney"
        body = [f"<h1>{place} service stations</h1>",
                f'<p class="lead">Every one of the {len(self.st):,} service stations Bowser tracks, by suburb. Each has today’s prices, and Sydney stations have their price history and a forecast.</p>']
        for g in sorted(groups, key=lambda g: (g == "Other", g)):
            body.append(f"<h3>{esc(g)}</h3><ul class=\"cols\">" + "".join(
                f'<li><a href="{up}{esc(s["url"])}">{esc(s["name"])}</a></li>' for s in sorted(groups[g], key=lambda s: s["name"])) + "</ul>")
        self.page("station/", "stations", "/station/", f"All {place} service stations and their fuel prices | Bowser",
                  f"Today’s fuel prices at all {len(self.st):,} {place} service stations Bowser tracks, listed by suburb, from NSW FuelCheck data.",
                  "\n".join(body), crumbs=[("Stations", "station/")], priority=0.4)

    def brand_pages(self):
        up = "../"; r = self.live.get("U91")
        rows = []
        for b in sorted(self.brand_url):
            pool = self.brands[b]; ps = [s["p"]["U91"][0] for s in pool if not s.get("out") and self.fresh(s, "U91") and not s.get("m")]
            f0 = self.brand_f0[b]; top = self.cheapest(pool, f0, 1, members=True)[0]
            rows.append((b, len(pool), sum(ps) / len(ps) if ps else None, f"{SHORT[f0]} {c1(top['p'][f0][0])}" + (" (members only)" if top.get("m") else "")))
        body = ["<h1>Fuel prices by brand</h1>",
                '<p class="lead">Which servo brands are cheapest in Sydney today? The average Unleaded 91 price at each brand, from NSW FuelCheck prices.</p>',
                '<div class="scroll"><table><thead><tr><th>Brand</th><th class="n">Stations</th><th class="n">Cheapest today</th><th class="n">Average U91</th><th class="n">vs median</th></tr></thead><tbody>'
                + "".join(f'<tr><td><a href="{slug(b)}/">{esc(b)}</a></td><td class="n">{n}</td><td class="n">{esc(low)}</td><td class="n">{f"{a:.1f}" if a else "–"}</td>'
                          + (f'<td class="n"><span class="{"cheap" if a < r["now"] else "dear"}">{"−" if a < r["now"] else "+"}{abs(a - r["now"]):.1f}</span></td>' if a and r else '<td class="n">–</td>')
                          + "</tr>" for b, n, a, low in sorted(rows, key=lambda t: (t[2] is None, t[2] or 0))) + "</tbody></table></div>",
                '<p class="small">The average leaves out members-only sites and prices over a week old; brands without an Unleaded 91 average are listed last.</p>',
                "<p>Brand averages hide a lot: the cheapest and dearest stations of the same brand are often 20c apart, so check the station, not the sign.</p>", self.sources_p()]
        self.page("brands/", "brands", "/brands/", "Cheapest petrol brands in Sydney today | Bowser",
                  f"Average fuel price by brand in Sydney for {self.sday}: 7-Eleven, Ampol, BP, Shell, Metro, Costco and more, with each brand’s cheapest price and every station.",
                  "\n".join(body), crumbs=[("Brands", "brands/")], priority=0.6)
        up = "../../"
        for b, path in self.brand_url.items():
            pool = self.brands[b]; f0 = self.brand_f0[b]; indep = b.lower() == "independent"
            at_b = "an independent station" if indep else b
            top = self.cheapest(pool, f0, 1, members=True)[0]
            ps = [s["p"][f0][0] for s in pool if self.fresh(s, f0) and self.reg(s, f0)] or [s["p"][f0][0] for s in pool if self.fresh(s, f0)]   # all premium: its own
            avg = sum(ps) / len(ps); x = self.live.get(f0)
            sp_ = [s["p"][f0][0] for s in pool if self.fresh(s, f0) and not s.get("out") and self.reg(s, f0)]   # the Sydney ones: only they compare with the Sydney median
            title = f"{b} fuel prices today: {SHORT[f0] if f0 != 'DL' else 'diesel'} from {c1(top['p'][f0][0])}c | Bowser"
            if len(title) > 65: title = f"{b} fuel prices today | Bowser"
            desc = clip(f"{b} petrol prices for {self.sday} at {len(pool)} stations: {NAME[f0]} from {c1(top['p'][f0][0])}c/L at {top['name']}, "
                        f"average {avg:.1f}c. Every station’s price" + (", and whether to fill up or wait." if x and len(sp_) >= 3 else ", from NSW FuelCheck data."))
            lead = (f"The cheapest {esc(NAME[f0])} at {esc(at_b)} today is <b>{c1(top['p'][f0][0])}c/L</b> at "
                    f'<a href="{up}{esc(top["url"])}">{esc(top["name"])}</a>. Across the {len(ps)} {"independent" if indep else esc(b)} {"station" if len(ps) == 1 else "stations"} with a current price the average is {avg:.1f}c')
            if x and len(sp_) >= 3:
                g = sum(sp_) / len(sp_) - x["now"]
                lead += (f". The {len(sp_)} in Sydney average {sum(sp_) / len(sp_):.1f}c, "
                         f"{'about the same as' if abs(g) < 0.5 else cents(g) + (' under' if g < 0 else ' over')} the Sydney median of {c1(x['now'])}c")
            body = [f"<h1>{esc(b)} fuel prices today</h1>", f'<p class="lead">{lead}.</p>', self.fuel_cards(pool, up, False)]
            if all(s.get("m") for s in pool): body.append(f"<p>{esc(b)} fuel is for members only: you need a membership card to fill up.</p>")
            extra_ld = []
            if slug(b) == "costco":
                body.append(self.costco_note(pool, f0, up)); extra_ld = self.costco_faq(pool, f0)
                # an ACT Costco with a current U91 price (Canberra Airport, the only Costco selling U91): one line and the Canberra page
                act_u91 = self.cheapest([s for s in pool if s.get("out") and self.is_act(s)], "U91", 1, members=True)
                if act_u91 and CANBERRA in self.regions:
                    t = act_u91[0]
                    body.append(f'<p><a href="{up}{esc(t["url"])}">{esc(t["name"])}</a> in the ACT also sells Unleaded 91: {c1(t["p"]["U91"][0])}c/L today. '
                                f'Compare it with <a href="{up}{esc(self.region_url[CANBERRA])}">Canberra fuel prices</a>.</p>')
            if x and len(sp_) >= 3: body.append(self.verdict_card(f0, up))
            body += [f"<h2>All {esc(b)} stations, cheapest first</h2>", self.price_table(pool, sort=f0, up=up),
                     f'<p>Compare with <a href="../">other brands</a> or see the <a href="{up}fuel-prices/{FSLUG[f0]}/">cheapest {esc(NAME[f0])} in Sydney</a>.</p>',
                     "" if indep else f'<p class="small">{esc(b)} is a trade mark of its owner. Bowser is independent and not affiliated with {esc(b)}.</p>', self.sources_p()]
            if extra_ld: body.insert(-1, extra_ld[0])
            self.page(path, "brand", "/brands/:brand/", title, desc, "\n".join(x for x in body if x), crumbs=[("Brands", "brands/"), (b, path)],
                      ld=extra_ld[1:], priority=0.7)

    def guides(self):
        up = "../"; S = self.stats; live = self.live
        art = lambda path, head, desc: [{"@context": "https://schema.org", "@type": "Article", "headline": head, "description": desc,
                                         "datePublished": PUBLISHED, "dateModified": self.asof, "mainEntityOfPage": f"{self.site}/{path}", "image": f"{self.site}/og.png",
                                         "author": {"@type": "Organization", "name": "Bowser", "url": self.site + "/"},
                                         "publisher": {"@type": "Organization", "name": "Bowser", "url": self.site + "/"}}]
        # ---- forecast
        r = live.get("U91") or next(iter(live.values())); v = (r.get("verdict") or {}).get("head", "")
        rows = "".join(
            f'<tr><td><a href="{up}fuel-prices/{FSLUG[f]}/">{NAME[f]}</a></td><td class="n">{c1(x["now"])}</td>'
            + "".join(f'<td class="n">{c1(x["now"] + x[k])}</td>' for k in ("d3", "d7", "d14"))
            + f'<td class="n">{x["now"] + x["lo7"]:.0f}–{x["now"] + x["hi7"]:.0f}</td><td><span class="chip {TONE.get((x.get("verdict") or {}).get("cls"), "calm")}">{esc((x.get("verdict") or {}).get("head", ""))}</span></td></tr>'
            for f, x in ((f, live[f]) for f in FUELS if f in live))
        d7 = r["d7"]; f0 = r["fuel"]; N0 = NAME[f0]; today = dt.date.fromisoformat(self.fc_asof)
        ans = ("stay about where they are" if abs(d7) < 1 else f"{'rise' if d7 > 0 else 'fall'} by about {cents(d7)} a litre")
        head = "Sydney fuel price forecast: will petrol go up or down this week?"
        body = [f"<h1>{head}</h1>",
                f'<p class="lead">As of {esc(self.day)}, Bowser predicts the Sydney median {esc(N0)} price will <b>{ans}</b> over the next week. Today’s call: <b>{esc(v.lower())}</b>.</p>',
                f'<p class="small">Updated {esc(self.day)}. The forecast is rebuilt about five times a day from the latest NSW FuelCheck prices.</p>',
                self.verdict_card(f0, up)]
        fc_chart = self.forecast_chart(f0)
        if fc_chart: body += [f"<h2>Sydney {esc(N0)} price: recent weeks and the next 14 days</h2>", fc_chart]
        body += ["<h2>The 14-day outlook for each fuel</h2>",
                 '<div class="scroll"><table><thead><tr><th>Fuel</th><th class="n">Today</th><th class="n">In 3 days</th><th class="n">In 7 days</th><th class="n">In 14 days</th><th class="n">7-day range</th><th>Call</th></tr></thead><tbody>'
                 + rows + "</tbody></table></div>",
                 '<p class="small">Sydney median prices in cents a litre. The range is where Bowser expects the price to land about 8 times in 10.</p>']
        pj = r.get("p_jump7")
        if num(pj):
            body.append(f"<p>The chance of a sharp jump (5c or more) in the Sydney {esc(N0)} median within a week is "
                        f"<b>{'under 5%' if pj < 0.05 else f'about {pj:.0%}'}</b>. "
                        + ("Sydney prices rise in sudden jumps and fall slowly, so this number matters more than the average move: when it is high, fill up before the jump."
                           if pj >= 0.35 else "Sydney prices rise in sudden jumps and fall slowly; while this number stays low, waiting usually pays.") + "</p>")
        if abs(d7) >= 1:
            verb = "waiting a week instead of filling today saves" if d7 < 0 else "filling today instead of in a week saves"
            body += ["<h2>What the timing is worth on your tank</h2>",
                     f"<p>If the forecast is right, {verb} about this much on {esc(N0)} at the Sydney median price:</p>",
                     '<div class="scroll"><table><thead><tr><th>Tank</th><th class="n">Saving</th></tr></thead><tbody>'
                     + "".join(f'<tr><td>{L} litres</td><td class="n">${L * abs(d7) / 100:.2f}</td></tr>' for L in (30, 50, 70, 100)) + "</tbody></table></div>"]
            if num(S.get("shop_around")):
                body.append(f'<p class="small">Picking the station often saves more than picking the day: the cheapest tenth of Sydney stations are typically {S["shop_around"]:.0f}c under the median, '
                            f'about ${TANK * S["shop_around"] / 100:.2f} on a {TANK} L tank. <a href="{up}fuel-prices/">Find them by suburb</a>.</p>')
        tr = (self.track.get("replay") or {}).get("U91") or {}; lv = (self.track.get("live") or {}).get("U91") or {}
        ok = lambda d, *ks: isinstance(d, dict) and all(num(d.get(k)) for k in ("n", "right", "close", "wrong")) and all(isinstance(d.get(k), str) for k in ks)
        if not ok(tr, "from", "to") or not (isodate(tr["from"]) and isodate(tr["to"])): tr = {}
        if not ok(lv, "since") or not isodate(lv["since"]): lv = {}
        body.append("<h2>How accurate is the forecast?</h2>")
        if tr.get("n"):
            body.append(f"<p>Replayed over every day from {esc(short_date(tr['from']))} {tr['from'][:4]} to {esc(short_date(tr['to']))} {tr['to'][:4]}, using only the data available "
                        f"on each day, Bowser’s fill-or-wait call for Unleaded 91 was right <b>{tr['right'] / tr['n']:.0%}</b> of the time ({tr['right']:,} of {tr['n']:,} calls), "
                        f"close on {tr['close'] / tr['n']:.0%} and wrong on {tr['wrong'] / tr['n']:.0%}."
                        + (f" Since the calls went live on {esc(short_date(lv['since']))}, {lv['right']} of {lv['n']} scored calls were right and {lv['wrong']} wrong." if lv.get("n") else "") + "</p>")
        body += ["<p>The forecast is tested the hard way: each month since January 2021 was forecast using only the data before it, including the 2022 and 2026 oil shocks. "
                 + (f'See <a href="{up}fuel-price-forecast/accuracy/">the full track record</a>, year by year and against the simplest guess, or the call-by-call record on the '
                    f'<a href="{up}" data-cta="forecast-track">dashboard</a>.</p>' if self.has_acc else
                    f'The full record, call by call, is on the <a href="{up}" data-cta="forecast-track">dashboard</a>.</p>'),
                 "<h2>How the forecast works</h2>",
                 "<ul><li><b>What it predicts:</b> how the Sydney median price of each fuel will move over the next 1, 3, 7 and 14 days, and the chance of a jump of 5c or more within a week.</li>"
                 "<li><b>What it looks at:</b> how far pump prices sit above the wholesale price compared with the past year, recent wholesale moves, the oil price in Australian dollars, "
                 "how spread out station prices are, and where Sydney is in its price cycle.</li>"
                 "<li><b>How it learns:</b> a machine-learning model trained on Sydney prices for all five fuels since 2019, with a separate model for price jumps.</li>"
                 "<li><b>Each station gets its own call:</b> some stations lead a price jump and some follow days later, and a few hardly move at all. Bowser adjusts the Sydney forecast for how each station usually behaves.</li>"
                 "<li><b>Limits:</b> it reacts to oil and wholesale moves as they happen, but it can’t see wars, OPEC decisions or excise changes coming.</li></ul>",
                 "<h2>When is the best time to buy petrol in Sydney?</h2>",
                 f'<p>Just before a jump, at the bottom of the <a href="{up}petrol-price-cycle/">price cycle</a>. The day of the week barely matters in Sydney'
                 + (f": across the calm years the average gap between the cheapest and dearest weekday is about {max(S['dow']) - min(S['dow']):.1f}c" if self.has_best else "")
                 + (f' (<a href="{up}best-day-to-buy-petrol/">the numbers for each day</a>)' if self.has_best else "")
                 + ". Where you fill matters more than when"
                 + (f": the cheapest tenth of Sydney stations are typically {S['shop_around']:.0f}c under the median" if num(S.get("shop_around")) else "")
                 + f'. Check <a href="{up}fuel-prices/">today’s cheapest stations by suburb</a>.</p>']
        if self.xmas and today.month in (11, 12, 1):
            body.append(f'<p>Planning a holiday drive? See <a href="{up}petrol-prices-christmas/">what Sydney petrol prices did over each Christmas since {self.xmas[0]["year"]}</a>.</p>')
        try:
            body += self.last_week(up)
        except Exception as e:   # the forecast page goes out without the block rather than not at all
            print(f"seo_pages: WARNING last week's outlook block skipped: {type(e).__name__}: {e}")
        # Questions people ask a search engine, answered with today's numbers (shown on the page and as FAQPage data)
        qa = [("Will petrol prices go up or down this week in Sydney?", f"{self.outlook(f0)} Bowser’s call today: {(v or 'no call').lower()}.")]
        if all(num(r.get(k)) for k in ("d1", "lo1", "hi1")):
            qa.append(("Will petrol go up tomorrow in Sydney?",
                       f"Bowser expects the Sydney median for {N0} to be about {c1(r['now'] + r['d1'])}c a litre tomorrow, likely between {r['now'] + r['lo1']:.0f}c and {r['now'] + r['hi1']:.0f}c"
                       + (f", with about a {pj:.0%} chance of a 5c-plus jump within a week." if num(pj) and pj >= 0.05 else ", and the chance of a 5c-plus jump within a week is under 5%." if num(pj) else ".")))
        qa.append(("Is it worth waiting to buy petrol this week?",
                   f"Bowser’s call for Sydney today is: {(v or 'no call').lower()}. "
                   + ("Prices are expected to keep easing, so if you have enough fuel, waiting a few days should be cheaper." if d7 <= -1 else
                      "Prices are expected to rise, so filling now should beat waiting." if d7 >= 1 else
                      "Little change is expected this week, so fill when it suits you and pick a cheap station.")
                   + " Each station page on Bowser also has its own call, based on how that station usually prices."))
        if num(r.get("d14")):   # "when will petrol go down sydney" (autocomplete, Nov 2026): answered here, not on a page of its own
            d14 = r["d14"]
            if d7 <= -1:
                down = (f"Prices are already easing: Bowser expects the Sydney median for {N0} to fall about {cents(d7)} over the next week, to about {c1(r['now'] + d7)}c"
                        + (f", and about {cents(d14)} over two weeks." if d14 < d7 else "."))
            elif d7 >= 1:
                down = (f"Not this week: Bowser expects the Sydney median for {N0} to rise about {cents(d7)} over the next week. "
                        "After a rise, Sydney prices usually ease slowly over the weeks that follow.")
            else:
                down = (f"Little change is expected this week: Bowser puts the Sydney median for {N0} within about a cent of today’s {c1(r['now'])}c in 7 days"
                        + (f", and about {cents(d14)} {'lower' if d14 < 0 else 'higher'} in two weeks." if abs(d14) >= 1 else "."))
            qa.append(("When will petrol go down in Sydney?", down))
        cs = self.cycle_status()
        if cs: qa.append(("Is the Sydney petrol price cycle still running?", cs))
        if tr.get("n"):
            base = tr.get("base") if isinstance(tr.get("base"), dict) else {}
            qa.append(("How accurate is Bowser’s fuel price forecast?",
                       f"Replayed on every day from {tr['from'][:4]} to {tr['to'][:4]} using only the data available at the time, the fill-or-wait call for Unleaded 91 was right {tr['right'] / tr['n']:.0%} of the time"
                       + (f", against {base['right'] / tr['n']:.0%} for always giving the same call" if num(base.get("right")) else "") + ". Every live call is scored a week later, in public."))
        fq, fq_ld = self.faq(qa); body += [fq, self.sources_p()]
        # "this week" and "tomorrow" are what people type (autocomplete, Nov 2026); "should you fill up today" stays the dashboard's
        t = "Will petrol go up this week? Sydney fuel price forecast | Bowser"
        d = (f"Petrol price prediction for Sydney, updated {self.sday}: {N0} is {c1(r['now'])}c/L and expected to {ans} in 7 days. "
             f"Bowser’s call: {v.lower()}. 14-day outlook for every fuel.")
        ds = {"@context": "https://schema.org", "@type": "Dataset", "name": "Sydney fuel price forecast",
              "description": "Bowser’s forecast of the Sydney median price of five fuels 1, 3, 7 and 14 days ahead, with a likely range and the chance of a price jump. Rebuilt about five times a day from NSW FuelCheck prices.",
              "url": f"{self.site}/fuel-price-forecast/", "isAccessibleForFree": True, "dateModified": self.asof,
              "temporalCoverage": f"{self.fc_asof}/{(today + dt.timedelta(days=14)).isoformat()}", "spatialCoverage": "Sydney, New South Wales, Australia",
              "creator": {"@type": "Organization", "name": "Bowser", "url": self.site + "/"},
              "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{self.site}/api/v1/forecast.json"}]}
        self.page("fuel-price-forecast/", "forecast", "/fuel-price-forecast/", t, d, "\n".join(body), crumbs=[("Forecast", "fuel-price-forecast/")],
                  ld=art("fuel-price-forecast/", head, d) + [ds, fq_ld], priority=1.0)

        # ---- price cycle
        body = ["<h1>The Sydney petrol price cycle, and where it is now</h1>"]
        last = S.get("last_restore"); gap, amp = S.get("cycle_gap_calm"), S.get("cycle_amp_calm")
        if not self.stage(): last = None                 # missing or unreadable: no "days since" anywhere on the page
        if last and num(gap):
            since = (today - dt.date.fromisoformat(last)).days
            body.append(f'<p class="lead">Sydney’s last big price jump began on <b>{esc(short_date(last))}</b>, {since} days ago. In normal years a jump comes about every <b>{gap:.0f} days</b>'
                        + (f" and lifts Unleaded 91 by about <b>{amp:.0f}c</b> a litre" if num(amp) else "") + ".</p>")
        body.append(f'<p class="small">Updated {esc(self.day)}.</p>')
        body.append(self.stage_card() or (self.verdict_card("U91", up) if "U91" in live else ""))
        if self.stage() and "U91" in live: body.append(f"<p>{esc(self.outlook('U91'))} Bowser’s call today: <b>{esc(v.lower())}</b>. "
                                                      f'See the <a href="{up}fuel-price-forecast/">full forecast</a>.</p>')
        body += ["<h2>What is the petrol price cycle?</h2>",
                 "<p>In Sydney, petrol prices don’t drift up and down with the oil price from day to day. They move in a saw-tooth: prices jump sharply over a day or two, "
                 "often by 30c a litre or more, then slide down a little each day for several weeks until the next jump. The ACCC, which monitors fuel prices, has found the same pattern in "
                 "Australia’s largest cities, and that the cycles come from retailers’ pricing decisions rather than from changes in wholesale costs.</p>",
                 "<p>For drivers the rule is simple: <b>fill up near the bottom, just before the jump, and buy as little as you can near the top</b>. The hard part is knowing when the jump is coming, "
                 f'because the cycle doesn’t keep to a timetable. That is what <a href="{up}fuel-price-forecast/">Bowser’s forecast</a> is for.</p>']
        rj = self.jumps()
        if rj:
            cs = self.cycle_status()
            left = lambda j: f"{j['gap']:.0f}" if num(j.get("gap")) else f"{(today - dt.date.fromisoformat(j['date'])).days} so far"
            body += ["<h2>Is the Sydney price cycle still running?</h2>",
                     (f"<p>{esc(cs)}</p>" if cs else "")
                     + "<p>The latest jumps in the Sydney Unleaded 91 median. Bowser counts a jump when the median rises 8c or more in three days, so a one-off rise, "
                     "such as a change in fuel excise or an oil price spike, can appear here too.</p>",
                     '<div class="scroll"><table><thead><tr><th>Jump began</th><th class="n">Size (c/L)</th><th class="n">Days to the next jump</th></tr></thead><tbody>'
                     + "".join(f'<tr><td>{esc(short_date(j["date"]))} {j["date"][:4]}</td><td class="n">{j["amp"]:.0f}</td>'
                               f'<td class="n">{left(j)}</td></tr>'
                               for j in reversed(rj[-8:])) + "</tbody></table></div>"]
        cy = [c for c in (S.get("cycles_by_year") or []) if num(c.get("gap")) and num(c.get("amp"))]
        if cy:
            body += ["<h2>How long is the Sydney price cycle?</h2>",
                     "<p>It changes from year to year. This table counts the big jumps in the Sydney Unleaded 91 median each year, the typical gap between them and the typical size of the jump.</p>",
                     '<div class="scroll"><table><thead><tr><th>Year</th><th class="n">Price jumps</th><th class="n">Typical days between</th><th class="n">Typical jump (c/L)</th></tr></thead><tbody>'
                     + "".join(f'<tr><td>{c["year"]}{" (so far)" if str(c["year"]) == self.asof[:4] else ""}</td><td class="n">{c["n"]}</td><td class="n">{c["gap"]:.0f}</td><td class="n">{c["amp"]:.0f}</td></tr>' for c in cy)
                     + "</tbody></table></div>"]
        if self.has_best:
            dow = S["dow"]; lo_d, hi_d = DOW[dow.index(min(dow))], DOW[dow.index(max(dow))]
            body += ["<h2>Is there a cheapest day of the week?</h2>",
                     f"<p>Not in Sydney, not any more. Averaged over the calm years since 2019, {lo_d} is the cheapest day and {hi_d} the dearest, but the gap is only about "
                     f"<b>{max(dow) - min(dow):.1f}c a litre</b>: about {TANK * (max(dow) - min(dow)) / 100 * 100:.0f} cents on a {TANK} L tank. With a cycle several weeks long, where prices are in the cycle "
                     f'matters far more than the day of the week. <a href="{up}best-day-to-buy-petrol/">The figures for every day</a>.</p>']
        if num(S.get("shop_around")):
            body += ["<h2>Stations don’t all jump together</h2>",
                     "<p>When a jump starts, some stations lift their price within hours and others hold the old price for days. A few, such as Costco, hardly follow the cycle at all. "
                     f"So even at the top of the cycle there are cheap stations to find: the cheapest tenth of Sydney stations typically sit {S['shop_around']:.0f}c under the median. "
                     f'<a href="{up}fuel-prices/">See today’s cheapest stations by suburb</a>.</p>']
        if num(S.get("low_2019")) and num(S.get("high_all")) and S.get("high_date"):
            body.append(f"<p>For scale: since 2019 the Sydney Unleaded 91 median has been as low as {S['low_2019']:.1f}c and as high as {S['high_all']:.1f}c "
                        f"(on {esc(short_date(S['high_date']))} {S['high_date'][:4]}).</p>")
        body += ["<h2>Do other fuels follow the cycle?</h2>",
                 "<p>E10, Premium 95 and Premium 98 move with Unleaded 91, a fixed step above or below it at most stations. Diesel does not cycle: it has no sudden jumps and slow slides. It follows the wholesale price, "
                 f'which can still carry it a long way over a few weeks when oil moves. See the <a href="{up}fuel-prices/diesel/">Sydney diesel price</a> and today’s call for it.</p>',
                 f'<p class="small">Run a local news or community site? <a href="{up}badge/">Show where Sydney is in the cycle on it</a>, free, with a small image that updates itself.</p>', self.sources_p()]
        t = "Sydney petrol price cycle today: where are we now? | Bowser"
        d = (f"Where Sydney is in its petrol price cycle on {self.sday}"
             + (f": the last jump began {short_date(last)}, and jumps come about every {gap:.0f} days" if last and num(gap) else "")
             + ". How the cycle works, how long it lasts, and when to fill up.")
        self.page("petrol-price-cycle/", "cycle", "/petrol-price-cycle/", t, d, "\n".join(body), crumbs=[("Price cycle", "petrol-price-cycle/")],
                  ld=art("petrol-price-cycle/", "The Sydney petrol price cycle, and where it is now", d), priority=0.9)

        # ---- NSW FuelCheck
        body = ["<h1>Bowser and NSW FuelCheck: what each one does</h1>",
                '<p class="lead">FuelCheck is the NSW Government’s fuel price service. Every service station in NSW must report its prices to it, so it is the source of truth for what fuel costs right now. '
                "It also lists ACT service stations that report to it. "
                "Bowser is an independent site built on that data: it shows the same prices and adds a forecast of where they are heading.</p>",
                "<h2>What is NSW FuelCheck?</h2>",
                "<p>FuelCheck is run by NSW Fair Trading. Under NSW law, service stations must report the price of every fuel they sell to FuelCheck whenever it changes, so the prices are the station’s own, not estimates or reports from other drivers. "
                'You can use it at <a href="https://www.fuelcheck.nsw.gov.au/" rel="noopener">fuelcheck.nsw.gov.au</a> or in the FuelCheck app, and the same data is published for others to build on, which is how Bowser gets it.</p>',
                "<p>If a station’s price at the pump doesn’t match what FuelCheck shows, you can report it to NSW Fair Trading through FuelCheck.</p>",
                "<h2>What FuelCheck tells you, and what it doesn’t</h2>",
                "<p>FuelCheck answers <b>where is fuel cheapest right now?</b> It doesn’t answer the question that often saves more money: <b>should I fill up today, or will it be cheaper in a few days?</b> "
                f'In Sydney that matters, because prices move in a <a href="{up}petrol-price-cycle/">cycle</a> with jumps of 30c a litre or more.</p>',
                "<h2>What Bowser adds to FuelCheck prices</h2>",
                f'<ul><li><b>A fill-or-wait call</b> for Sydney each day, from a <a href="{up}fuel-price-forecast/">forecast</a> of the next 14 days.</li>'
                "<li><b>A call for each station</b>, based on how that station usually prices: whether it is early or late to follow a jump, and how it compares with the rest of Sydney.</li>"
                f'<li><b>Price history</b> for every station, and <a href="{up}fuel-prices/">a page for every suburb</a> with the cheapest fuel nearby.</li>'
                "<li><b>A public track record</b>: every call is scored a week later.</li></ul>",
                f'<div class="row"><a class="btn" href="{up}" data-cta="fuelcheck-map">Open Bowser’s live map</a><a href="{up}fuel-prices/">Fuel prices by suburb</a></div>',
                "<h2>How fresh are the prices on Bowser?</h2>",
                f"<p>Bowser reads FuelCheck several times a day, so a price here can be a few hours behind FuelCheck itself. Prices on this site are for {esc(self.day)}. "
                "Where a Sydney station hasn’t updated its price for more than a week, Bowser says so. Elsewhere in NSW and the ACT prices change less often, "
                "so Bowser shows the day a price last changed and flags it after three weeks. For the price this minute, check FuelCheck or the board at the station.</p>",
                "<h2>Is Bowser part of FuelCheck or the NSW Government?</h2>",
                "<p>No. Bowser is an independent project and isn’t affiliated with or endorsed by the NSW Government, NSW Fair Trading or FuelCheck. It uses FuelCheck data under its open licence "
                "(Creative Commons Attribution-ShareAlike 3.0 Australia), © State of New South Wales (NSW Fair Trading).</p>", self.sources_p()]
        t = "How Bowser uses NSW FuelCheck prices, and what it adds | Bowser"
        d = ("What NSW FuelCheck is, where its fuel prices come from, and what Bowser adds: a fill-or-wait forecast, a call for every station and "
             f"price history, all from FuelCheck data. Updated {self.sday}.")
        self.page("nsw-fuelcheck/", "fuelcheck", "/nsw-fuelcheck/", t, d, "\n".join(body), crumbs=[("NSW FuelCheck", "nsw-fuelcheck/")],
                  ld=art("nsw-fuelcheck/", "Bowser and NSW FuelCheck: what each one does", d), priority=0.8)

        # ---- about, privacy
        body = ["<h1>About Bowser</h1>",
                '<p class="lead">Bowser tells Sydney drivers when to fill up, and shows where fuel is cheapest across NSW and the ACT. It is an independent project, free to use.</p>',
                "<p>A bowser is what Australians call a petrol pump. The site and app take the prices NSW and ACT service stations report to the NSW Government’s FuelCheck service, "
                "add a forecast of where Sydney prices are heading, and turn it into one plain call: fill up now, or wait. "
                "The fill-or-wait forecast covers Sydney only. Elsewhere in NSW and the ACT you get today’s prices.</p>",
                "<h2>What’s here</h2>",
                f'<ul><li><a href="{up}" data-cta="about-map">The live dashboard</a>: today’s call, the cheapest stations near you on a map, and the forecast.</li>'
                f'<li><a href="{up}fuel-prices/">Fuel prices by suburb</a> and <a href="{up}station/">for every station</a>.</li>'
                f'<li><a href="{up}fuel-price-forecast/">The Sydney fuel price forecast</a> and how it is tested.</li>'
                f'<li><a href="{up}petrol-price-cycle/">The Sydney petrol price cycle</a>, explained.</li></ul>',
                "<h2>Where the data comes from</h2>",
                f"<p>{SOURCES} The forecast also uses wholesale prices from the "
                '<a href="https://www.aip.com.au/pricing/terminal-gate-prices" rel="noopener">Australian Institute of Petroleum</a>, oil prices from the '
                '<a href="https://www.eia.gov/dnav/pet/hist/RBRTED.htm" rel="noopener">U.S. Energy Information Administration</a> and the exchange rate from the '
                '<a href="https://www.rba.gov.au/statistics/frequency/exchange-rates.html" rel="noopener">Reserve Bank of Australia</a>.</p>',
                "<h2>How reliable is it?</h2>",
                "<p>Prices are the stations’ own reports, read several times a day, so they can be a few hours old; always check the board before you fill. "
                "Forecasts are estimates for planning, not financial advice, and every call Bowser makes is scored in public a week later.</p>",
                "<h2>Contact</h2>",
                f"<p>Found a wrong price or a bug, or have a question? Email {CONTACT}.</p>"]
        self.page("about/", "about", "/about/", "About Bowser: Sydney fuel prices and when to fill up",
                  "Bowser is an independent, free site and app that uses NSW FuelCheck prices to tell Sydney drivers when to fill up and where fuel is cheapest.",
                  "\n".join(body), crumbs=[("About", "about/")], priority=0.3)
        body = ["<h1>Privacy</h1>",
                '<p class="lead">Bowser has no accounts, no cookies and no advertising, on this site or in the app. It counts use anonymously, and this page says what is sent and to whom.</p>',
                '<p>Jump to: <a href="#site">the website</a> · <a href="#app">the Bowser app</a> · <a href="#contact">contact</a></p>',
                '<h2 id="site">What the website counts</h2>',
                "<p>When you open a page, leave it, or use one of its main buttons (such as Directions or Open the map), Bowser records an anonymous event. On the price pages it carries "
                "the kind of page (for example “a suburb page”, not which suburb), whether you’re on a phone or a computer, and the website that sent you here. "
                "On the dashboard it also records which fuel you chose, whether you switched between the list and the map, whether you set an area (not which area), "
                "and how many stations you have pinned (not which ones).</p>",
                "<p>Two random numbers kept in your browser’s storage tell a return visit from a new one and group one visit’s events together. "
                "They aren’t linked to your name, email or any account, because there are none.</p>",
                "<h2>What is never sent to Bowser’s analytics</h2>",
                "<ul><li>Your location: “Use my location” works out distances in your browser.</li>"
                "<li>Your suburb, the stations you look at or pin, or what you search for.</li>"
                "<li>Cookies: none are set.</li></ul>",
                "<p>Bowser asks its analytics provider not to work out where you are from your IP address, and its project is set to discard IP addresses.</p>",
                "<h2>Turning counting off</h2>",
                "<p>If your browser sends Global Privacy Control or Do Not Track, no events are sent at all.</p>",
                "<h2>Other services your browser contacts</h2>",
                "<p>Like any website, loading Bowser means your browser contacts the services that deliver it, and each sees your IP address and the usual technical details of the request:</p>"
                "<ul><li><b>GitHub Pages</b> hosts the site.</li>"
                "<li><b>PostHog</b> stores the anonymous events described above.</li>"
                "<li><b>OpenFreeMap</b> supplies the map: when you open or move the map on the dashboard, your browser fetches the map tiles for the area shown.</li>"
                "<li><b>Cloudflare (cdnjs)</b> delivers the chart and map code on the dashboard; OpenFreeMap also supplies the map’s lettering. The site uses no web fonts.</li>"
                "<li><b>Google Maps</b> opens only if you follow a Directions link.</li></ul>",
                # The app (Android on Google Play; iOS when it ships). Keep in step with app/src/lib/analytics.ts, lib/location.ts,
                # lib/alerts.ts and the More screen: Play's Data safety form (docs/PLAY_STORE.md) gives the same answers.
                '<h2 id="app">In the Bowser app</h2>',
                "<p>The app works without an account and keeps what you set up on your phone.</p>",
                "<h3>Your location</h3>"
                "<p>If you allow it, the app uses your phone’s location to sort stations by distance and to show where you are on the Stations map. "
                "Distances are worked out on the phone. Your location is never sent to Bowser, to its analytics or to anyone else by Bowser. "
                "The app only reads your location while you are using it. The home-screen widget lists stations near the area saved in the app, "
                "and if you set that area with “Use my location”, the widget uses the position the app took then.</p>",
                "<h3>What stays on your phone</h3>"
                "<p>Your area, fuel, pinned stations, logged fills, discounts and settings are stored only on your phone. They are left out of "
                "phone backups, and uninstalling Bowser deletes them. Price-rise alerts are scheduled on the phone itself: there is no notification server "
                "and no notification token.</p>",
                "<h3>Anonymous usage and crash reports</h3>"
                "<p>Unless you turn it off, the app sends anonymous events about how it is used: that it was opened, which kind of screen you visited, "
                "and which main features you used (for example pinning a station, logging a fill, opening directions or changing the fuel). "
                "They never include your location, your area, the stations you pin or what you paid. A random number made when you install the app "
                "groups an install’s events; it isn’t linked to your name, email, phone number or advertising ID. "
                "The events go to <b>PostHog</b>, which is set to discard IP addresses, and to <b>Expo</b> (EAS Observe), the service that builds "
                "and updates the app, along with crash reports and the app’s loading times.</p>"
                "<p>To stop them, turn off <b>More → Share anonymous usage</b>. Usage events stop straight away; crash reports stop once the app has been "
                "fully closed and opened again.</p>",
                "<h3>Other services the app contacts</h3>"
                "<ul><li><b>checkbowser.app</b> (GitHub Pages) for prices and forecasts. Requests carry no location; opening a station downloads that station’s price file, as a web page would.</li>"
                "<li><b>Expo</b> (EAS Update), to check for and download app updates.</li>"
                "<li><b>Google Maps</b> draws the Stations map on Android, so Google receives the area shown on the map and the usual technical details "
                "of the request, under <a href=\"https://policies.google.com/privacy\" rel=\"noopener\">Google’s privacy policy</a>. On iPhone the map is Apple Maps.</li>"
                "<li>Your maps app, if you tap Directions.</li>"
                "<li><b>Google Play</b>, which installs and updates the app under Google’s own terms.</li></ul>"
                "<p>Each sees your IP address, as any internet request does.</p>",
                "<h3>Deleting your data</h3>"
                "<p>Uninstalling Bowser deletes everything it stored on your phone. Bowser holds nothing that identifies you, so there is no account to close. "
                "If you would like the anonymous usage events from your install deleted, ask through the contact below and say roughly when you used the app.</p>",
                "<h3>Children</h3>"
                "<p>Bowser is meant for drivers and is not directed at children.</p>",
                "<h2>Changes</h2>",
                f"<p>If this changes, for example if the site starts to carry advertising, this page will be updated first. Last updated {esc(self.day)}.</p>",
                f'<h2 id="contact">Contact</h2><p>Questions or requests about privacy, including deleting usage data: email {CONTACT}.</p>']
        self.page("privacy/", "privacy", "/privacy/", "Privacy | Bowser",
                  "Bowser’s privacy policy for the website and the Android app: no accounts, no cookies, no advertising, and your location stays on your phone. What is counted anonymously and how to turn it off.",
                  "\n".join(body), crumbs=[("Privacy", "privacy/")], priority=0.2)
        body = ["<h1>That page isn’t here</h1>", '<p class="lead">The station or suburb may have changed its name, or the link is out of date.</p>',
                '<div class="row"><a class="btn" href="/fuel-prices/">Fuel prices by suburb</a><a href="/">Open the live map</a></div>']
        self.page("404.html", "404", "/404", "Page not found | Bowser", "This page isn’t on Bowser.", "\n".join(body), index=False, root="/")

    # ---- guides that answer one question each (docs/SEO.md keyword map)
    # ---- weekly outlooks (weekly.py): one dated page per saved week, the archive, and last week's result on the forecast page
    @staticmethod
    def week_title(w):
        d = dt.date.fromisoformat(w["week"])
        return f"Sydney fuel price outlook, week of {d.day} {d:%b %Y}"

    @staticmethod
    def _main(w):
        live = {r["fuel"]: r for r in w["live"]}
        return live.get("U91") or w["live"][0]

    def last_week(self, up):
        """The forecast page's "last week, scored" block: the newest week whose 7 days are known."""
        if not self.weeks: return []
        done = [w for w in self.weeks if w.get("done") and "actual" in (w["score"][self._main(w)["fuel"]].get("h7") or {})]
        if not done:
            return [f'<p class="small">Each week’s outlook is saved and scored a week later: <a href="{up}fuel-price-forecast/weekly/">weekly outlooks</a>.</p>']
        w = done[-1]; r = self._main(w); f = r["fuel"]; sc = w["score"][f]; h7, c = sc["h7"], sc["call"]
        move = "held about steady" if abs(h7["change"]) < 1 else f"{'risen' if h7['change'] > 0 else 'fallen'} {cents(h7['change'])}"
        exp = "little change" if abs(r["d7"]) < 1 else f"{'a rise' if r['d7'] > 0 else 'a fall'} of about {cents(r['d7'])}"
        res = {"right": "right", "close": "close", "wrong": "wrong"}.get(c["status"])
        return ["<h2>Last week’s outlook, scored</h2>",
                f"<p>On {esc(long_date(w['asof']))}, Bowser expected {exp} in the Sydney {esc(NAME[f])} median over the week. By {esc(short_date(h7['day']))} it had {move}, to {c1(h7['actual'])}c: "
                f"{'inside' if h7['inside'] else 'outside'} the likely range"
                + (f", {abs(h7['err']):.1f}c from the forecast." if abs(h7['err']) >= 0.5 else ", within half a cent of the forecast.")
                + (f" The call that morning, “{esc(c['head'] or WCALL.get(c['cls'], ''))}”, was <b>{res}</b>." if res else "")
                + f' <a href="{up}fuel-price-forecast/{w["week"]}/">That week’s outlook</a> · <a href="{up}fuel-price-forecast/weekly/">every week so far</a></p>']

    def week_page(self, w, prev, nxt):
        path = f"fuel-price-forecast/{w['week']}/"; up = "../../"
        r0 = self._main(w); f0 = r0["fuel"]; sc0 = w["score"][f0]; c0 = sc0["call"]; h70 = sc0.get("h7")
        head = self.week_title(w)
        exp = "stay about where it was" if abs(r0["d7"]) < 1 else f"{'rise' if r0['d7'] > 0 else 'fall'} by about {cents(r0['d7'])}"
        lead = (f"On {esc(long_date(w['asof']))}, Bowser expected the Sydney median {esc(NAME[f0])} price of {c1(r0['now'])}c to <b>{exp}</b> over the following week. "
                f"Its call that morning: <b>{esc((c0['head'] or WCALL.get(c0['cls'], '')).lower())}</b>.")
        if h70 and h70.get("missing"):
            lead += " There is no Sydney median on record for the day a week later."
        elif h70:
            lead += (f" A week later the median was {c1(h70['actual'])}c ({'+' if h70['change'] >= 0 else '−'}{abs(h70['change']):.1f}c), "
                     f"{'inside' if h70['inside'] else 'outside'} the likely range.")
        else:
            lead += f" It is scored once {esc(short_date((dt.date.fromisoformat(w['asof']) + dt.timedelta(days=7)).isoformat()))} is over."
        rng = lambda r, h: f"{r['now'] + r[f'lo{h}']:.0f}–{r['now'] + r[f'hi{h}']:.0f}"
        fuels = [r for f in FUELS for r in w["live"] if r["fuel"] == f]
        out_rows = "".join(
            f'<tr><td>{esc(NAME[r["fuel"]])}</td><td class="n">{c1(r["now"])}</td><td class="n">{c1(r["now"] + r["d7"])}<br><span class="small">{rng(r, 7)}</span></td>'
            f'<td class="n">{c1(r["now"] + r["d14"])}<br><span class="small">{rng(r, 14)}</span></td><td class="n">{"under 5%" if r["p_jump7"] < 0.05 else pct0(r["p_jump7"])}</td>'
            f'<td>{esc((w["score"][r["fuel"]]["call"]["head"] or "").lower() or WCALL.get(w["score"][r["fuel"]]["call"]["cls"], ""))}</td></tr>' for r in fuels)
        def landed(r, h):
            x = w["score"][r["fuel"]].get(f"h{h}")
            if x and x.get("missing"): return '<span class="small">no median that day</span>'
            if not x: return f'<span class="small">due {esc(short_date((dt.date.fromisoformat(w["asof"]) + dt.timedelta(days=h)).isoformat()))}</span>'
            return (f'{c1(x["actual"])} ({"+" if x["change"] >= 0 else "−"}{abs(x["change"]):.1f}c)<br><span class="small">'
                    f'{"in range" if x["inside"] else "outside the range"}, {"+" if x["err"] >= 0 else "−"}{abs(x["err"]):.1f}c vs forecast</span>')
        land_rows = "".join(f'<tr><td>{esc(NAME[r["fuel"]])}</td><td class="n">{landed(r, 7)}</td><td class="n">{landed(r, 14)}</td></tr>' for r in fuels)
        def call_cell(r):
            c = w["score"][r["fuel"]]["call"]
            if c["status"] == "pending": return '<td class="n">–</td><td>Pending</td>'
            return f'<td class="n">{"+" if c["move"] >= 0 else "−"}{abs(c["move"]):.1f}c</td><td>{esc(c["status"].capitalize())}</td>'
        call_rows = "".join(f'<tr><td>{esc(NAME[r["fuel"]])}</td><td>{esc(WCALL.get(w["score"][r["fuel"]]["call"]["cls"], "").capitalize())}</td>{call_cell(r)}</tr>' for r in fuels)
        links = [f'<a href="{up}fuel-price-forecast/{prev["week"]}/">‹ Week of {esc(short_date(prev["week"]))}</a>' if prev else "",
                 f'<a href="{up}fuel-price-forecast/weekly/">All weeks</a>',
                 f'<a href="{up}fuel-price-forecast/{nxt["week"]}/">Week of {esc(short_date(nxt["week"]))} ›</a>' if nxt else "",
                 f'<a href="{up}fuel-price-forecast/">This week’s forecast</a>']
        trk = f'<a href="{up}fuel-price-forecast/accuracy/">track record</a>' if self.has_acc else "track record"
        body = [f"<h1>{esc(head)}</h1>", f'<p class="lead">{lead}</p>',
                f'<p class="small">Saved {esc(long_date(w["asof"]))} and never revised. Sydney median prices in cents a litre; the range is where Bowser expected the price to land about 8 times in 10.</p>',
                "<h2>The outlook that week</h2>",
                '<div class="scroll"><table><thead><tr><th>Fuel</th><th class="n">Then</th><th class="n">In 7 days</th><th class="n">In 14 days</th><th class="n">Jump chance</th><th>Call</th></tr></thead><tbody>'
                + out_rows + "</tbody></table></div>",
                "<h2>Where the price landed</h2>",
                "<p>The Sydney median at the end of the day 7 and 14 days later, against the price the outlook started from: inside or outside the likely range, and how far from the forecast.</p>",
                '<div class="scroll"><table><thead><tr><th>Fuel</th><th class="n">7 days later</th><th class="n">14 days later</th></tr></thead><tbody>' + land_rows + "</tbody></table></div>",
                "<h2>The call</h2>",
                f'<p>Scored the way every call in the {trk} is: the average Sydney median over the 7 days after the call against the price it was made with. '
                "<b>Fill now</b> is right if that rose 1c or more, <b>wait</b> if it fell 1c or more, <b>no rush</b> if it moved under 3c. "
                "So a call can be right while the price ends outside the range, or the other way round: they measure different things.</p>",
                '<div class="scroll"><table><thead><tr><th>Fuel</th><th>Call</th><th class="n">Week’s average vs then</th><th>Result</th></tr></thead><tbody>' + call_rows + "</tbody></table></div>",
                '<p class="row">' + " ".join(x for x in links if x) + "</p>", self.sources_p()]
        lastmod = w.get("scored") or w["asof"]
        d = (f"Bowser’s Sydney fuel price outlook saved {short_date(w['asof'])} {w['asof'][:4]}: the call, the 7 and 14-day forecast with ranges"
             + (", and how it turned out." if h70 else ". Scored a week later."))
        art = {**self._art(path, head, d), "datePublished": w["asof"], "dateModified": lastmod}
        dd = dt.date.fromisoformat(w["week"])
        title = f"Sydney fuel outlook, week of {dd.day} {dd:%b %Y}" + (", scored" if h70 else "") + " | Bowser"   # under 70 characters
        self.page(path, "week", "/fuel-price-forecast/:week/", title, d, "\n".join(body),
                  crumbs=[("Forecast", "fuel-price-forecast/"), ("Weekly", "fuel-price-forecast/weekly/"), (short_date(w["week"]), path)],
                  ld=[art], priority=0.4, index=bool(w.get("done")), lastmod=lastmod)

    def weekly_pages(self):
        if not self.weeks: return
        ws = self.weeks
        for i, w in enumerate(ws): self.week_page(w, ws[i - 1] if i else None, ws[i + 1] if i + 1 < len(ws) else None)
        up = "../../"; path = "fuel-price-forecast/weekly/"
        def row(w):
            r = self._main(w); sc = w["score"][r["fuel"]]; h7, c = sc.get("h7"), sc["call"]
            sg = lambda v: f"{'+' if v >= 0 else '−'}{abs(v):.1f}c"
            actual = sg(h7["change"]) if h7 and "change" in h7 else "–"
            return (f'<tr><td><a href="{up}fuel-price-forecast/{w["week"]}/">{esc(short_date(w["week"]))} {w["week"][:4]}</a></td><td class="n">{c1(r["now"])}</td>'
                    f'<td class="n">{sg(r["d7"])}</td><td class="n">{actual}</td>'
                    f'<td>{esc(WCALL.get(c["cls"], "").capitalize())}</td><td>{esc(c["status"].capitalize())}</td></tr>')
        head = "Sydney fuel price outlooks, week by week"
        body = [f"<h1>{head}</h1>",
                '<p class="lead">Each week Bowser saves the forecast it published on its first run of the week (normally early Monday), and scores it once the week is over: where the price landed against the forecast, and whether the fill-or-wait call was right.</p>',
                '<p class="small">Unleaded 91, Sydney median, cents a litre. Each week’s page has every fuel. Nothing is revised after it is saved.</p>',
                '<div class="scroll"><table><thead><tr><th>Week of</th><th class="n">Price then</th><th class="n">Expected in 7 days</th><th class="n">Actual</th><th>Call</th><th>Result</th></tr></thead><tbody>'
                + "".join(row(w) for w in reversed(ws)) + "</tbody></table></div>",
                f'<p>See <a href="{up}fuel-price-forecast/">this week’s forecast</a>'
                + (f' and <a href="{up}fuel-price-forecast/accuracy/">the full track record</a>, replayed back to 2021' if self.has_acc else "") + ".</p>", self.sources_p()]
        d = "Every weekly Sydney fuel price outlook Bowser has saved, and how each turned out: the forecast against the price, and the fill-or-wait call."
        done = [w for w in ws if w.get("done")]
        lastmod = max((w.get("scored") or w["asof"]) for w in ws)
        self.page(path, "weekly", "/fuel-price-forecast/weekly/", "Sydney fuel price outlooks, week by week | Bowser", d, "\n".join(body),
                  crumbs=[("Forecast", "fuel-price-forecast/"), ("Weekly", path)], ld=[{**self._art(path, head, d), "datePublished": ws[0]["asof"], "dateModified": lastmod}],
                  priority=0.5, index=bool(done), lastmod=lastmod)

    def _art(self, path, head, desc):
        return {"@context": "https://schema.org", "@type": "Article", "headline": head, "description": desc,
                "datePublished": PUBLISHED, "dateModified": self.asof, "mainEntityOfPage": f"{self.site}/{path}", "image": f"{self.site}/og.png",
                "author": {"@type": "Organization", "name": "Bowser", "url": self.site + "/"},
                "publisher": {"@type": "Organization", "name": "Bowser", "url": self.site + "/"}}

    def accuracy(self):
        """The forecast's track record: the replayed and live fill-or-wait calls (track.json) and the price forecast's error
        against assuming no change (forecast.json bt, the walk-forward backtest). Nobody else publishes theirs."""
        up = "../../"; path = "fuel-price-forecast/accuracy/"
        tr = (self.track.get("replay") or {}).get("U91") or {}; lv = (self.track.get("live") or {}).get("U91") or {}
        sm = self.bt.get("summary") if isinstance(self.bt.get("summary"), dict) else {}; prod = self.bt.get("prod")
        ent = lambda f, h: e if isinstance(e := sm.get(f"{f}|{h}"), dict) else {}
        err = lambda f, h: (ent(f, h).get(prod) if isinstance(prod, str) else None, ent(f, h).get("naive"))
        counts = lambda d: isinstance(d, dict) and all(num(d.get(k)) for k in ("n", "right", "close", "wrong")) and d["n"] > 0
        if not (counts(tr) and isodate(tr.get("from")) and isodate(tr.get("to"))): tr = {}
        CALL = {"up": "fill now", "down": "wait", "flat": "no rush"}
        pct = lambda a, n: f"{a / n:.0%}" if n else "–"
        m7, n7 = err("U91", 7)
        lead = []
        if tr.get("n"):
            base = tr.get("base") if isinstance(tr.get("base"), dict) else {}
            lead.append(f"Replayed on {tr['n']:,} days from {esc(short_date(tr['from']))} {tr['from'][:4]} to {esc(short_date(tr['to']))} {tr['to'][:4]}, using only what was known on each day, "
                        f"Bowser’s fill-or-wait call for Sydney Unleaded 91 was right <b>{pct(tr['right'], tr['n'])}</b> of the time."
                        + (f" The best rule that ignores the forecast, always saying “{CALL.get(base.get('cls'), base.get('cls'))}”, was right on {pct(base['right'], tr['n'])}." if num(base.get("right")) else "")
                        + (f" On average, following the call would have saved about {tr['save']:.1f}c a litre each time you checked, ${TANK * tr['save'] / 100:.2f} on a {TANK} L tank, against filling up that day." if num(tr.get("save")) and math.isfinite(tr["save"]) and tr["save"] > 0 else ""))
        if num(m7) and num(n7):
            lead.append(f"Its 7-day price forecast was off by <b>{m7:.1f}c</b> a litre on average, against {n7:.1f}c for assuming today’s price holds.")
        body = ["<h1>How accurate is Bowser’s fuel price forecast?</h1>",
                f'<p class="lead">{" ".join(lead) or "Every call Bowser makes is scored a week later, in public."}</p>',
                f'<p class="small">Updated {esc(self.day)}. Figures are for Sydney medians; Bowser’s forecast covers Sydney only.</p>']
        if tr.get("n"):
            by = tr.get("by") or {}
            body += ["<h2>The fill-or-wait call</h2>",
                     "<p>Each day Bowser says fill now, wait, or no rush. A week later the call is scored against what the Sydney median actually did over that week: "
                     "<b>fill now</b> is right if prices rose by 1c or more, <b>wait</b> is right if they fell by 1c or more, and <b>no rush</b> is right if they moved less than 3c. "
                     "Anything in between counts as close, and a no-rush call is wrong only if prices moved 5c or more.</p>",
                     '<div class="scroll"><table><thead><tr><th>Call</th><th class="n">Days</th><th class="n">Right</th><th class="n">Close</th><th class="n">Wrong</th></tr></thead><tbody>'
                     + "".join(f'<tr><td>{esc(CALL[c].capitalize())}</td><td class="n">{b["n"]:,}</td><td class="n">{pct(b["right"], b["n"])}</td><td class="n">{pct(b["close"], b["n"])}</td><td class="n">{pct(b["wrong"], b["n"])}</td></tr>'
                               for c in ("up", "down", "flat") if counts(b := by.get(c)))
                     + f'<tr><td><b>All calls</b></td><td class="n">{tr["n"]:,}</td><td class="n">{pct(tr["right"], tr["n"])}</td><td class="n">{pct(tr["close"], tr["n"])}</td><td class="n">{pct(tr["wrong"], tr["n"])}</td></tr>'
                     + "</tbody></table></div>"]
            rc = tr.get("recent") or {}
            if counts(rc) and isodate(rc.get("from")) and isodate(rc.get("to")):
                rb = rc.get("base") if isinstance(rc.get("base"), dict) else {}
                harder = rc["right"] / rc["n"] < tr["right"] / tr["n"] - 0.03
                body.append(f"<p>Over the last 12 months of the replay ({esc(short_date(rc['from']))} {rc['from'][:4]} to {esc(short_date(rc['to']))} {rc['to'][:4]}) "
                            + ("the going was harder: " if harder else "the call held up: ") + f"right on <b>{pct(rc['right'], rc['n'])}</b> of {rc['n']} days"
                            + (f", against {pct(rb['right'], rc['n'])} for always saying “{CALL.get(rb.get('cls'), rb.get('cls'))}”" if num(rb.get("right")) else "") + ".</p>")
            if counts(lv) and isodate(lv.get("since")):
                body.append(f"<p>Live calls, made each morning since {esc(short_date(lv['since']))} and never revised: {lv['right']} of {lv['n']} scored so far were right, {lv['close']} close and {lv['wrong']} wrong. "
                            f'Every one is listed on the <a href="{up}" data-cta="accuracy-track">dashboard</a>.</p>')
        if tr.get("n"):
            body += ["<h2>Why accuracy figures differ between sites</h2>",
                     "<p>A hit rate depends on the scoring rule as much as on the forecast. Bowser counts a wait as right only if the Sydney median then averaged at least 1c lower "
                     "over the following week, and a fill only if it averaged at least 1c higher; a no-rush call is right if prices moved less than 3c and wrong at 5c or more. It scores every day, including days without a strong call, and live calls keep the "
                     "morning call, never revised. A rule that counts a wait as right whenever any cheaper day follows within the week, or leaves out the hard days, reports a higher "
                     "figure for the same forecast.</p>",
                     "<p>That is why Bowser also shows what following the calls saved, in cents, and what a fixed habit such as always waiting would have scored on the same days. "
                     "A forecast earns its keep only if it beats the habit.</p>"]
        hs = [(h, *err("U91", h), ent("U91", h).get("dir")) for h in (1, 3, 7, 14)]
        hs = [x for x in hs if num(x[1]) and num(x[2])]
        if hs:
            body += ["<h2>The price forecast against the simplest guess</h2>",
                     "<p>The simplest forecast is that today’s price holds. This is how far each was from the real Sydney Unleaded 91 median, on average, over every day since January 2021.</p>",
                     '<div class="scroll"><table><thead><tr><th>Days ahead</th><th class="n">Bowser’s error</th><th class="n">“No change” error</th><th class="n">Direction right</th></tr></thead><tbody>'
                     + "".join(f'<tr><td>{h}</td><td class="n">{m:.1f}c</td><td class="n">{n:.1f}c</td><td class="n">{f"{d:.0%}" if num(d) else "–"}</td></tr>' for h, m, n, d in hs)
                     + "</tbody></table></div>",
                     '<p class="small">Error: the average gap between the forecast and the real median, in cents a litre. Direction: how often the forecast got the direction right on days the price moved 1c or more.</p>']
        yr = self.bt.get("yearly_u91_h7") or {}
        ys = sorted((str(y), v["model"], v["naive"]) for y, v in (yr.items() if isinstance(yr, dict) else []) if isinstance(v, dict) and num(v.get("model")) and num(v.get("naive")) and v["naive"] > 0)
        if ys:
            worst = max(ys, key=lambda t: t[1] / t[2])
            body += ["<h2>Year by year</h2>",
                     "<p>The 7-day forecast for Unleaded 91 in each year of the test, against assuming no change. Each month was forecast with a model trained only on the data before it.</p>",
                     '<div class="scroll"><table><thead><tr><th>Year</th><th class="n">Bowser’s error</th><th class="n">“No change” error</th></tr></thead><tbody>'
                     + "".join(f'<tr><td>{esc(y)}{" (so far)" if str(y) == self.asof[:4] else ""}</td><td class="n">{m:.1f}c</td><td class="n">{n:.1f}c</td></tr>' for y, m, n in ys)
                     + "</tbody></table></div>",
                     f"<p>The hardest year was {esc(worst[0])}, when Bowser’s error was {worst[1]:.1f}c against {worst[2]:.1f}c for no change. Sudden shocks, such as an oil price spike or a change in fuel excise, "
                     "can’t be seen in the data before they happen, so the forecast catches up only once they show in prices.</p>"]
        cs = [(f, *err(f, 7)) for f in FUELS if f in self.live]
        cs = [x for x in cs if num(x[1]) and num(x[2])]
        if len(cs) > 1:
            body += ["<h2>Every fuel, 7 days ahead</h2>",
                     '<div class="scroll"><table><thead><tr><th>Fuel</th><th class="n">Bowser’s error</th><th class="n">“No change” error</th></tr></thead><tbody>'
                     + "".join(f'<tr><td><a href="{up}fuel-prices/{FSLUG[f]}/">{NAME[f]}</a></td><td class="n">{m:.1f}c</td><td class="n">{n:.1f}c</td></tr>' for f, m, n in cs)
                     + "</tbody></table></div>",
                     "<p>Diesel doesn’t follow the petrol price cycle, so assuming no change is already a good guess for it a few days out; the forecast earns its keep on the cycling petrol grades.</p>"]
        body += ["<h2>How the test is run</h2>",
                 "<ul><li><b>No peeking:</b> each month from January 2021 is forecast by a model trained only on the days before it, then the model is retrained and the next month is forecast.</li>"
                 "<li><b>Every day counts:</b> calm months, price jumps and the 2022 and 2026 oil shocks are all in the figures, nothing left out.</li>"
                 "<li><b>The same rule live:</b> live calls are scored exactly as the replay is, and the morning call is kept, so a call is never changed with hindsight.</li></ul>",
                 f'<p>See <a href="{up}fuel-price-forecast/">today’s forecast</a> and <a href="{up}petrol-price-cycle/">where Sydney is in the price cycle</a>.</p>', self.sources_p()]
        t = "How accurate is Bowser’s fuel price forecast? | Bowser"
        d = clip("Bowser’s Sydney fuel price forecast, tested on every day since 2021: how often the fill-or-wait call was right, the average error against assuming no change, "
                 f"year by year and for every fuel. Updated {self.sday}.")
        self.page(path, "accuracy", "/fuel-price-forecast/accuracy/", t, d, "\n".join(x for x in body if x),
                  crumbs=[("Forecast", "fuel-price-forecast/"), ("Accuracy", path)], ld=[self._art(path, "How accurate is Bowser’s fuel price forecast?", d)], priority=0.7)

    def best_day(self):
        """The weekday question, answered with Bowser's own weekday figures (stats.dow), and what to watch instead."""
        up = "../"; path = "best-day-to-buy-petrol/"; S = self.stats; dow = S["dow"]
        lo_d, hi_d = DOW[dow.index(min(dow))], DOW[dow.index(max(dow))]; spread = max(dow) - min(dow)
        rel = lambda x: "about the same as" if abs(x) < 0.05 else f"{abs(x):.1f}c {'under' if x < 0 else 'over'}"
        gaps = [c["gap"] for c in (S.get("cycles_by_year") or []) if num(c.get("gap"))]
        amp = S.get("cycle_amp_calm")
        body = ["<h1>What is the best day to buy petrol in Sydney?</h1>",
                f'<p class="lead">There isn’t one any more. Averaged over the calm years since 2019, {lo_d} is the cheapest day to buy petrol in Sydney and {hi_d} the dearest, '
                f"but the difference is only <b>{spread:.1f}c a litre</b>, about {TANK * spread:.0f} cents on a {TANK} L tank. What matters is where Sydney is in its price cycle, "
                "and the cheap days fall on a different weekday every cycle.</p>",
                f'<p class="small">Updated {esc(self.day)}.</p>',
                self.stage_card() or (self.verdict_card("U91", up) if "U91" in self.live else ""),
                "<h2>Petrol prices by day of the week in Sydney</h2>",
                '<div class="scroll"><table><thead><tr><th>Day</th><th class="n">Against the week’s average</th><th class="n">On a 50 L tank</th></tr></thead><tbody>'
                + "".join(f'<tr><td>{"<b>" + d + "</b>" if x in (min(dow), max(dow)) else d}</td><td class="n">{rel(x)}</td><td class="n">{"−" if x < 0 else "+" if x > 0 else ""}{abs(TANK * x):.0f}c</td></tr>'
                          for d, x in zip(DOW, dow))
                + "</tbody></table></div>",
                '<p class="small">How it’s measured: each day’s Sydney Unleaded 91 median against the seven-day average around it, averaged over 2019 to early 2026, leaving out the 2022 oil shock '
                "and the months since March 2026, when oil and excise moves swamped the weekly pattern.</p>",
                "<h2>Why the “cheap Tuesday” rule doesn’t work in Sydney</h2>",
                "<p>Sydney’s price cycle runs for weeks, not days"
                + (f": the typical gap between jumps has been {min(gaps):.0f} to {max(gaps):.0f} days, depending on the year" if gaps else "")
                + ". So each cycle’s cheapest days land on a different weekday, and averaged over years every weekday comes out close to even. "
                "Tips about a cheap weekday come from cities, or years, where the cycle ran on a weekly timetable.</p>",
                "<h2>So when should you fill up?</h2>",
                "<p>Near the bottom of the cycle, just before the next jump"
                + (f". Filling just before a jump instead of just after it saves about {amp:.0f}c a litre, ${TANK * amp / 100:.2f} on a {TANK} L tank, "
                   f"{amp / spread:.0f} times the gap between the cheapest and dearest weekday" if num(amp) and spread > 0 else "")
                + (f". Today, {esc(lc(self.outlook('U91')))}" if "U91" in self.live else "")
                + f' See the <a href="{up}fuel-price-forecast/">Sydney fuel price forecast</a> and <a href="{up}petrol-price-cycle/">where the cycle is now</a>.</p>']
        if num(S.get("shop_around")):
            body += ["<h2>Pick the station, not just the day</h2>",
                     f"<p>On any given day the cheapest tenth of Sydney stations are typically {S['shop_around']:.0f}c a litre under the median: "
                     f'more than {S["shop_around"] / spread:.0f} times the weekday difference. <a href="{up}fuel-prices/">Find today’s cheapest stations by suburb</a>.</p>' if spread > 0 else
                     f'<p>On any given day the cheapest tenth of Sydney stations are typically {S["shop_around"]:.0f}c a litre under the median. <a href="{up}fuel-prices/">Find them by suburb</a>.</p>']
        body += ["<h2>Other cities</h2>",
                 "<p>Each big Australian city has its own price cycle, with its own length. The ACCC publishes where "
                 '<a href="https://www.accc.gov.au/consumers/petrol-and-fuel/petrol-price-cycles-in-the-5-largest-cities" rel="noopener">Sydney, Melbourne, Brisbane, Adelaide and Perth</a> '
                 "are in theirs. In Western Australia, FuelWatch publishes tomorrow’s prices each afternoon. Bowser’s numbers on this page are for Sydney.</p>"]
        wk, we = sum(dow[:5]) / 5, (dow[5] + dow[6]) / 2
        qa = [("What day is petrol cheapest in Sydney?",
               f"No day is reliably cheapest. Averaged over the calm years since 2019, {lo_d} comes out cheapest and {hi_d} dearest, but only {spread:.1f}c a litre apart. "
               "Filling near the bottom of the price cycle, before the next jump, matters far more."),
              ("Is Tuesday the cheapest day to buy petrol in Sydney?",
               ("Only just, and not by enough to matter. " if lo_d == "Tuesday" else "No. ") + f"In Sydney, Tuesday averages {rel(dow[1])} the week’s average price. The cheap-Tuesday rule comes from cities, or years, where the price cycle ran weekly; "
               "Sydney’s runs for weeks."),
              ("Is petrol cheaper in the morning or at night in Sydney?",
               "There’s no reliable daily pattern on ordinary days. On the day of a price jump, though, stations raise their prices through the day: on the days of Sydney’s 8c-plus jumps in 2025–26, "
               + ", ".join(f"about {x:.0%} of stations had raised by {t}" for t, x in JUMP_BY_TIME) + ". So when a jump is forecast, fill up in the morning rather than the evening."),
              ("Is petrol cheaper on weekends in Sydney?",
               f"{'Barely' if abs(we - wk) < 0.5 else 'A little'}. Saturday and Sunday average {rel(we - wk)} the weekdays, about {abs(TANK * (we - wk)):.0f} cents on a {TANK} L tank. "
               "The price cycle and the station you choose matter far more.")]
        fq, fq_ld = self.faq(qa); body += [fq, self.sources_p()]
        t = "Best day to buy petrol in Sydney: is there one? | Bowser"
        d = clip(f"Is there a cheapest day to buy petrol in Sydney? Bowser’s figures since 2019: {lo_d} is cheapest and {hi_d} dearest, only {spread:.1f}c apart. "
                 "What to watch instead, and today’s fill-or-wait call.")
        self.page(path, "bestday", "/best-day-to-buy-petrol/", t, d, "\n".join(x for x in body if x), crumbs=[("Best day to buy petrol", path)],
                  ld=[self._art(path, "What is the best day to buy petrol in Sydney?", d), fq_ld], priority=0.8)

    def christmas(self):
        """What the Sydney U91 median did over each Christmas in history.json, and the outlook for this one."""
        up = "../"; path = "petrol-prices-christmas/"; rows = self.xmas; today = dt.date.fromisoformat(self.fc_asof)
        n = len(rows); jy = [x for x in rows if x["jump"]]
        span = f"{rows[0]['year']} to {rows[-1]['year']}"
        lab = lambda y: f"{y}–{str(y + 1)[2:]}"
        ans = (f"In {len(jy)} of the last {n} Christmas holidays ({span}), Sydney petrol prices jumped at some point between 10 December and 10 January; "
               f"in the other {n - len(jy)} there was no jump. The jumps follow Sydney’s price cycle, which runs on its own timetable, so the useful question is where the cycle will be in late December.")
        body = ["<h1>Do petrol prices go up at Christmas in Sydney?</h1>", f'<p class="lead">{esc(ans)}</p>', f'<p class="small">Updated {esc(self.day)}.</p>']
        xmas = dt.date(today.year, 12, 25)
        reach = today + dt.timedelta(days=14)
        r = self.live.get("U91")
        if r and dt.date(today.year, 11, 1) <= today <= xmas:          # the run-up only; the table covers the rest of the year
            k = (xmas - today).days; dx = self.path(r, "d", k) if k <= 14 else None
            now = (f"This year, {lc(self.outlook('U91'))} "
                   + (f"For Christmas Day, {k} days away, Bowser expects about {c1(r['now'] + dx)}c." if dx is not None else
                      f"Christmas is {(xmas - today).days} days away; Bowser’s 14-day forecast will reach it from {short_date((xmas - dt.timedelta(days=14)).isoformat())}."))
            body += [f"<h2>Christmas {xmas.year}: what Bowser expects</h2>", self.stage_card() or self.verdict_card("U91", up),
                     f'<p>{esc(now)} <a href="{up}fuel-price-forecast/">See the full forecast</a>.</p>']
        else:
            now = "Bowser’s 14-day forecast reaches Christmas Day from 11 December each year."
        body += ["<h2>Every Christmas since " + str(rows[0]["year"]) + "</h2>",
                 "<p>The Sydney Unleaded 91 median from 10 December to 10 January, in cents a litre.</p>",
                 '<div class="scroll"><table><thead><tr><th>Holidays</th><th class="n">10 Dec</th><th class="n">24 Dec</th><th class="n">10 Jan</th><th class="n">Highest</th><th>Jump began</th></tr></thead><tbody>'
                 + "".join(f'<tr><td>{lab(x["year"])}</td><td class="n">{c1(x["start"])}</td><td class="n">{c1(x["eve"])}</td><td class="n">{c1(x["end"])}</td>'
                           f'<td class="n">{c1(x["hi"])} <span class="small">{esc(short_date(x["hi_d"].isoformat()))}</span></td><td>{esc(short_date(x["jump"].isoformat())) if x["jump"] else "No jump"}</td></tr>'
                           for x in reversed(rows))
                 + "</tbody></table></div>",
                 '<p class="small">A jump: the median rose 8c or more within three days, the rule Bowser uses to count the price cycle.</p>',
                 "<h2>Tips for a holiday road trip</h2>",
                 "<ul><li><b>Check the forecast before you leave.</b> If a jump is likely within the week, fill up before it; if prices are sliding, fill only what you need.</li>"
                 f'<li><b>Fill in Sydney if it’s cheaper.</b> Regional prices often sit above Sydney’s; compare <a href="{up}fuel-prices/">Sydney and regional prices</a> before you go.</li>'
                 "<li><b>Pick the station.</b> Even at the top of the cycle some stations hold their old price for days.</li></ul>"]
        qa = [("Do petrol prices go up before Christmas in Sydney?", ans),
              *([("Will petrol prices go up this Christmas?", now)] if r and dt.date(today.year, 11, 1) <= today <= xmas else [])]
        fq, fq_ld = self.faq(qa); body += [fq, self.sources_p()]
        t = "Petrol prices at Christmas in Sydney: do they go up? | Bowser"
        d = clip(f"Do Sydney petrol prices go up at Christmas? In {len(jy)} of the last {n} holidays they jumped between 10 December and 10 January. "
                 f"Every year since {rows[0]['year']}, and this year’s forecast. Updated {self.sday}.")
        self.page(path, "christmas", "/petrol-prices-christmas/", t, d, "\n".join(x for x in body if x), crumbs=[("Petrol prices at Christmas", path)],
                  ld=[self._art(path, "Do petrol prices go up at Christmas in Sydney?", d), fq_ld], priority=0.6)

    # ---- fuel discounts: the hub and a page for each big one (DEALS; docs/SEO.md "Keyword research, 2026-11-22")
    def built(self, key):
        """True when offer `key` is running and its own page is built (so links to it lead somewhere)."""
        return any(d["key"] == key and self.deal_page(d) for d in self.offers())

    def offers(self):
        """The DEALS still running on the build day."""
        return [d for d in DEALS if not d.get("until") or self.asof <= d["until"]]

    def costco_gap(self, pool, f):
        """(Sydney Costco average for fuel f, its gap under the Sydney median in c/L) or None."""
        ps = [s["p"][f][0] for s in pool if not s.get("out") and self.fresh(s, f)]; x = self.live.get(f)
        if len(ps) < 2 or not x or not num(x.get("now")): return None
        a = sum(ps) / len(ps); return a, x["now"] - a

    def costco_note(self, pool, f, up):
        g = self.costco_gap(pool, f)
        if not g: return ""
        a, gap = g
        txt = (f"<h2>Does a Costco membership pay for itself?</h2><p>Sydney’s Costcos average {a:.1f}c for {esc(NAME[f])} today, "
               + (f"{gap:.1f}c under the Sydney median. At that gap a ${COSTCO_FEE} Gold Star membership pays for itself after about {COSTCO_FEE * 100 / gap:,.0f} litres, "
                  f"or {COSTCO_FEE * 100 / gap / TANK:.0f} {TANK} L tanks, before counting the drive and the queue." if gap >= 1 else
                  "about the same as the Sydney median, so the fuel alone doesn’t pay for the membership today.")
               + f' That’s against the median; the cheapest stations near you may narrow it. Compare with <a href="{up}petrol-deals-sydney/">other fuel discounts</a>.</p>')
        return txt

    def costco_faq(self, pool, f):
        g = self.costco_gap(pool, f)
        qa = [("Do you need a Costco membership to buy Costco fuel?",
               f"Yes. NSW FuelCheck lists every Costco fuel station as members only, and Costco’s Gold Star membership is ${COSTCO_FEE} a year."),
              ("Which Costco stations in Sydney sell fuel?",
               "Auburn, Casula (Crossroads) and Marsden Park, with another at Lake Macquarie near Newcastle. They sell E10 and Premium 98, and Bowser shows each one’s price every day.")]
        if g:
            a, gap = g
            qa.append(("Is Costco fuel cheaper?", f"Today, yes: Sydney’s Costcos average {a:.1f}c for {NAME[f]}, {gap:.1f}c under the Sydney median." if gap >= 1 else
                       f"Not by much today: Sydney’s Costcos average {a:.1f}c for {NAME[f]}, close to the Sydney median."))
        fq, fq_ld = self.faq(qa)
        return [fq, fq_ld]

    def deal_page(self, d):
        """The offer's own page if it is built (a brand page exists only with 3+ stations), else None."""
        p = d.get("page")
        if not p: return None
        return p if not p.startswith("brands/") or p in self.brand_url.values() else None

    def deal_pool(self, d, f=None):
        """The Sydney stations that take offer d, with a fresh price for fuel f (default the offer's fuel), members' sites included."""
        f = f or d.get("fuel", "U91")
        return [s for s in self.st if not s.get("out") and s["brand"] in d["brands"] and self.fresh(s, f)]

    def deal_avg(self, d, f=None):
        """(average price at the stations that take d, the Sydney median for that fuel or None) for fuel f; average None under 3 stations."""
        f = f or d.get("fuel", "U91"); ps = [s["p"][f][0] for s in self.deal_pool(d, f) if self.reg(s, f)]
        x = self.live.get(f)
        return (sum(ps) / len(ps) if len(ps) >= 3 else None), (x["now"] if x and num(x.get("now")) else None)

    @staticmethod
    def gap_span(a, m):
        if a is None or m is None: return "–"
        if abs(a - m) < 0.05: return "0.0"
        return f'<span class="{"cheap" if a < m else "dear"}">{"−" if a < m else "+"}{abs(a - m):.1f}</span>'

    def deal_note(self):
        return ('<p class="small">Offers change often: check the current terms before relying on one. Prices are pump prices as reported to NSW FuelCheck; '
                "a price after a discount is that pump price less the discount, and only applies under the offer’s conditions. Bowser is independent, isn’t affiliated "
                "with any of these businesses and is paid nothing for listing them. Their names are trade marks of their owners.</p>")

    def deals(self):
        """Fuel discounts (DEALS, from each program's own terms) beside what Bowser can measure: the price at those stations
        before the discount, and what timing and the choice of station are worth by comparison."""
        up = "../"; path = "petrol-deals-sydney/"; S = self.stats; r = self.live.get("U91")
        r = r if r and num(r.get("now")) else None
        rows = []
        for d in self.offers():
            f = d.get("fuel", "U91"); avg, med = self.deal_avg(d); cut = d.get("cut")
            fl = "" if f == "U91" else f' <span class="small">{esc(SHORT[f])}</span>'
            link = f'<a href="{up}{esc(self.deal_page(d))}">{esc(d["name"])}</a>' if self.deal_page(d) else f'<a href="{esc(d["terms"])}" rel="noopener">{esc(d["name"])}</a>'
            rows.append(f'<tr><td>{link}</td><td>{esc(", ".join(d["brands"]))}</td>'
                        f'<td class="n">{f"{cut}c/L" if cut else "varies"}</td><td class="n">{f"{avg:.1f}{fl}" if avg is not None else "–"}</td>'
                        f'<td class="n">{self.gap_span(avg, med)}</td><td class="n">{f"{avg - cut:.1f}" if avg is not None and cut else "–"}</td></tr>')
        amp, shop = S.get("cycle_amp_calm"), S.get("shop_around"); med_now = f" of {c1(r['now'])}c" if r else ""
        worth = [f"a 4c docket saves <b>${TANK * 4 / 100:.2f}</b>"]
        if num(shop): worth.append(f"picking one of the cheapest tenth of Sydney stations, typically {shop:.0f}c under the median, saves about <b>${TANK * shop / 100:.2f}</b>")
        if num(amp): worth.append(f"filling up before a price jump instead of just after it saves about <b>${TANK * amp / 100:.2f}</b>")
        own = [d for d in self.offers() if self.deal_page(d)]
        guides = []
        for d in own:
            if d["page"] not in [g for g, _ in guides]: guides.append((d["page"], {"woolworths": "Woolworths fuel discount: where it works and today’s prices",
                "coles": "Coles fuel docket and the Reddy Express offer: today’s prices", "reddy": "", "lock": "7-Eleven Fuel Price Lock: should you lock today?",
                "costco": "Costco fuel prices today, and whether membership pays"}.get(d["key"], d["name"])))
        body = ["<h1>Fuel discounts in Sydney</h1>",
                f'<p class="lead">On a {TANK} L tank, ' + "; ".join(worth) + ". So the best deal is timing and the station first, "
                "and a discount on top of them, not instead of them.</p>",
                f'<p class="small">Prices updated {esc(self.day)}. Each offer was checked against its own terms on the date beside it.</p>',
                self.verdict_card("U91", up) if r else "",
                "<h2>The main fuel discounts in Sydney, and the price before them</h2>",
                "<p>A discount only helps if the station wasn’t dearer to begin with. Beside each offer is today’s average Unleaded 91 price at the Sydney stations that take it, "
                f"against the Sydney median{med_now}. Costco’s is its E10 price against the E10 median.</p>",
                '<div class="scroll"><table><thead><tr><th>Discount</th><th>Where</th><th class="n">Saving</th><th class="n">Average price</th><th class="n">vs median</th>'
                '<th class="n">After the saving</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>",
                '<p class="small">Averages leave out prices over a week old and need at least three stations; Costco’s include its members-only sites. '
                "“After the saving” takes the full discount off the average; most offers also need a shop spend or a membership.</p>",
                "<h2>Guides to the big ones</h2>",
                "<ul>" + "".join(f'<li><a href="{up}{esc(p)}">{esc(t)}</a></li>' for p, t in guides if t) + "</ul>",
                "<h2>How each discount works</h2>",
                "<ul>" + "".join(f'<li><b>{esc(d["name"])}:</b> {esc(d["how"])} <a href="{esc(d["terms"])}" rel="noopener">Terms</a>'
                                 f' <span class="small">(checked {esc(short_date(d["checked"]))} {d["checked"][:4]})</span></li>' for d in self.offers()) + "</ul>",
                "<h2>Is the docket worth the drive?</h2>",
                "<p>Only if the station that takes it is within 4c of the cheapest one near you. A 4c docket at a station 8c over the cheapest nearby still costs you 4c a litre. "
                f'Check <a href="{up}fuel-prices/">today’s prices by suburb</a> first, and <a href="{up}fuel-price-forecast/">the forecast</a> to see whether waiting a few days beats both.</p>']
        qa = [("What is the cheapest way to buy petrol in Sydney?",
               "Fill up near the bottom of Sydney’s price cycle, at one of the cheapest stations near you, and add a discount if you have one"
               + (f". Timing is worth about {amp:.0f}c a litre" if num(amp) else "") + (f", the choice of station about {shop:.0f}c" if num(shop) else "")
               + ", and a supermarket docket 4c."),
              ("Can I use a Woolworths or a Coles fuel docket anywhere?",
               "No. Woolworths Everyday Rewards dockets work at participating Ampol Foodary, EG Ampol and U-GO sites, and Coles dockets at participating Shell Reddy Express sites."),
              ("Do fuel discounts stack?",
               "Some do. Shell Reddy Express’s terms say its 10c in-store offer is valid with the Coles docket (4c plus 10c), and NRMA says its member discount combines with the "
               "Woolworths docket at Ampol Foodary. 7-Eleven’s Fuel Price Lock can’t be combined with its partner codes or other app offers. Check each offer’s current terms."),
              ("Is there a fuel discount for seniors in NSW?",
               "Yes: NSW Seniors Card and Senior Savers Card holders get 4c a litre at participating United sites. See United’s terms for how to sign up.")]
        fq, fq_ld = self.faq(qa)
        body += [fq, self.deal_note(), self.sources_p()]
        # "fuel discounts" is what people type; "deals" barely registers (autocomplete, Nov 2026). The address stays.
        t = "Fuel discounts in Sydney: dockets, codes, live prices | Bowser"
        d = clip(f"Fuel discounts in Sydney for {self.sday}: Woolworths and Coles dockets, 7-Eleven Fuel Price Lock and codes, NRMA, seniors, Costco, "
                 "with today’s price at the stations that take each one.")
        self.page(path, "deals", "/petrol-deals-sydney/", t, d, "\n".join(x for x in body if x), crumbs=[("Fuel discounts", path)],
                  ld=[self._art(path, "Fuel discounts in Sydney", d), fq_ld], priority=0.8)
        for d in own:
            if d["key"] == "lock": self.lock_page(d)
            elif d["key"] == "woolworths": self.docket_page(d, None)
            elif d["key"] == "coles": self.docket_page(d, next((x for x in self.offers() if x["key"] == "reddy"), None))

    def lock_call(self):
        """(head, tone, sentence): whether to lock a 7-Eleven price today, from the Sydney U91 forecast. A lock never costs more
        than the pump (you pay the lower), so the forecast is about timing: lock before a rise, wait for the bottom of a fall."""
        r = self.live.get("U91")
        if not r or not num(r.get("now")) or not num(r.get("d7")): return None
        d7 = r["d7"]; pj = r.get("p_jump7"); cls = (r.get("verdict") or {}).get("cls")
        jump = f" The chance of a 5c-plus jump within a week is about {pj:.0%}." if num(pj) and pj >= 0.05 else ""
        if cls == "up" or d7 >= 1 or (num(pj) and pj >= 0.25):
            move = (f"Bowser expects the Sydney median for Unleaded 91 to rise about {cents(d7)} over the next week." if d7 >= 1 else
                    "Sydney prices may still edge down this week, but a jump is the bigger risk." if d7 <= -1 else
                    "Bowser expects little change in the Sydney median this week, but a jump is the bigger risk.")
            return ("Lock today", "act", f"{move}{jump} A lock now holds today’s price for 7 days, and you pay the pump price instead if it ends up lower.")
        if d7 <= -1:
            return ("No rush to lock", "wait", f"Bowser expects the Sydney median for Unleaded 91 to ease about {cents(d7)} over the next week. A lock can’t cost more than the pump price, "
                    "but you can hold only one at a time and can’t cancel it, so locking nearer the bottom should save more.")
        return ("Lock when you’re ready to fill", "calm", f"Bowser expects little change in the Sydney median for Unleaded 91 this week.{jump} "
                "A lock costs nothing, so lock when you know you’ll fill within 7 days.")

    def lock_page(self, d):
        up = "../"; path = d["page"]; f = "U91"
        pool = self.deal_pool(d, f); avg, med = self.deal_avg(d, f); top = self.cheapest(pool, f, 10)
        call = self.lock_call()
        body = ["<h1>7-Eleven Fuel Price Lock: should you lock today?</h1>"]
        if call:
            head, tone, txt = call
            body += [f'<p class="lead">Bowser’s answer for Sydney on {esc(self.day)}: <b>{esc(lc(head))}</b>. A lock never costs more than the pump price, '
                     "so the question is only when to use your one lock.</p>",
                     f'<div class="verdict {tone}"><span class="eyebrow">Bowser’s lock call for Sydney, {esc(self.sday)}</span><b>{esc(head)}</b><span>{esc(txt)}</span>'
                     '<span class="small">The call follows the Sydney median; the lock uses the 7-Elevens near you, which can differ. It’s a forecast, not a promise.</span></div>']
        if top:
            body += ["<h2>7-Eleven prices in Sydney today</h2>",
                     f"<p>The cheapest Unleaded 91 at a Sydney 7-Eleven today is <b>{c1(top[0]['p'][f][0])}c/L</b> at <a href=\"{up}{esc(top[0]['url'])}\">{esc(top[0]['name'])}</a>."
                     + (f" Across {len(pool)} Sydney 7-Elevens the average is {avg:.1f}c, {'about the same as' if abs(avg - med) < 0.5 else cents(avg - med) + (' under' if avg < med else ' over')} the Sydney median of {c1(med)}c."
                        if avg is not None and med is not None else "") + "</p>",
                     self.price_table(top, sort=f, up=up)]
        body += ["<h2>How the Fuel Price Lock works</h2>",
                 "<ul><li>In the My 7-Eleven app, lock the lowest price at the 7-Elevens near you. The lock lasts 7 days.</li>"
                 "<li>It covers one fill of up to 150 L, and the saving is capped at 25c a litre.</li>"
                 "<li>If the pump price is lower when you fill, you pay the pump price, so a lock never costs more.</li>"
                 "<li>You can hold one lock at a time, can’t cancel it, and can activate at most two in 24 hours.</li>"
                 "<li>Locking voids the app’s other fuel offers, and partner codes (such as Linkt’s 6c) can’t be used with a lock.</li></ul>",
                 f'<p>From 7-Eleven’s <a href="{esc(d["terms"])}" rel="noopener">Fuel Price Lock terms</a>, checked {esc(short_date(d["checked"]))} {d["checked"][:4]}.</p>',
                 "<h2>When a lock pays off</h2>",
                 "<p>A lock is worth most just before a price jump: lock at the bottom, and fill after prices have gone up. When prices are sliding, there’s no hurry, "
                 f'because a later lock will be lower. That’s what <a href="{up}fuel-price-forecast/">Bowser’s forecast</a> is for, and '
                 f'<a href="{up}petrol-price-cycle/">where Sydney is in its price cycle</a> shows why.</p>']
        qa = [("Should I lock my 7-Eleven fuel price today?", f"{call[0]}. {call[2]}" if call else "Bowser has no call today."),
              ("How does the 7-Eleven Fuel Price Lock work?",
               "In the My 7-Eleven app you lock the lowest price at the 7-Elevens near you for 7 days. When you fill, you pay the locked price or the pump price, whichever is lower, on up to 150 L."),
              ("What is the maximum discount with the 7-Eleven Fuel Price Lock?",
               f"The saving is capped at 25c a litre on up to 150 L, so at most $37.50 on one fill; on a {TANK} L tank, at most ${TANK * 25 / 100:.2f}."),
              ("Can I use a 7-Eleven fuel code with a price lock?",
               "No. Partner codes, such as Linkt’s 6c a litre barcode, can’t be used with a Fuel Price Lock.")]
        fq, fq_ld = self.faq(qa)
        body += [fq, self.deal_note(), self.sources_p()]
        t = "7-Eleven Fuel Price Lock: when to lock in Sydney | Bowser"
        desc = clip(f"Should you lock your 7-Eleven fuel price today? Bowser’s call for {self.sday}" + (f": {call[0].lower()}." if call else ".")
                    + " How the lock works, its limits, and today’s 7-Eleven prices in Sydney.")
        self.page(path, "lock", "/7-eleven-fuel-price-lock/", t, desc, "\n".join(x for x in body if x),
                  crumbs=[("Fuel discounts", "petrol-deals-sydney/"), ("7-Eleven Fuel Price Lock", path)],
                  ld=[self._art(path, "7-Eleven Fuel Price Lock: should you lock today?", desc), fq_ld], priority=0.7)

    def docket_page(self, d, extra):
        """A supermarket docket's page: today's prices at the stations that take it, before and after (and with `extra`, an
        offer that stacks with it: Reddy Express's in-store 10c)."""
        up = "../"; path = d["page"]; f = "U91"; coles = d["key"] == "coles"
        pool = self.deal_pool(d, f); avg, med = self.deal_avg(d, f); top = self.cheapest(pool, f, 15)
        where = "participating Shell Reddy Express sites" if coles else "participating Ampol Foodary, EG Ampol and U-GO sites"
        h1 = "Coles fuel docket: where it works and today’s prices" if coles else "Woolworths fuel discount: where it works and today’s prices"
        lead = f"The {'Coles fuel docket' if coles else 'Woolworths Everyday Rewards fuel docket'} takes {d['cut']}c a litre off at {where}."
        if avg is not None and med is not None:
            lead += (f" Today those Sydney stations average <b>{avg:.1f}c</b> for Unleaded 91, {'about the same as' if abs(avg - med) < 0.5 else cents(avg - med) + (' under' if avg < med else ' over')} "
                     f"the Sydney median of {c1(med)}c, so about <b>{avg - d['cut']:.1f}c</b> after the docket")
            if extra: lead += f", or {avg - d['cut'] - extra['cut']:.1f}c with the {extra['cut']}c in-store offer as well (with a $20 shop spend)"
            lead += "."
        body = [f"<h1>{esc(h1)}</h1>", f'<p class="lead">{lead}</p>', f'<p class="small">Prices updated {esc(self.day)}.</p>',
                self.verdict_card("U91", up) if "U91" in self.live else ""]
        if not coles:
            rows = []; cut = d["cut"]
            for b in d["brands"]:
                ps = [s["p"][f][0] for s in pool if s["brand"] == b and self.reg(s, f)]
                a = sum(ps) / len(ps) if len(ps) >= 3 else None
                name = f'<a href="{up}{esc(self.brand_url[b])}">{esc(b)}</a>' if b in self.brand_url else esc(b)
                rows.append(f'<tr><td>{name}</td><td class="n">{len(ps)}</td><td class="n">{f"{a:.1f}" if a is not None else "–"}</td>'
                            f'<td class="n">{self.gap_span(a, med)}</td><td class="n">{f"{a - cut:.1f}" if a is not None else "–"}</td></tr>')
            body += ["<h2>Where it works, brand by brand</h2>",
                     '<div class="scroll"><table><thead><tr><th>Brand</th><th class="n">Sydney stations with a U91 price</th><th class="n">Average U91</th><th class="n">vs median</th>'
                     f'<th class="n">After {d["cut"]}c</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"]
        if top:
            body += [f"<h2>Cheapest stations that take the docket today</h2>",
                     f"<p>The 15 cheapest Unleaded 91 prices at these brands in Sydney, before the docket. Take {d['cut']}c off each"
                     + (f", or {d['cut'] + extra['cut']}c with the in-store offer" if extra else "") + ". A few sites of these brands may not take it.</p>",
                     self.price_table(top, sort=f, up=up)]
        how = [d] + ([extra] if extra else [])
        body += ["<h2>How it works</h2>",
                 "<ul>" + "".join(f'<li><b>{esc(x["name"])}:</b> {esc(x["how"])} <a href="{esc(x["terms"])}" rel="noopener">Terms</a></li>' for x in how) + "</ul>"]
        nrma = next((x for x in self.offers() if x["key"] == "nrma"), None)
        if nrma and not coles:
            body.append(f"<p>NRMA members can add NRMA’s {nrma['cut']}c a litre at participating Ampol Foodary sites (not EG Ampol); NRMA says it combines with the docket. "
                        f'<a href="{esc(nrma["terms"])}" rel="noopener">NRMA’s terms</a>.</p>')
        body.append(f'<p>See <a href="../petrol-deals-sydney/">the main fuel discounts in Sydney</a>, and <a href="{up}fuel-price-forecast/">the forecast</a> before a big fill: '
                    "waiting a few days can be worth more than the docket.</p>")
        if coles:
            qa = [("Where can I use a Coles fuel docket?", "At participating Shell Reddy Express sites (the stations once called Coles Express)."),
                  ("How much is the Coles fuel docket?", "4c a litre on up to 150 L, after spending $30 or more in one shop at Coles. It’s in the Flybuys app and lasts 4 weeks."),
                  ("Can I combine the Coles docket with other discounts?",
                   "Reddy Express’s terms say its in-store offer is valid with the docket: spend $20 or more in the shop in the same transaction for another 10c a litre. Not with other offers or fuel cards.")]
            t, title_h = "Coles fuel docket: Shell Reddy Express prices today | Bowser", "Coles fuel docket"
        else:
            qa = [("Where can I use my Woolworths fuel discount?", "At participating Ampol Foodary, EG Ampol and U-GO sites, by scanning your Everyday Rewards card."),
                  ("How much is the Woolworths fuel discount?",
                   "4c a litre, after spending $30 or more in one shop at Woolworths, used within 28 days. Up to 150 L; Woolworths’ U-GO page says the first 75 L at U-GO."),
                  ("Does the Woolworths fuel docket work with NRMA?", "NRMA says its member discount combines with the docket at participating Ampol Foodary sites, but not at EG Ampol.")]
            t, title_h = "Woolworths fuel discount: today’s prices at Ampol | Bowser", "Woolworths fuel discount"
        fq, fq_ld = self.faq(qa)
        body += [fq, self.deal_note(), self.sources_p()]
        desc = clip(f"{title_h} for {self.sday}: where it works, how much it saves, and today’s Unleaded 91 prices at the Sydney stations that take it"
                    + (f", about {avg - d['cut']:.1f}c on average after the docket." if avg is not None else "."))
        self.page(path, "docket", "/" + path, t, desc, "\n".join(x for x in body if x),
                  crumbs=[("Fuel discounts", "petrol-deals-sydney/"), (title_h, path)], ld=[self._art(path, h1, desc), fq_ld], priority=0.7)

    def badge_page(self):
        """/badge/: the embeddable cycle-stage badge, a preview and the code to copy. The image itself is written apart
        (write_badge, from export_api.py), so a failed page build never takes it down on the sites that show it."""
        img = f"{self.site}/{BADGE_PATH}"
        alt = "Where Sydney is in the petrol price cycle today, from Bowser"
        code = (f'<a href="{self.site}/petrol-price-cycle/" title="Sydney petrol price cycle today">'
                f'<img src="{img}" width="{BADGE_W}" height="{BADGE_H}" alt="{alt}" loading="lazy"></a>')
        st = self.stage()
        now = f" Today it says <b>{esc(st[2])}</b>: day {st[0]} since the last price jump." if st else ""
        body = ["<h1>A free Sydney petrol price badge for your website</h1>",
                '<p class="lead">Show your readers where Sydney is in its petrol price cycle, today, with a small image that updates itself. '
                "Free for news sites, community pages, car clubs and blogs.</p>",
                f'<p class="badge"><img src="sydney.svg" width="{BADGE_W}" height="{BADGE_H}" alt="{esc(alt)}"></p>',
                f"<p>{now.strip()}</p>" if now else "",
                "<h2>Add it to your site</h2>",
                "<p>Copy this into your page’s HTML, where you want the badge to appear:</p>",
                f"<pre><code>{esc(code)}</code></pre>",
                "<p>It is a plain image in a link: no script, no cookies, no tracking, and nothing that slows your page. "
                f"It works anywhere you can add HTML or an image with a link (on a site that only takes an image address, use <code>{esc(img)}</code> "
                f'and link it to <code>{esc(self.site)}/petrol-price-cycle/</code>).</p>',
                "<h2>What it shows</h2>",
                "<p>Sydney petrol prices move in a cycle: a sudden jump of 15c a litre or more, then weeks of slow falls. The badge says which part of it Sydney is in, "
                "from the same figures as the <a href=\"../petrol-price-cycle/\">price cycle page</a>:</p>",
                "<ul><li><b>A jump looks likely soon</b>: Bowser’s forecast puts the chance of a 5c-plus jump within a week at 35% or more.</li>"
                "<li><b>Near the top</b>: a jump began within the last week.</li>"
                "<li><b>Falling</b>: the slow slide after a jump, when waiting usually pays.</li>"
                "<li><b>Late in the cycle</b>: a jump is due by the usual timing.</li>"
                "<li><b>Running long</b>: this cycle has lasted longer than usual.</li></ul>",
                "<p>It is rebuilt several times a day and shows the day it is for, so readers can see it is current. "
                "If the cycle stage can’t be worked out, it shows Bowser’s call for Unleaded 91 instead.</p>",
                "<h2>Terms</h2>",
                "<p>Free to use, with no sign-up. Please keep the link and the credit on the image: prices come from NSW FuelCheck "
                "(© State of New South Wales, NSW Fair Trading, CC BY-SA 3.0 AU) and the stage is Bowser’s own estimate, for planning, not financial advice. "
                f"Questions, or want a different size? Email {CONTACT}.</p>", self.sources_p()]
        self.page("badge/", "badge", "/badge/", "Free Sydney petrol price badge for your website | Bowser",
                  "A free image for news and community sites that shows where Sydney is in its petrol price cycle today. No script, no tracking; updates itself.",
                  "\n".join(b for b in body if b), crumbs=[("Badge", "badge/")], priority=0.3)

    def finish(self):
        """robots.txt, sitemap.xml (the dashboard's address first) and llms.txt (a plain summary for AI assistants)."""
        rules = "Allow: /\nDisallow: /api/v1/station/\n"   # the per-station JSON files are the app's, one per station page here
        with open(os.path.join(self.out, "robots.txt"), "w", encoding="utf-8") as fh:
            fh.write("# Everyone is welcome, search engines and AI assistants alike. Prices are CC BY-SA 3.0 AU: credit NSW FuelCheck and Bowser.\n"
                     f"User-agent: *\n{rules}\n" + "".join(f"User-agent: {b}\n" for b in AI_BOTS) + f"{rules}\nSitemap: {self.site}/sitemap.xml\n")
        rows = [("", 1.0, self.asof)] + self.urls
        with open(os.path.join(self.out, "sitemap.xml"), "w", encoding="utf-8") as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                     + "".join(f"<url><loc>{esc(self.site + '/' + p)}</loc><lastmod>{lm}</lastmod><priority>{pr:.1f}</priority></url>\n" for p, pr, lm in rows)
                     + "</urlset>\n")
        u = self.site; md = lambda s: re.sub(r"\S+://\S+|[\[\]\n\r<>()]", " ", str(s))[:80]   # feed text can't add a link or break one
        syd = [s for s in self.st if not s.get("out")]
        lines = ["# Bowser", "",
                 f"> Bowser (checkbowser.app) is an independent, free site and app for fuel prices in "
                 + ("New South Wales and the Australian Capital Territory" if self.any_out else "New South Wales") + f", Australia. It shows today's price at {len(self.st):,} "
                 + "service stations" + (f" (including {len(self.act):,} ACT stations that report to NSW FuelCheck)" if self.act else "")
                 + ", taken from the NSW Government's FuelCheck service, and adds a forecast for Sydney only that says whether to fill up now or wait. "
                 "Pages are rebuilt about five times a day. Bowser is not affiliated with the NSW Government or any fuel retailer.", "",
                 f"## Today ({self.day})", ""]
        for f in FUELS:
            if f not in self.live: continue
            r = self.live[f]; c = self.cheapest(syd, f, 1)
            lines.append(f"- Sydney {NAME[f]}: median {c1(r['now'])} cents per litre; expected {c1(r['now'] + r['d7'])} in 7 days "
                         f"(likely range {r['now'] + r['lo7']:.0f} to {r['now'] + r['hi7']:.0f}); Bowser's call: {(r.get('verdict') or {}).get('head', 'none')}"
                         + (f"; cheapest {c1(c[0]['p'][f][0])} at {md(c[0]['name'])}" if c else "") + ".")
        lines += ["", "Prices are in Australian cents per litre. A station can change its price at any time; each page shows the date it was built.", "",
                  "## Main pages", "",
                  f"- [Sydney fuel price forecast]({u}/fuel-price-forecast/): the 14-day outlook for each fuel, the chance of a price jump, and how accurate past calls were.",
                  f"- [Fuel prices today]({u}/fuel-prices/): the cheapest stations in Sydney, each region outside it, and a link to every suburb.",
                  f"- [The Sydney petrol price cycle]({u}/petrol-price-cycle/): how the cycle works, how long it is each year, and where it is now.",
                  f"- [Bowser and NSW FuelCheck]({u}/nsw-fuelcheck/): what FuelCheck is and what Bowser adds to it.",
                  *([f"- [How accurate the forecast is]({u}/fuel-price-forecast/accuracy/): the fill-or-wait call replayed on every day since 2021, live calls, and the error against assuming no change."] if self.has_acc else []),
                  *([f"- [Weekly outlooks]({u}/fuel-price-forecast/weekly/): each week's saved forecast for every fuel (normally Monday's), and how it turned out a week and two weeks later."] if any(w.get("done") for w in self.weeks) else []),
                  *([f"- [Best day to buy petrol in Sydney]({u}/best-day-to-buy-petrol/): the price on each weekday since 2019 (cheapest and dearest {max(self.stats['dow']) - min(self.stats['dow']):.1f}c apart) and what matters instead."] if self.has_best else []),
                  *([f"- [Petrol prices at Christmas]({u}/petrol-prices-christmas/): what the Sydney price did over each Christmas since {self.xmas[0]['year']}, and this year's outlook."] if self.xmas else []),
                  f"- [Free cycle-stage badge]({u}/badge/): an image for other websites showing where Sydney is in its petrol price cycle today, linking back here.",
                  f"- [Prices by brand]({u}/brands/): 7-Eleven, Ampol, BP, Shell, Costco and others compared.",
                  f"- [Fuel discounts in Sydney]({u}/petrol-deals-sydney/): supermarket dockets, 7-Eleven Fuel Price Lock and codes, NRMA, seniors and Costco, with today's price at the stations that take each.",
                  *([f"- [7-Eleven Fuel Price Lock]({u}/7-eleven-fuel-price-lock/): whether to lock today, from the Sydney forecast, and how the lock works."] if self.built("lock") else []),
                  *([f"- [Woolworths fuel discount]({u}/woolworths-fuel-discount/): where it works and today's prices before and after."] if self.built("woolworths") else []),
                  *([f"- [Coles fuel docket]({u}/coles-fuel-docket/): where it works and today's prices before and after."] if self.built("coles") else [])]
        lines += [f"- [{NAME[f]} prices in Sydney]({u}/fuel-prices/{FSLUG[f]}/)" for f in FUELS if f in self.live]
        if self.regions:
            lines += ["", f"## Regions outside Sydney ({'NSW and ACT; ' if self.act else ''}prices only, no forecast)", ""] + [f"- [{md(n)} fuel prices]({u}/{self.region_url[n]})" for n in sorted(self.regions)]
        # an ACT example: the ACT suburb with the most stations (the data's own, never a fixed address)
        act_subs = sorted({s["sub"] for s in self.act if s["sub"]}, key=lambda k: (-len(self.subs[k]), k))
        lines += ["", "## Page patterns", "",
                  f"- One page per suburb: {u}/fuel-prices/{{suburb}}-{{postcode}}/ (for example {u}/fuel-prices/parramatta-2150/"
                  + (f", or in the ACT {u}/{self.sub_url[act_subs[0]]}" if act_subs else "") + ").",
                  f"- One page per station, listed at {u}/station/. Sydney stations also have a price history and their own fill-or-wait call.",
                  f"- {u}/sitemap.xml lists every page except stations that have reported no price for over a month.", "",
                  "## Data", "",
                  f"- [stations.json]({u}/api/v1/stations.json): every station with today's price for each fuel.",
                  f"- [forecast.json]({u}/api/v1/forecast.json): the Sydney forecast for each fuel.",
                  f"- [track.json]({u}/api/v1/track.json): past fill-or-wait calls and how each turned out.",
                  f"- [meta.json]({u}/api/v1/meta.json): when the data was built, sources and licence.", "",
                  "## Using this information", "",
                  "- Station prices come from NSW FuelCheck, (c) State of New South Wales (NSW Fair Trading), licensed CC BY-SA 3.0 AU. Credit NSW FuelCheck and Bowser when quoting them.",
                  "- Forecasts are Bowser's own estimates for planning, not financial advice, and cover Sydney only.",
                  f"- Quote prices with their date ({self.asof}) and link to the page they came from.",
                  f"- About: {u}/about/  Privacy: {u}/privacy/", ""]
        with open(os.path.join(self.out, "llms.txt"), "w", encoding="utf-8") as fh: fh.write("\n".join(lines))
        with open(os.path.join(self.out, f"{INDEXNOW_KEY}.txt"), "w", encoding="utf-8") as fh: fh.write(INDEXNOW_KEY)


FUEL_NOTE = {
    "U91": lambda S: "Unleaded 91 is regular unleaded petrol, the fuel most Australian petrol cars are built to run on, and the price this site’s Sydney forecast is centred on. "
                     "It follows Sydney’s price cycle closely: sharp jumps, then weeks of slow falls.",
    "E10": lambda S: "E10 is regular unleaded blended with up to 10% ethanol. Most petrol cars made since 2005 can use it, but check your owner’s manual or fuel flap first."
                     + (f" Since 2023 it has averaged about {S['e10_disc']:.1f}c a litre under Unleaded 91 in Sydney; cars use slightly more E10 per kilometre, so a small discount may not make it cheaper to run." if num(S.get("e10_disc")) else ""),
    "P95": lambda S: "Premium 95 is a higher-octane petrol that many European and turbocharged cars require; using it in a car built for 91 rarely pays for itself."
                     + (f" Since 2023 it has averaged about {S['p95_prem']:.0f}c a litre more than Unleaded 91 in Sydney, and the step varies a lot between stations, so it pays to compare." if num(S.get("p95_prem")) else ""),
    "P98": lambda S: "Premium 98 is the highest-octane petrol commonly sold, required by some performance engines."
                     + (f" Since 2023 it has averaged about {S['p98_prem']:.0f}c a litre more than Unleaded 91 in Sydney. The premium differs widely from station to station, which makes shopping around worth more for 98 than for any other fuel." if num(S.get("p98_prem")) else ""),
    "DL": lambda S: "Diesel doesn’t follow Sydney’s petrol price cycle. Its price tracks the wholesale cost, which follows international diesel prices and the Australian dollar, so it has no "
                    "sudden jumps followed by slow slides. It changes gradually from day to day, but when oil prices move it can rise or fall a long way over a few weeks, "
                    "so the call above is still worth a look before a big fill.",
}


def home_head(stations, forecast, site=SITE, og="og.png"):
    """The dashboard's <title> and the tags after it: description, canonical, Open Graph, icons and JSON-LD. `og`: the
    link-preview image under the site, today's call (og_image.py, "og/today.png?d=…") when export_api.py drew it."""
    site = site.rstrip("/"); live = {r["fuel"]: r for r in forecast["live"]}
    r = live.get("U91") or next(iter(live.values())); v = (r.get("verdict") or {}).get("head", "")
    n = sum(usable(s) is not None for s in stations["stations"]); day = short_date(stations["asof"])
    # "Should you fill up today?" is the question the dashboard answers and the phrase PetrolPulse builds its title on
    # (docs/SEO.md, competitors); the forecast page keeps "fuel price forecast … next week", so the two don't compete
    title = "Should you fill up today? Sydney fuel prices | Bowser"
    wide = any(s.get("out") for s in stations["stations"])   # the rest of NSW and the ACT stations that report to FuelCheck
    lead = f"Should you fill up today? Bowser’s call for Sydney: {(v or 'no call today').lower()}. {NAME[r['fuel']]} is {c1(r['now'])}c/L ({day})"
    desc = f"{lead}, with today’s prices at {n:,} {'NSW and ACT' if wide else 'Sydney'} stations."
    if len(desc) > 155: desc = f"{lead}. Prices at {n:,} {'NSW and ACT' if wide else 'Sydney'} stations."   # the longest call with a 4-digit count
    area = {"areaServed": STATES} if wide else {}
    org = {"@type": "Organization", "@id": site + "/#org", "name": "Bowser", "url": site + "/", "logo": site + "/apple-touch-icon.png", **area}
    ld = {"@context": "https://schema.org", "@graph": [
        org, {"@type": "WebSite", "@id": site + "/#site", "name": "Bowser", "alternateName": ["Check Bowser", "checkbowser.app"], "url": site + "/",
              "inLanguage": "en-AU", "publisher": {"@id": site + "/#org"}, "description": "Fuel prices at every NSW and ACT station that reports to NSW FuelCheck, and a Sydney forecast of when to fill up." if wide
              else "Sydney fuel prices today, the cheapest stations near you and a forecast of when to fill up."},
        {"@type": "WebApplication", "name": "Bowser", "url": site + "/", "applicationCategory": "UtilitiesApplication", "operatingSystem": "Any", **area,
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "AUD"}, "publisher": {"@id": site + "/#org"}}]}
    alt = f"Bowser: {v}. {NAME[r['fuel']]} in Sydney, {c1(r['now'])}c/L on {day}" if v else "Bowser: fill up now, or wait?"   # the image's words
    return "\n".join([
        f"<title>{esc(title)}</title>", f'<meta name="description" content="{esc(desc)}">', f'<link rel="canonical" href="{site}/">',
        '<meta property="og:type" content="website">', '<meta property="og:site_name" content="Bowser">', '<meta property="og:locale" content="en_AU">',
        f'<meta property="og:title" content="{esc(title)}">', f'<meta property="og:description" content="{esc(desc)}">',
        f'<meta property="og:url" content="{site}/">', f'<meta property="og:image" content="{site}/{esc(og)}">',
        '<meta property="og:image:width" content="1200">', '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{esc(alt)}">',
        '<meta name="twitter:card" content="summary_large_image">', f'<meta name="twitter:image" content="{site}/{esc(og)}">',
        '<link rel="icon" href="favicon.svg" type="image/svg+xml">', '<link rel="apple-touch-icon" href="apple-touch-icon.png">', jsonld(ld)])


def home_links(stations, forecast):
    """Plain links from the dashboard's footer to the search pages (the busiest suburbs, the fuels, the guides).
    Built from the same Site as the pages, so every link leads to a page that was written."""
    S = Site(None, stations, forecast)
    top = sorted(sorted(S.subs, key=lambda k: (-len(S.subs[k]), k))[:16])
    a = lambda href, text: f'<a href="{esc(href)}">{esc(text)}</a>'
    syd = [s for s in S.st if not s.get("out")]; today = []
    for f in FUELS:
        if f not in S.live: continue
        r = S.live[f]; c = S.cheapest(syd, f, 1)
        today.append(f"{NAME[f]} {c1(r['now'])}c/L" + (f" (cheapest {c1(c[0]['p'][f][0])}c at {esc(c[0]['name'])})" if c else ""))
    r = S.live.get("U91") or next(iter(S.live.values()))
    summary = (f"<div>Sydney fuel prices on {esc(S.day)}, median across Sydney stations: {'; '.join(today)}. "
               f"Bowser’s call for {esc(NAME[r['fuel']])}: {esc((r.get('verdict') or {}).get('head') or 'no call today')}. {esc(S.outlook(r['fuel']))}</div>")
    return (summary + "<div>" + " · ".join([a("fuel-prices/", "Fuel prices by suburb")] + [a(f"fuel-prices/{FSLUG[f]}/", f"{NAME[f]} prices") for f in FUELS if f in S.live]
                                 + [a("fuel-price-forecast/", "Fuel price forecast")] + ([a("fuel-price-forecast/accuracy/", "Forecast accuracy")] if S.has_acc else [])
                                 + [a("petrol-price-cycle/", "Sydney petrol price cycle")] + ([a("best-day-to-buy-petrol/", "Best day to buy petrol")] if S.has_best else [])
                                 + [a("petrol-deals-sydney/", "Fuel discounts")] + ([a("7-eleven-fuel-price-lock/", "7-Eleven Fuel Price Lock")] if S.built("lock") else [])
                                 + [ a("brands/", "Prices by brand"),
                                    a("nsw-fuelcheck/", "About NSW FuelCheck"), a("about/", "About Bowser"), a("privacy/", "Privacy")]) + "</div>"
            + ("<div>Popular suburbs: " + " · ".join(a(S.sub_url[k], S.sub_label[k]) for k in top) + "</div>" if top else ""))


def clear(out):
    """Remove everything this module writes, so a failed run leaves no half-built pages to publish."""
    for d in OWN: shutil.rmtree(os.path.join(out, d), ignore_errors=True)
    for f in ["404.html", "robots.txt", "sitemap.xml", "llms.txt", f"{INDEXNOW_KEY}.txt"]:
        if os.path.exists(os.path.join(out, f)): os.remove(os.path.join(out, f))


def build(out, stations, forecast, history=None, details=None, track=None, site=SITE, static=None, weekly=None):
    """Write every search page under `out`. Returns {"pages": n, "stations": n, "suburbs": n}. Raises on bad input:
    the caller (export_api.py) then clears the pages and publishes the rest of the site without them."""
    clear(out)
    S = Site(out, stations, forecast, history, details, track, site, weekly)
    if len(S.st) < 1 or "U91" not in S.live: raise ValueError(f"search pages: {len(S.st)} stations, fuels {sorted(S.live)}")
    S.hub()
    for f in FUELS:
        if f in S.live: S.fuel(f)
    for n in sorted(S.regions): S.region(n)
    for k in sorted(S.subs): S.suburb(k)
    S.station_index()
    for s in S.st: S.station(s)
    S.brand_pages(); S.guides()
    try:
        S.weekly_pages()
    except Exception as e:   # a weekly page bug drops those pages only, never the rest of the site
        print(f"seo_pages: WARNING weekly outlook pages skipped: {type(e).__name__}: {e}")
        S.urls = [u for u in S.urls if not u[0].startswith("fuel-price-forecast/") or u[0].count("/") < 2 or u[0] == "fuel-price-forecast/accuracy/"]
    if S.has_acc: S.accuracy()
    if S.has_best: S.best_day()
    if S.xmas: S.christmas()
    S.deals()
    S.badge_page()
    S.finish()
    if static:
        for f in STATIC:
            if os.path.exists(os.path.join(static, f)): shutil.copyfile(os.path.join(static, f), os.path.join(out, f))
    seen = [u[0] for u in S.urls]
    if len(set(seen)) != len(seen): raise ValueError("search pages: two pages share an address")
    return {"pages": len(seen), "stations": len(S.st), "suburbs": len(S.subs), "brands": len(S.brand_url), "regions": len(S.regions)}
