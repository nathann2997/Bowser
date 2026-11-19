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
  OUT/petrol-price-cycle/             guide: the Sydney price cycle and where it is now
  OUT/nsw-fuelcheck/                  guide: what NSW FuelCheck is and how Bowser uses it
  OUT/about/, OUT/privacy/            who runs the site, what is counted
  OUT/404.html, OUT/robots.txt, OUT/sitemap.xml, OUT/llms.txt (a plain summary for AI assistants)

Links between pages are relative (../), so the site also works under a sub-path; canonical, Open Graph and sitemap
addresses use SITE. Each page carries a hash Content-Security-Policy for its one style block and one script (the
anonymous visit counter, the same rule as share.html). Wholesale (AIP) figures are left out on purpose: see DATA-LICENSE.md.
A station outside Sydney (`out: 1`, once the all-NSW station list is live) gets its prices but no forecast wording.
"""
import base64, datetime as dt, hashlib, html, json, math, os, re, shutil, statistics

SITE = "https://checkbowser.app"
FUELS = ["U91", "E10", "P95", "P98", "DL"]          # fuels.py order; the pages' own copy so this file has no imports
NAME = {"U91": "Unleaded 91", "E10": "E10", "P95": "Premium 95", "P98": "Premium 98", "DL": "Diesel"}
SHORT = {"U91": "U91", "E10": "E10", "P95": "95", "P98": "98", "DL": "Diesel"}
FSLUG = {"U91": "unleaded-91", "E10": "e10", "P95": "premium-95", "P98": "premium-98", "DL": "diesel"}
TONE = {"now": "act", "by": "act", "wait": "wait", "hi": "wait", "up": "act", "down": "wait"}   # anything else: calm
OWN = ["fuel-prices", "station", "brands", "fuel-price-forecast", "petrol-price-cycle", "nsw-fuelcheck", "about", "privacy"]
STATIC = ["favicon.svg", "apple-touch-icon.png", "og.png"]
TANK = 50                                           # litres, for "a fill costs"
NEAR_KM, STALE = 5.0, 7                             # "nearby" radius; a price older than this many days is flagged
BRAND_MIN = 3
DEAD = 30                                           # every price older than this: the page stays, but out of search (noindex)
PUBLISHED = "2026-11-17"                            # when the guides first went up (Article datePublished)
# Regional centres outside Sydney: a station joins the nearest one within its radius (km). Each gets a page.
REGIONS = [("Newcastle", -32.93, 151.75, 32), ("Central Coast", -33.36, 151.38, 28), ("Wollongong", -34.45, 150.87, 30),
           ("Southern Highlands", -34.48, 150.42, 18), ("Taree and Forster", -32.02, 152.48, 25), ("Lithgow", -33.48, 150.15, 12),
           ("Hunter Valley", -32.75, 151.45, 20), ("Canberra and Queanbeyan", -35.30, 149.13, 25), ("Coffs Harbour", -30.30, 153.11, 20),
           ("Port Macquarie", -31.43, 152.91, 20), ("Northern Rivers", -28.81, 153.35, 35), ("Tweed Heads", -28.20, 153.53, 25),
           ("Tamworth", -31.09, 150.93, 20), ("Armidale", -30.51, 151.67, 15), ("Wagga Wagga", -35.12, 147.37, 20), ("Albury", -36.07, 146.92, 20),
           ("Dubbo", -32.25, 148.60, 20), ("Orange", -33.28, 149.10, 20), ("Bathurst", -33.42, 149.58, 20), ("Nowra and Shoalhaven", -34.88, 150.60, 22),
           ("Goulburn", -34.75, 149.72, 15), ("Griffith", -34.29, 146.05, 15), ("Broken Hill", -31.95, 141.45, 15)]
REGION_MIN = 5
# Crawlers named so their owners' own "is this site open to us" checks pass; the rules are the same for everyone.
AI_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User", "PerplexityBot", "Perplexity-User",
           "Google-Extended", "Applebot-Extended", "Amazonbot", "meta-externalagent", "CCBot", "Bingbot", "DuckAssistBot"]
state_of = lambda pc: "ACT" if isinstance(pc, int) and (2600 <= pc <= 2618 or 2900 <= pc <= 2920) else "NSW"
# The privacy and support address shown on /privacy/ and /about/ (Google Play requires a contact in the privacy policy).
# The owner's choice (2026-11-18). No page links to the code repository: the owner wants the source kept private.
CONTACT_EMAIL = "checkbowser@gmail.com"
CONTACT = f'<a href="mailto:{html.escape(CONTACT_EMAIL, quote=True)}">{html.escape(CONTACT_EMAIL)}</a>'

esc = lambda v: html.escape(str(v), quote=True)
num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v
c1 = lambda v: f"{v:.1f}"
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
    odd = lambda s: bool(re.search(r"\d", s)) or s.strip().lower() in ("", "nsw")
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
    return p or None


# ---- the look: the dashboard's tokens (template.html), one style block shared by every page
CSS = """:root{--bg:#f6f6f3;--surface:#fff;--sunk:#eeefeb;--line:#e2e3df;--fg:#141618;--fg2:#45494d;--muted:#6f7479;--link:#1d62b5;--chip:#ffb22e;--cheap:#14865c;--dear:#c4511f;--retail:#eb6834;--median:#8a9096;--band:rgba(235,104,52,.14);--act-bg:#fff3d6;--act-fg:#7a4a00;--wait-bg:#e4eefa;--wait-fg:#1b5799;--calm-bg:#eceeea;--calm-fg:#3d4246;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#0f1113;--surface:#181b1e;--sunk:#131618;--line:#2a2e33;--fg:#eef0f2;--fg2:#c2c7cc;--muted:#8b9197;--link:#6aa9f0;--cheap:#3cc28f;--dear:#f08a5d;--retail:#e5703f;--median:#8b9197;--band:rgba(229,112,63,.2);--act-bg:#2e2410;--act-fg:#ffcf7a;--wait-bg:#122238;--wait-fg:#9cc6f7;--calm-bg:#1d2124;--calm-fg:#c2c7cc}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg2);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--link)}a:hover{text-decoration-thickness:2px}:focus-visible{outline:2px solid var(--link);outline-offset:2px}
h1,h2,h3{color:var(--fg);margin:0;text-wrap:balance}h1{font-size:30px;line-height:1.15;letter-spacing:-.5px}h2{font-size:21px;letter-spacing:-.2px;margin-top:8px}h3{font-size:16px}
p{margin:0;max-width:72ch}ul{margin:0;padding-left:20px;max-width:72ch}li{margin:4px 0}
.wrap{max-width:960px;margin:0 auto;padding:16px 16px 56px;display:flex;flex-direction:column;gap:20px}main{display:flex;flex-direction:column;gap:16px;min-width:0}.wrap>*,main>*{min-width:0;max-width:100%}body{overflow-wrap:break-word}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.logo{display:flex;align-items:center;gap:8px;font-weight:800;font-size:22px;color:var(--fg);text-decoration:none;letter-spacing:-.3px}.logo svg{width:24px;height:24px}
nav{display:flex;gap:4px 16px;flex-wrap:wrap;font-size:14px;font-weight:600}nav a{text-decoration:none}nav a:hover{text-decoration:underline}
.crumbs{font-size:13px;color:var(--muted)}.crumbs a{color:var(--muted)}
.lead{font-size:18px;color:var(--fg)}.small{font-size:13px;line-height:1.45;color:var(--muted)}
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


class Site:
    def __init__(self, out, stations, forecast, history=None, details=None, track=None, site=SITE):
        self.out, self.site = out, site.rstrip("/")
        self.asof = stations["asof"]; self.day, self.sday = long_date(self.asof), short_date(self.asof)
        self.live = {r["fuel"]: r for r in forecast["live"]}
        self.stats, self.fc_asof = forecast.get("stats") or {}, forecast.get("asof") or self.asof
        self.history, self.details, self.track = history or {}, details or {}, track or {}
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
            self.st.append(dict(s, id=str(s["id"]), name=name, brand=b, sub=k, p=p, s=str(s.get("s") or "NSW"),
                                url=f"station/{slug(name) or 'station'}-{s['id']}/", main=next(f for f in FUELS if f in p)))
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
        regs = {n.lower() for n, *_ in REGIONS}
        self.sub_label = {k: k[0] if names[k[0]] == 1 and k[0].lower() not in regs else f"{k[0]} {k[1]}" for k in self.subs}
        self.sub_at = {k: (sum(s["la"] for s in v) / len(v), sum(s["lo"] for s in v) / len(v)) for k, v in self.subs.items()}
        self.brands = {}
        for s in self.st: self.brands.setdefault(s["brand"], []).append(s)
        self.grid = {}
        for s in self.st: self.grid.setdefault(self._cell(s["la"], s["lo"]), []).append(s)
        # A brand page needs 3+ stations and a current price to lead with (else nothing links to it)
        self.brand_f0 = {b: next((f for f in FUELS if self.cheapest(v, f, 1, members=True)), None) for b, v in self.brands.items()}
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
        self.n_syd = sum(not s.get("out") for s in self.st)

    # ---- small helpers
    _cell = staticmethod(lambda la, lo: (int(math.floor(la / 0.06)), int(math.floor(lo / 0.06))))   # cells of about 6 km
    fresh = staticmethod(lambda s, f: f in s["p"] and not (num(s["p"][f][1]) and s["p"][f][1] > STALE))
    dead = staticmethod(lambda s: all(num(p[1]) and p[1] > DEAD for p in s["p"].values()))   # nothing reported for a month

    def changed(self, pool):
        """The day the newest price among `pool` was reported (asof less its age in days): a sitemap lastmod for pages
        outside Sydney, whose content moves only with their prices. Sydney pages carry the day's forecast call, so they keep asof."""
        ages = [p[1] for s in pool for p in s["p"].values() if num(p[1]) and p[1] >= 0]
        if not ages: return self.asof
        return (dt.date.fromisoformat(self.asof) - dt.timedelta(days=int(min(ages)))).isoformat()

    def median(self, pool, f):
        """The middle fresh price for fuel f among `pool` (members-only sites left out), or None under 3 prices."""
        ps = [s["p"][f][0] for s in pool if self.fresh(s, f) and not s.get("m")]
        return statistics.median(ps) if len(ps) >= 3 else None

    @staticmethod
    def faq(items):
        """Questions with short answers: (html, FAQPage JSON-LD). items: [(question, answer as plain text)]."""
        htm = "<h2>Quick answers</h2>" + "".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in items)
        return htm, {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in items]}

    def near(self, at, radius=NEAR_KM):
        """Stations within `radius` km of a (lat, lon), nearest first, as (km, station)."""
        a, b = self._cell(*at)
        hits = [(km(at, (s["la"], s["lo"])), s) for i in (a - 1, a, a + 1) for j in (b - 1, b, b + 1) for s in self.grid.get((i, j), [])]
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

    def verdict_card(self, f):
        r = self.live[f]; v = r.get("verdict") or {}
        return (f'<div class="verdict {TONE.get(v.get("cls"), "calm")}"><span class="eyebrow">Bowser’s call for Sydney {esc(NAME[f])}, {esc(self.sday)}</span>'
                f'<b>{esc(v.get("head", "No call today"))}</b><span>{esc(self.outlook(f))}</span></div>')

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
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#ffb22e">
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
<nav aria-label="More"><a href="{up}fuel-prices/">Sydney fuel prices</a><a href="{up}station/">All stations</a><a href="{up}nsw-fuelcheck/">About NSW FuelCheck</a><a href="{up}about/">About Bowser</a><a href="{up}privacy/">Privacy</a></nav>
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
                tds.append(f'<td class="{cls}">{c1(p[0])}{f"<br><span class=small>{p[1]} days old</span>" if old else ""}</td>')
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
        f0 = next((f for f in FUELS if self.cheapest(pool, f, 1)), None) or next(f for f in FUELS if any(f in s["p"] for s in pool))
        top = (self.cheapest(pool, f0, 1) or self.cheapest(pool, f0, 1, members=True) or [min((s for s in pool if f0 in s["p"]), key=lambda s: s["p"][f0][0])])[0]
        n = len(pool); stations_n = f"{n} station{'s' if n != 1 else ''}"; label = self.sub_label[key]
        old = not self.fresh(top, f0)                     # every price for this fuel here is over a week old
        title = f"{label} fuel prices today: {SHORT[f0] if f0 != 'DL' else 'diesel'} from {c1(top['p'][f0][0])}c | Bowser"
        if len(title) > 62 or old: title = f"{label} fuel prices today | Bowser"
        others = [f"{NAME[f]} {c1(t[0]['p'][f][0])}c" for f in FUELS if f != f0 and (t := self.cheapest(pool, f, 1))]
        desc = clip(f"Petrol prices in {name} {state_of(pc)} {pc} for {self.sday}: {NAME[f0]} {'last listed at' if old else 'from'} {c1(top['p'][f0][0])}c/L at {top['name']}"
                    + (f", {', '.join(others[:2])}" if others else "") + f". Compare {stations_n}" + ("." if out_syd else " and see whether to fill up or wait."))
        link = f'<a href="{up}{esc(top["url"])}">{esc(top["name"])}</a>'
        vm = self.vs_median(top, f0)
        if old:
            lead = (f"The lowest listed {NAME[f0]} price in {esc(name)} is <b>{c1(top['p'][f0][0])}c/L</b> at {link}, but it was last updated "
                    f"{top['p'][f0][1]} days ago, so check it before you drive there.")
        else:
            lead = f"The cheapest {NAME[f0]} in {esc(name)} today is <b>{c1(top['p'][f0][0])}c/L</b> at {link}" + (" (members only)" if top.get("m") else "") + (f", {vm}." if vm else ".")
        lead += f" {esc(name)} has {stations_n} reporting prices to NSW FuelCheck." if n > 1 else ""
        body = [f"<h1>{esc(label)} fuel prices today</h1>", f'<p class="lead">{lead}</p>', self.fuel_cards(pool, up, True)]
        if not out_syd: body.append(self.verdict_card(f0 if f0 in self.live else "U91"))
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
            body.append(f"<p>Bowser’s forecast is fitted on Sydney prices, so for {esc(name)} this page shows today’s prices only. "
                        "Without a forecast, the saving is in comparing stations rather than picking the day."
                        + (f' See <a href="{up}{esc(self.region_url[reg])}">all {esc(reg)} fuel prices</a>.' if reg else "") + "</p>")
        else:
            r = self.live[f0 if f0 in self.live else "U91"]; v = (r.get("verdict") or {}).get("head", "")
            body.append(f"<p>{esc(self.outlook(f0 if f0 in self.live else 'U91'))} Bowser’s call today is <b>{esc(v.lower())}</b>. "
                        f"Each station also gets its own call in the table above, based on how it usually prices against the rest of Sydney. "
                        f'See the <a href="{up}fuel-price-forecast/">Sydney fuel price forecast</a> for the 14-day outlook, '
                        f'or <a href="{up}" data-cta="suburb-map">open the live map</a> to compare stations around you.</p>')
        body += [f"<h3>Where do these {esc(name)} prices come from?</h3>",
                 f'<p>From <a href="{up}nsw-fuelcheck/">NSW FuelCheck</a>: every NSW service station must report its prices to the NSW Government when they change. '
                 "Bowser reads those prices several times a day and adds a forecast.</p>", self.sources_p()]
        ld = [{"@context": "https://schema.org", "@type": "ItemList", "name": f"Service stations in {name} {state_of(pc)} {pc}", "numberOfItems": n,
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

    def station(self, s):
        up = "../../"; f0 = s["main"]; p0 = s["p"][f0]; d = self.details.get(s["id"]) or {}
        where = s["sub"][0] if s["sub"] else s["s"]
        title = f"{s['label']} fuel prices today: {SHORT[f0] if f0 != 'DL' else 'diesel'} {c1(p0[0])}c | Bowser"
        if len(title) > 65: title = f"{s['label']} fuel prices today | Bowser"
        if len(title) > 70:   # too long with the street: the station number keeps it unique where a cut street name wouldn't
            short = s["label"] if s["label"] == s["name"] else f"{s['name']} (no. {s['id']})"
            title = f"{short} fuel prices | Bowser" if len(short) <= 48 else f"{s['name'][:36].rstrip()}… no. {s['id']} fuel prices | Bowser"
        listed = ", ".join(f"{SHORT[f] if f != 'DL' else 'diesel'} {c1(s['p'][f][0])}c" for f in FUELS if f in s["p"])
        call = "" if s.get("out") or not p0[3] else f" Bowser says: {p0[3].lower()}."
        desc = clip(f"{s['label']} fuel prices for {self.sday}: {listed}.{call}" + (" Today’s prices as reported to NSW FuelCheck." if s.get("out") else " With price history and a 7-day forecast."))
        addr = d.get("addr") if isinstance(d.get("addr"), str) else None
        sub_link = f'<a href="{up}{esc(self.sub_url[s["sub"]])}">{esc(self.sub_label[s["sub"]])}</a>' if s["sub"] else esc(where)
        brand_link = f'<a href="{up}{esc(self.brand_url[s["brand"]])}">{esc(s["brand"])}</a>' if s["brand"] in self.brand_url else esc(s["brand"])
        vm = self.vs_median(s, f0)
        lead = f"{esc(NAME[f0])} is <b>{c1(p0[0])}c/L</b> at {esc(s['name'])} today" + (f", {vm}." if vm else ".")
        if not self.fresh(s, f0): lead += f" This price was last updated {p0[1]} days ago, so check it before you drive there."
        body = [f"<h1>{esc(s['name'])}</h1>",
                f'<p class="small">{brand_link} · {esc(addr) if addr else sub_link}{" · Members only" if s.get("m") else ""}</p>',
                f'<p class="lead">{lead}</p>']
        cards = []
        for f in FUELS:
            if f not in s["p"]: continue
            p = s["p"][f]; g = self.vs_median(s, f)
            wk = f'<span class="small">In 7 days: about {c1(p[5])}c</span>' if len(p) > 5 and num(p[5]) and not s.get("out") else ""
            old = f'<span class="small">Updated {p[1]} days ago</span>' if not self.fresh(s, f) else ""
            cards.append(f'<div class="card"><span class="eyebrow">{esc(NAME[f])}</span><span class="big">{c1(p[0])}<small>c/L</small></span>'
                         f'{self.advice(s, f)}{f"<span class=small>{g}</span>" if g else ""}{wk}{old}</div>')
        body.append('<div class="grid">' + "".join(cards) + "</div>")
        dirs = f"https://www.google.com/maps/dir/?api=1&destination={s['la']:.5f},{s['lo']:.5f}"
        body.append(f'<div class="row"><a class="btn" href="{esc(dirs)}" rel="noopener" data-cta="directions">Directions</a>'
                    f'<a href="{up}" data-cta="station-map">Compare on the live map</a></div>')
        body.append(f"<h2>Should you fill up at {esc(s['name'])} today?</h2>")
        if s.get("out"):
            reg = s.get("region") if s.get("region") in self.regions else None; rm = self.median(self.regions[reg], f0) if reg else None
            txt = "This station is outside Sydney, where Bowser has no forecast, so this page shows its prices only."
            if rm is not None and self.fresh(s, f0):
                g = p0[0] - rm
                txt += (f" Its {esc(NAME[f0])} price is " + ("about the same as" if abs(g) < 0.5 else f"{cents(g)} {'under' if g < 0 else 'over'}")
                        + f" the {esc(reg)} median of {c1(rm)}c today. A {TANK} L fill costs about ${TANK * p0[0] / 100:.2f}.")
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
        body.append(self.station_chart(s, f0))
        near = [t for dist, t in self.near((s["la"], s["lo"]), 4.0) if t["id"] != s["id"]]
        pick = self.cheapest(near, f0, 6)
        if pick:
            n_cheaper = sum(t["p"][f0][0] < p0[0] for t in pick)
            body += [f"<h2>Cheaper {esc(NAME[f0])} near {esc(s['name'])}?</h2>",
                     f"<p>The cheapest {esc(NAME[f0])} within 4 km" + (f": {n_cheaper} of these {'is' if n_cheaper == 1 else 'are'} cheaper than here today." if n_cheaper else ". None of them beats this station today.") + "</p>",
                     self.price_table(pick, sort=f0, up=up)]
        more = []
        if s["sub"]: more.append(f'<li><a href="{up}{esc(self.sub_url[s["sub"]])}">All fuel prices in {esc(self.sub_label[s["sub"]])}</a></li>')
        if s["brand"] in self.brand_url: more.append(f'<li><a href="{up}{esc(self.brand_url[s["brand"]])}">{esc(s["brand"])} fuel prices</a></li>')
        if s.get("region") in self.regions: more.append(f'<li><a href="{up}{esc(self.region_url[s["region"]])}">{esc(s["region"])} fuel prices</a></li>')
        if f0 in self.live: more.append(f'<li><a href="{up}fuel-prices/{FSLUG[f0]}/">Cheapest {esc(NAME[f0])} in Sydney today</a></li>')
        body += ["<h2>More prices</h2>", "<ul>" + "".join(more) + "</ul>", self.sources_p()]
        m = re.match(r"^(.*?),\s*(.+?)\s+NSW\s+(\d{4})$", addr or "")
        ld = {"@context": "https://schema.org", "@type": "GasStation", "name": s["name"], "url": f"{self.site}/{s['url']}",
              "brand": {"@type": "Brand", "name": s["brand"]},
              "geo": {"@type": "GeoCoordinates", "latitude": s["la"], "longitude": s["lo"]},
              "address": {"@type": "PostalAddress", **({"streetAddress": m.group(1)} if m else {}), "addressLocality": where,
                          "addressRegion": state_of(s.get("pc")), **({"postalCode": str(s["pc"])} if s.get("pc") else {}), "addressCountry": "AU"}}
        crumbs = [("Fuel prices", "fuel-prices/")] + ([(self.sub_label[s["sub"]], self.sub_url[s["sub"]])] if s["sub"] else [("Stations", "station/")]) + [(s["name"], s["url"])]
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
                self.verdict_card(f)]
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
            ps = [s["p"][f][0] for s in pool if not s.get("out") and self.fresh(s, f) and not s.get("m")]
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
            body += [f"<h2>{esc(nm)} prices outside Sydney</h2>",
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
        place = "NSW" if nsw else "Sydney"
        title = f"{place} fuel prices today: cheapest petrol by suburb | Bowser"
        desc = clip(f"{'NSW and Sydney' if nsw else 'Sydney'} petrol prices for {self.sday}: Sydney {NAME[f0]} median {c1(r['now'])}c/L. Bowser’s call: {v.lower()}. "
                    f"Cheapest fuel in {len(self.subs):,} suburbs, from NSW FuelCheck data.", 165)
        body = [f"<h1>{place} fuel prices today</h1>",
                f'<p class="lead">On {esc(self.day)} the median price of {esc(NAME[f0])} in Sydney is <b>{c1(r["now"])}c/L</b>. '
                f"Bowser tracks {len(self.st):,} service stations in {len(self.subs):,} suburbs{' across NSW' if nsw else ''} using NSW FuelCheck prices, "
                "and for Sydney tells you whether to fill up now or wait.</p>",
                self.verdict_card(f0)]
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
            body += ["<h2>Fuel prices by region</h2>",
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
        qa.append(("Where do these fuel prices come from?",
                   "From NSW FuelCheck, the NSW Government service that every service station in the state must report its prices to. "
                   "Bowser reads those prices several times a day and adds a forecast. Bowser is independent and not part of the NSW Government."))
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
               "dateModified": self.asof, "spatialCoverage": "New South Wales, Australia" if nsw else "Sydney, New South Wales, Australia",
               "creator": {"@type": "Organization", "name": "Bowser", "url": self.site + "/"},
               "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{self.site}/api/v1/stations.json"}]}, fq_ld]
        self.page("fuel-prices/", "hub", "/fuel-prices/", title, desc, "\n".join(body), crumbs=[("Fuel prices", "fuel-prices/")], ld=ld, priority=1.0)

    def region(self, name):
        """A regional centre outside Sydney: its median, its cheapest stations and its suburbs. Prices only, no forecast."""
        up = "../../"; pool = self.regions[name]; path = self.region_url[name]
        f0 = next((f for f in FUELS if self.cheapest(pool, f, 1)), None)
        if not f0: return
        top = self.cheapest(pool, f0, 20); m = self.median(pool, f0); syd = self.live.get(f0)
        title = f"{name} fuel prices today: {SHORT[f0] if f0 != 'DL' else 'diesel'} from {c1(top[0]['p'][f0][0])}c | Bowser"
        if len(title) > 65: title = f"{name} fuel prices today | Bowser"
        desc = clip(f"Petrol prices in {name} for {self.sday}: {NAME[f0]} from {c1(top[0]['p'][f0][0])}c/L at {top[0]['name']}"
                    + (f", median {c1(m)}c" if m is not None else "") + f". Compare {len(pool)} stations, from NSW FuelCheck data.")
        lead = (f"The cheapest {esc(NAME[f0])} in {esc(name)} today is <b>{c1(top[0]['p'][f0][0])}c/L</b> at "
                f'<a href="{up}{esc(top[0]["url"])}">{esc(top[0]["name"])}</a>.')
        if m is not None:
            priced = sum(self.fresh(s, f0) and not s.get("m") for s in pool)
            lead += f" The median across {priced} stations with a current price is {c1(m)}c"
            if syd and num(syd.get("now")):
                g = m - syd["now"]
                lead += ", about the same as Sydney" if abs(g) < 0.5 else f", {cents(g)} {'under' if g < 0 else 'over'} Sydney’s {c1(syd['now'])}c"
            lead += "."
        body = [f"<h1>{esc(name)} fuel prices today</h1>", f'<p class="lead">{lead}</p>', self.fuel_cards(pool, up, False),
                f"<h2>The {len(top)} cheapest {esc(NAME[f0])} stations in {esc(name)}</h2>", self.price_table(top, sort=f0, up=up),
                '<p class="small">Members-only sites and prices not updated for over a week are left out of this list.</p>']
        if m is not None and len(top) > 1:
            body.append(f"<p>On a {TANK} L tank, filling at the cheapest station instead of a typical one saves about ${TANK * (m - top[0]['p'][f0][0]) / 100:.2f} today.</p>")
        subs = sorted({s["sub"] for s in pool if s["sub"]})
        if subs:
            body += [f"<h2>Fuel prices by suburb in {esc(name)}</h2>", '<ul class="cols">' + "".join(
                f'<li><a href="{up}{esc(self.sub_url[k])}">{esc(self.sub_label[k])}</a></li>' for k in subs) + "</ul>"]
        body += [f"<h2>Should you fill up in {esc(name)} today?</h2>",
                 f"<p>Bowser’s fill-or-wait forecast is fitted on Sydney prices and doesn’t cover {esc(name)}, so this page shows today’s prices without a call. "
                 "Without a forecast, the saving is in comparing stations rather than picking the day. "
                 f'For Sydney, see the <a href="{up}fuel-price-forecast/">fuel price forecast</a>.</p>', self.sources_p()]
        self.page(path, "region", "/fuel-prices/:region/", title, desc, "\n".join(x for x in body if x),
                  crumbs=[("Fuel prices", "fuel-prices/"), (name, path)], priority=0.8)

    def station_index(self):
        up = "../"
        groups = {}
        for s in self.st: groups.setdefault(s["sub"][0] if s["sub"] else "Other", []).append(s)
        place = "NSW" if self.any_out else "Sydney"
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
            ps = [s["p"][f0][0] for s in pool if self.fresh(s, f0)]
            avg = sum(ps) / len(ps); x = self.live.get(f0)
            sp_ = [s["p"][f0][0] for s in pool if self.fresh(s, f0) and not s.get("out")]   # the Sydney ones: only they compare with the Sydney median
            title = f"{b} fuel prices today: {SHORT[f0] if f0 != 'DL' else 'diesel'} from {c1(top['p'][f0][0])}c | Bowser"
            if len(title) > 65: title = f"{b} fuel prices today | Bowser"
            desc = clip(f"{b} petrol prices for {self.sday} at {len(pool)} stations: {NAME[f0]} from {c1(top['p'][f0][0])}c/L at {top['name']}, "
                        f"average {avg:.1f}c. Every station’s price" + (", and whether to fill up or wait." if x and len(sp_) >= 3 else ", from NSW FuelCheck data."))
            lead = (f"The cheapest {esc(NAME[f0])} at {esc(at_b)} today is <b>{c1(top['p'][f0][0])}c/L</b> at "
                    f'<a href="{up}{esc(top["url"])}">{esc(top["name"])}</a>. Across the {len(ps)} {"independent" if indep else esc(b)} stations with a current price the average is {avg:.1f}c')
            if x and len(sp_) >= 3:
                g = sum(sp_) / len(sp_) - x["now"]
                lead += (f". The {len(sp_)} in Sydney average {sum(sp_) / len(sp_):.1f}c, "
                         f"{'about the same as' if abs(g) < 0.5 else cents(g) + (' under' if g < 0 else ' over')} the Sydney median of {c1(x['now'])}c")
            body = [f"<h1>{esc(b)} fuel prices today</h1>", f'<p class="lead">{lead}.</p>', self.fuel_cards(pool, up, False)]
            if all(s.get("m") for s in pool): body.append(f"<p>{esc(b)} fuel is for members only: you need a membership card to fill up.</p>")
            if x and len(sp_) >= 3: body.append(self.verdict_card(f0))
            body += [f"<h2>All {esc(b)} stations, cheapest first</h2>", self.price_table(pool, sort=f0, up=up),
                     f'<p>Compare with <a href="../">other brands</a> or see the <a href="{up}fuel-prices/{FSLUG[f0]}/">cheapest {esc(NAME[f0])} in Sydney</a>.</p>',
                     "" if indep else f'<p class="small">{esc(b)} is a trade mark of its owner. Bowser is independent and not affiliated with {esc(b)}.</p>', self.sources_p()]
            self.page(path, "brand", "/brands/:brand/", title, desc, "\n".join(x for x in body if x), crumbs=[("Brands", "brands/"), (b, path)], priority=0.7)

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
        d7 = r["d7"]
        ans = ("stay about where they are" if abs(d7) < 1 else f"{'rise' if d7 > 0 else 'fall'} by about {cents(d7)} a litre")
        body = ["<h1>Sydney fuel price forecast: will petrol go up or down this week?</h1>",
                f'<p class="lead">As of {esc(self.day)}, Bowser expects the Sydney median {esc(NAME[r["fuel"]])} price to <b>{ans}</b> over the next seven days. Today’s call: <b>{esc(v.lower())}</b>.</p>',
                self.verdict_card(r["fuel"]),
                "<h2>The 14-day outlook for each fuel</h2>",
                '<div class="scroll"><table><thead><tr><th>Fuel</th><th class="n">Today</th><th class="n">In 3 days</th><th class="n">In 7 days</th><th class="n">In 14 days</th><th class="n">7-day range</th><th>Call</th></tr></thead><tbody>'
                + rows + "</tbody></table></div>",
                '<p class="small">Sydney median prices in cents a litre. The range is where Bowser expects the price to land about 8 times in 10.</p>']
        if num(r.get("p_jump7")):
            pj = r["p_jump7"]
            body.append(f"<p>The chance of a sharp jump (5c or more) in the Sydney {esc(NAME[r['fuel']])} median within a week is "
                        f"<b>{'under 5%' if pj < 0.05 else f'about {pj:.0%}'}</b>. "
                        + ("Sydney prices rise in sudden jumps and fall slowly, so this number matters more than the average move: when it is high, fill up before the jump."
                           if pj >= 0.35 else "Sydney prices rise in sudden jumps and fall slowly; while this number stays low, waiting usually pays."))
        tr = (self.track.get("replay") or {}).get("U91") or {}; lv = (self.track.get("live") or {}).get("U91") or {}
        body.append("<h2>How accurate is the forecast?</h2>")
        if tr.get("n"):
            body.append(f"<p>Replayed over every day from {esc(short_date(tr['from']))} {tr['from'][:4]} to {esc(short_date(tr['to']))} {tr['to'][:4]}, using only the data available "
                        f"on each day, Bowser’s fill-or-wait call for Unleaded 91 was right <b>{tr['right'] / tr['n']:.0%}</b> of the time ({tr['right']:,} of {tr['n']:,} calls), "
                        f"close on {tr['close'] / tr['n']:.0%} and wrong on {tr['wrong'] / tr['n']:.0%}."
                        + (f" Since the calls went live on {esc(short_date(lv['since']))}, {lv['right']} of {lv['n']} scored calls were right and {lv['wrong']} wrong." if lv.get("n") else "") + "</p>")
        body += ["<p>The forecast is tested the hard way: each month since January 2021 was forecast using only the data before it, including the 2022 and 2026 oil shocks. "
                 f'The full record, call by call, is on the <a href="{up}" data-cta="forecast-track">dashboard</a>.</p>',
                 "<h2>How the forecast works</h2>",
                 "<ul><li><b>What it predicts:</b> how the Sydney median price of each fuel will move over the next 1, 3, 7 and 14 days, and the chance of a jump of 5c or more within a week.</li>"
                 "<li><b>What it looks at:</b> how far pump prices sit above the wholesale price compared with the past year, recent wholesale moves, the oil price in Australian dollars, "
                 "how spread out station prices are, and where Sydney is in its price cycle.</li>"
                 "<li><b>How it learns:</b> a machine-learning model trained on Sydney prices for all five fuels since 2019, with a separate model for price jumps.</li>"
                 "<li><b>Each station gets its own call:</b> some stations lead a price jump and some follow days later, and a few hardly move at all. Bowser adjusts the Sydney forecast for how each station usually behaves.</li>"
                 "<li><b>Limits:</b> it reacts to oil and wholesale moves as they happen, but it can’t see wars, OPEC decisions or excise changes coming.</li></ul>",
                 "<h2>When is the best time to buy petrol in Sydney?</h2>",
                 f'<p>Just before a jump, at the bottom of the <a href="{up}petrol-price-cycle/">price cycle</a>. The day of the week barely matters in Sydney'
                 + (f": across the calm years the average gap between the cheapest and dearest weekday is about {max(S['dow']) - min(S['dow']):.1f}c" if isinstance(S.get("dow"), list) and all(num(x) for x in S["dow"]) else "")
                 + ". Where you fill matters more than when"
                 + (f": the cheapest tenth of Sydney stations are typically {S['shop_around']:.0f}c under the median" if num(S.get("shop_around")) else "")
                 + f'. Check <a href="{up}fuel-prices/">today’s cheapest stations by suburb</a>.</p>', self.sources_p()]
        t = "Sydney fuel price forecast: will petrol go up this week? | Bowser"
        d = (f"Petrol price forecast for Sydney, updated {self.sday}: {NAME[r['fuel']]} is {c1(r['now'])}c/L and expected to {ans} in 7 days. "
             f"Bowser’s call: {v.lower()}. 14-day outlook for every fuel.")
        self.page("fuel-price-forecast/", "forecast", "/fuel-price-forecast/", t, d, "\n".join(body), crumbs=[("Forecast", "fuel-price-forecast/")],
                  ld=art("fuel-price-forecast/", "Sydney fuel price forecast: will petrol go up or down this week?", d), priority=1.0)

        # ---- price cycle
        body = ["<h1>The Sydney petrol price cycle, and where it is now</h1>"]
        last = S.get("last_restore"); gap, amp = S.get("cycle_gap_calm"), S.get("cycle_amp_calm")
        if last and num(gap):
            since = (dt.date.fromisoformat(self.fc_asof) - dt.date.fromisoformat(last)).days
            body.append(f'<p class="lead">Sydney’s last big price jump began on <b>{esc(short_date(last))}</b>, {since} days ago. In normal years a jump comes about every <b>{gap:.0f} days</b>'
                        + (f" and lifts Unleaded 91 by about <b>{amp:.0f}c</b> a litre" if num(amp) else "") + ".</p>")
        if "U91" in live: body.append(self.verdict_card("U91"))
        body += ["<h2>What is the petrol price cycle?</h2>",
                 "<p>In Sydney, petrol prices don’t drift up and down with the oil price from day to day. They move in a saw-tooth: prices jump sharply over a day or two, "
                 "often by 30c a litre or more, then slide down a little each day for several weeks until the next jump. The ACCC, which monitors fuel prices, has found the same pattern in "
                 "Australia’s largest cities, and that the cycles come from retailers’ pricing decisions rather than from changes in wholesale costs.</p>",
                 "<p>For drivers the rule is simple: <b>fill up near the bottom, just before the jump, and buy as little as you can near the top</b>. The hard part is knowing when the jump is coming, "
                 f'because the cycle doesn’t keep to a timetable. That is what <a href="{up}fuel-price-forecast/">Bowser’s forecast</a> is for.</p>']
        cy = [c for c in (S.get("cycles_by_year") or []) if num(c.get("gap")) and num(c.get("amp"))]
        if cy:
            body += ["<h2>How long is the Sydney price cycle?</h2>",
                     "<p>It changes from year to year. This table counts the big jumps in the Sydney Unleaded 91 median each year, the typical gap between them and the typical size of the jump.</p>",
                     '<div class="scroll"><table><thead><tr><th>Year</th><th class="n">Price jumps</th><th class="n">Typical days between</th><th class="n">Typical jump (c/L)</th></tr></thead><tbody>'
                     + "".join(f'<tr><td>{c["year"]}{" (so far)" if str(c["year"]) == self.asof[:4] else ""}</td><td class="n">{c["n"]}</td><td class="n">{c["gap"]:.0f}</td><td class="n">{c["amp"]:.0f}</td></tr>' for c in cy)
                     + "</tbody></table></div>"]
        dow = S.get("dow")
        if isinstance(dow, list) and len(dow) == 7 and all(num(x) for x in dow):
            names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            lo_d, hi_d = names[dow.index(min(dow))], names[dow.index(max(dow))]
            body += ["<h2>Is there a cheapest day of the week?</h2>",
                     f"<p>Not in Sydney, not any more. Averaged over the calm years since 2019, {lo_d} is the cheapest day and {hi_d} the dearest, but the gap is only about "
                     f"<b>{max(dow) - min(dow):.1f}c a litre</b>: about {TANK * (max(dow) - min(dow)) / 100 * 100:.0f} cents on a {TANK} L tank. With a cycle several weeks long, where prices are in the cycle "
                     "matters far more than the day of the week.</p>"]
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
                 f'which can still carry it a long way over a few weeks when oil moves. See the <a href="{up}fuel-prices/diesel/">Sydney diesel price</a> and today’s call for it.</p>', self.sources_p()]
        t = "Sydney petrol price cycle: where are we now? | Bowser"
        d = (f"Where Sydney is in its petrol price cycle on {self.sday}"
             + (f": the last jump began {short_date(last)}, and jumps come about every {gap:.0f} days" if last and num(gap) else "")
             + ". How the cycle works, how long it lasts, and when to fill up.")
        self.page("petrol-price-cycle/", "cycle", "/petrol-price-cycle/", t, d, "\n".join(body), crumbs=[("Price cycle", "petrol-price-cycle/")],
                  ld=art("petrol-price-cycle/", "The Sydney petrol price cycle, and where it is now", d), priority=0.9)

        # ---- NSW FuelCheck
        body = ["<h1>Bowser and NSW FuelCheck: what each one does</h1>",
                '<p class="lead">FuelCheck is the NSW Government’s fuel price service. Every service station in NSW must report its prices to it, so it is the source of truth for what fuel costs right now. '
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
                "Where a station hasn’t updated its price for more than a week, Bowser says so. For the price this minute, check FuelCheck or the board at the station.</p>",
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
                '<p class="lead">Bowser tells Sydney drivers when to fill up and where it’s cheapest. It is an independent project, free to use.</p>',
                "<p>A bowser is what Australians call a petrol pump. The site and app take the prices every NSW service station reports to the NSW Government’s FuelCheck service, "
                "add a forecast of where Sydney prices are heading, and turn it into one plain call: fill up now, or wait.</p>",
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
                 f"> Bowser (checkbowser.app) is an independent, free site and app for fuel prices in New South Wales, Australia. It shows today's price at {len(self.st):,} "
                 "service stations, taken from the NSW Government's FuelCheck service, and adds a forecast for Sydney that says whether to fill up now or wait. "
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
                  f"- [Prices by brand]({u}/brands/): 7-Eleven, Ampol, BP, Shell, Costco and others compared."]
        lines += [f"- [{NAME[f]} prices in Sydney]({u}/fuel-prices/{FSLUG[f]}/)" for f in FUELS if f in self.live]
        if self.regions:
            lines += ["", "## Regions outside Sydney (prices only, no forecast)", ""] + [f"- [{md(n)} fuel prices]({u}/{self.region_url[n]})" for n in sorted(self.regions)]
        lines += ["", "## Page patterns", "",
                  f"- One page per suburb: {u}/fuel-prices/{{suburb}}-{{postcode}}/ (for example {u}/fuel-prices/parramatta-2150/).",
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


def home_head(stations, forecast, site=SITE):
    """The dashboard's <title> and the tags after it: description, canonical, Open Graph, icons and JSON-LD."""
    site = site.rstrip("/"); live = {r["fuel"]: r for r in forecast["live"]}
    r = live.get("U91") or next(iter(live.values())); v = (r.get("verdict") or {}).get("head", "")
    n = sum(usable(s) is not None for s in stations["stations"]); day = short_date(stations["asof"])
    title = "Bowser: Sydney fuel prices today and when to fill up"
    desc = (f"{NAME[r['fuel']]} is {c1(r['now'])}c/L in Sydney today ({day}). Bowser’s call: {v.lower()}. Live NSW FuelCheck prices for {n} stations, "
            "a map of the cheapest near you and a 14-day fuel price forecast.")
    org = {"@type": "Organization", "@id": site + "/#org", "name": "Bowser", "url": site + "/", "logo": site + "/apple-touch-icon.png"}
    ld = {"@context": "https://schema.org", "@graph": [
        org, {"@type": "WebSite", "@id": site + "/#site", "name": "Bowser", "alternateName": ["Check Bowser", "checkbowser.app"], "url": site + "/",
              "inLanguage": "en-AU", "publisher": {"@id": site + "/#org"}, "description": "Sydney fuel prices today, the cheapest stations near you and a forecast of when to fill up."},
        {"@type": "WebApplication", "name": "Bowser", "url": site + "/", "applicationCategory": "UtilitiesApplication", "operatingSystem": "Any",
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "AUD"}, "publisher": {"@id": site + "/#org"}}]}
    return "\n".join([
        f"<title>{esc(title)}</title>", f'<meta name="description" content="{esc(desc)}">', f'<link rel="canonical" href="{site}/">',
        '<meta property="og:type" content="website">', '<meta property="og:site_name" content="Bowser">', '<meta property="og:locale" content="en_AU">',
        f'<meta property="og:title" content="{esc(title)}">', f'<meta property="og:description" content="{esc(desc)}">',
        f'<meta property="og:url" content="{site}/">', f'<meta property="og:image" content="{site}/og.png">',
        '<meta name="twitter:card" content="summary_large_image">', '<meta name="theme-color" content="#ffb22e">',
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
                                 + [a("fuel-price-forecast/", "Fuel price forecast"), a("petrol-price-cycle/", "Sydney petrol price cycle"), a("brands/", "Prices by brand"),
                                    a("nsw-fuelcheck/", "About NSW FuelCheck"), a("about/", "About Bowser"), a("privacy/", "Privacy")]) + "</div>"
            + ("<div>Popular suburbs: " + " · ".join(a(S.sub_url[k], S.sub_label[k]) for k in top) + "</div>" if top else ""))


def clear(out):
    """Remove everything this module writes, so a failed run leaves no half-built pages to publish."""
    for d in OWN: shutil.rmtree(os.path.join(out, d), ignore_errors=True)
    for f in ["404.html", "robots.txt", "sitemap.xml", "llms.txt"]:
        if os.path.exists(os.path.join(out, f)): os.remove(os.path.join(out, f))


def build(out, stations, forecast, history=None, details=None, track=None, site=SITE, static=None):
    """Write every search page under `out`. Returns {"pages": n, "stations": n, "suburbs": n}. Raises on bad input:
    the caller (export_api.py) then clears the pages and publishes the rest of the site without them."""
    clear(out)
    S = Site(out, stations, forecast, history, details, track, site)
    if len(S.st) < 1 or "U91" not in S.live: raise ValueError(f"search pages: {len(S.st)} stations, fuels {sorted(S.live)}")
    S.hub()
    for f in FUELS:
        if f in S.live: S.fuel(f)
    for n in sorted(S.regions): S.region(n)
    for k in sorted(S.subs): S.suburb(k)
    S.station_index()
    for s in S.st: S.station(s)
    S.brand_pages(); S.guides(); S.finish()
    if static:
        for f in STATIC:
            if os.path.exists(os.path.join(static, f)): shutil.copyfile(os.path.join(static, f), os.path.join(out, f))
    seen = [u[0] for u in S.urls]
    if len(set(seen)) != len(seen): raise ValueError("search pages: two pages share an address")
    return {"pages": len(seen), "stations": len(S.st), "suburbs": len(S.subs), "brands": len(S.brand_url), "regions": len(S.regions)}
