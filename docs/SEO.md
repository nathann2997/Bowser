# Search plan: checkbowser.app

How Bowser gets found on Google, what was built for it (2026-11-17), and what the owner still has to do. The code is `sydney/pipeline/seo_pages.py`; it runs inside `export_api.py` on every pipeline run.

## The goal
Rank for the fuel searches Sydney and NSW drivers make, bring that traffic to checkbowser.app, and later earn from it with AdSense. Traffic first: AdSense needs a site with real content and visitors before it approves, and pays in proportion to page views.

## Where Bowser can win
The big names (FuelCheck itself, PetrolSpy, MotorMouth, NRMA, the 7-Eleven app) all answer "where is it cheap right now". Nobody answers "should I fill up today or wait" with a tested forecast. So the plan has two halves:
1. **Match them on coverage:** a page for every suburb, station, fuel and brand, so Bowser is a candidate for every local price search.
2. **Beat them on the forecast:** every page carries the fill-or-wait call, and two guides own the forecast and price-cycle searches outright.

## Keyword map
One page per search intent, so pages don't compete with each other. Volumes are judgement, not measured: confirm them in Search Console once data arrives, and in Google Keyword Planner before spending effort on a new group.

| Searches | Page | Why Bowser can rank |
|---|---|---|
| bowser, check bowser, bowser fuel app; should I fill up today, fill up now or wait | `/` (dashboard) | Brand, and the question the dashboard answers. Title since 2026-11-20: "Should you fill up today? Sydney fuel prices \| Bowser" (PetrolPulse builds its title on the same phrase). |
| nsw fuel prices, sydney petrol prices, fuel price sydney, nsw fuel price check, cheapest petrol sydney, petrol prices near me | `/fuel-prices/` | Today's median, the 15 cheapest, every suburb linked. Title since 2026-11-26: "Sydney, NSW & ACT fuel price check: cheapest petrol today", because "fuel price sydney" (the top query) was going to `/brands/`. |
| petrol prices {suburb}, cheapest fuel {suburb}, {suburb} fuel prices | `/fuel-prices/{suburb}-{postcode}/` (384 today) | Long tail. Low competition per suburb, large in total. The main traffic source. |
| {station name} fuel price, 7-eleven parramatta petrol price | `/station/{name}-{id}/` (864 today) | Very long tail; price history and a per-station forecast nobody else has. |
| newcastle fuel prices, central coast petrol prices, wollongong fuel prices, canberra petrol prices | `/fuel-prices/{region}/` (23) | Median, 20 cheapest, the gap to Sydney, every suburb in the region. |
| e10 price sydney, diesel price sydney, 98 petrol price, unleaded 91 price today | `/fuel-prices/{fuel}/` (5) | Median, 25 cheapest, 90-day chart, brand table. |
| costco fuel price, 7-eleven fuel price, ampol/bp/shell petrol price, cheapest petrol brand | `/brands/`, `/brands/{brand}/` (22) | "costco fuel price" and "7 eleven fuel price" are among the largest fuel searches in Australia. |
| fuel price forecast, petrol price forecast/prediction (sydney), petrol prices next week, will petrol go up/down this week or tomorrow | `/fuel-price-forecast/` | The product. Updated five times a day: a 60-day + 14-day chart, the call, tank savings, and question-style answers (FAQPage) with today's numbers. Every "next week / tomorrow / prediction" search belongs here, not on new pages. |
| petrol prices this week sydney (dated), did petrol go up last week | `/fuel-price-forecast/<Monday>/`, `/fuel-price-forecast/weekly/` | Roadmap item 7 (2026-11-23): each Monday's saved outlook, scored a week later. Noindex until its 7 days are known, so the current week never competes with `/fuel-price-forecast/`. |
| how accurate is the fuel forecast, fuel price prediction accuracy | `/fuel-price-forecast/accuracy/` | No competitor publishes a track record (2026-11-20 review). Trust page for Google and for people deciding whether to believe the call. |
| sydney petrol price cycle, petrol cycle sydney, where are we in the petrol cycle, is the petrol cycle back | `/petrol-price-cycle/` | Own data: a cycle-stage card, the latest jumps, cycle length by year. The ACCC's Sydney table is stale (stops in January 2026). |
| best day to buy petrol (sydney), cheapest day to buy petrol, is tuesday the cheapest day for petrol, is petrol cheaper on weekends | `/best-day-to-buy-petrol/` | Split out of the cycle page on 2026-11-20 (FuelRadar ranks a dedicated page). The answer, "no day in Sydney", backed by Bowser's weekday figures. |
| petrol prices christmas (sydney), will petrol go up before christmas, petrol prices holidays | `/petrol-prices-christmas/` | Every Christmas since 2019 from Bowser's own history, plus this year's outlook. One evergreen address, so it builds links year on year. |
| nsw fuel check, fuelcheck nsw, fuel check app, fuelcheck prices | `/nsw-fuelcheck/` | See the next section. |
| 7 eleven fuel lock, fuel price lock, how does 7 eleven fuel lock work | `/7-eleven-fuel-price-lock/` | The only page that says whether to lock today, from a tested forecast. |
| woolworths fuel discount, everyday rewards fuel, woolworths fuel discount locations | `/woolworths-fuel-discount/` | Today's prices at the brands that take it, before and after. |
| coles fuel docket, flybuys fuel discount | `/coles-fuel-docket/` | The same, with the 14c Reddy Express stack. |
| costco fuel price (sydney), is costco fuel cheaper, do you need membership | `/brands/costco/` | Every Sydney Costco's price and the membership break-even, from today's gap. |
| fuel discounts nsw/sydney, cheapest petrol deals sydney, fuel discounts for seniors | `/petrol-deals-sydney/` | Every discount beside today's price at the stations that take it: nobody else shows whether the docket station was dearer to begin with. Offers in `DEALS`, each with the date it was checked against its terms (`checked`) and an optional end date (`until`); re-check every few months. |

### "NSW FuelCheck" searches
Most people typing "fuel check nsw" want the government site, and Google will keep it first. Bowser can't and shouldn't pretend to be it. What it can do honestly:
- one guide that explains FuelCheck and what Bowser adds, for people comparing options;
- "NSW FuelCheck" in the description and body of every price page, because that is where the prices come from (and the licence requires the credit anyway);
- every page says Bowser is independent and not affiliated with the NSW Government.

Never lead a page title with "FuelCheck" or call the site "FuelCheck": it risks a complaint from NSW Fair Trading and a manual action from Google.

## What was built
- **1,283 pages** of plain HTML, rebuilt on every run: readable without running any script (the only script is the small visit counter), about 20 KB each, one inline style block.
- **On every page:** a unique title and description with today's price in them, a canonical address on checkbowser.app, Open Graph and Twitter tags with a share image, breadcrumbs (visible and as structured data), FuelCheck attribution, and links to its neighbours (suburb to its stations and nearby suburbs, station to its suburb, brand and nearby stations).
- **Structured data:** `WebSite`, `Organization` and `WebApplication` on the dashboard; `GasStation` with address and coordinates on station pages; `ItemList` on suburb pages; `Article` on guides; `Dataset` on the hub; `BreadcrumbList` everywhere.
- **`sitemap.xml`** and **`robots.txt`**. Since 2026-11-26, `sitemap.xml` is an index of `sitemap-pages.xml` (the dashboard, hubs, regions, fuels, brands, guides), `sitemap-suburbs.xml` and `sitemap-stations.xml`, so Search Console's Sitemaps report shows indexing for each group. It stays at the address already submitted: nothing to resubmit. `indexnow.py` follows the index. (allows everything except the app's per-station JSON files).
- **Dashboard:** a real title and description, canonical, share tags, `lang="en-AU"`, a favicon, and footer links into the new pages. The app's share page (`/s/`) is marked `noindex`.
- **`/about/` and `/privacy/`:** needed for trust, and AdSense requires a privacy policy.
- **Safety:** stale prices (over 7 days) and members-only sites never count as "cheapest"; wholesale (AIP) figures are left out of these pages, since their licence is unresolved (`DATA-LICENSE.md`); station names from the feed are escaped.
- **Counting:** each page sends one anonymous pageview with its page *type* (suburb, station, …), never which suburb or station, so the privacy promise still holds. Per-page traffic comes from Search Console instead.
- **All NSW** (since 2026-11-17): stations outside Sydney get prices without forecast wording, and those within reach of a regional centre join its region page (`/fuel-prices/newcastle/` and so on; 23 centres, about half the stations outside Sydney). The rest are reached through their suburb pages. A station silent for over 30 days stays reachable but is kept out of search.

## Owner to do, in order
1. **Done 2026-11-17:** PR #11 is merged and the pages are live (3,546 with all NSW stations).
2. **Done 2026-11-17/18:** Google Search Console (Domain property, sitemap submitted at its full address) and Bing Webmaster Tools.
3. **Done 2026-11-17:** the owner confirmed "Discard client IP data" is on in PostHog, as the Privacy page says.
4. **Links.** A new domain has no authority, and links are what Google trusts most. Cheap, honest ones:
   - list the site in the NSW FuelCheck API showcase / data.nsw.gov.au "apps using this data" if offered;
   - post the forecast and its track record on r/sydney and r/AusFinance when a price jump is forecast (useful, timely, not spam), and to Whirlpool's motoring forum;
   - pitch local news: "site predicts Sydney's next petrol price jump" is a story every time prices spike; the public track record is the proof;
   - when the app reaches the Play Store, the listing links to the site.
5. **Decide on a contact address.** The About page points to GitHub issues for now; AdSense reviewers prefer an email (for example hello@checkbowser.app through Porkbun's forwarding).

## What to watch
In Search Console, weekly for the first two months:
- **Pages indexed** against the 1,284 in the sitemap. Expect weeks, not days, for a new domain; station pages will be last.
- **Queries and clicks by page group** (filter by `/fuel-prices/`, `/station/`, `/brands/`): shows which group earns its keep.
- **First report (2026-11-20, three days in):** 21 excluded by noindex (intended: stations silent 30+ days and `/s/`; don't validate them) and 1,512 crawled but not indexed, which is normal at this age. The sitemap's `lastmod` now follows price dates for pages outside Sydney. Making single-station suburb pages noindex is on hold until the example URLs, or a "Duplicate" row, show suburb pages losing out to their station page.
- **"Crawled, currently not indexed"** on station pages. If most stay unindexed after two months, Google finds them too thin: add content to them or drop them from the sitemap and keep the suburb pages.
- **Core Web Vitals:** the new pages should pass easily (one tiny script, no web fonts). The dashboard is heavier; watch it separately.

## AdSense readiness
Not yet. What is missing, in the order to fix it:
1. **Traffic and age.** Apply once the domain has been indexed for a few weeks and has steady daily visits.
2. **`ads.txt`** at the site root, with the publisher line Google gives on approval. Add it to `sydney/pipeline/static/` and to `STATIC` in `seo_pages.py`.
3. **Privacy.** The site now says "no cookies, no advertising trackers". Ads change that: `/privacy/` and both footers must be rewritten first, and Google requires a certified consent banner for visitors from Europe and the UK.
4. **The security policy.** Every page has a strict Content-Security-Policy that blocks third-party scripts, which blocks ads too. It has to be loosened on the pages that carry ads. Suggested: ads on the search pages only, and keep the dashboard clean and fast, since it is the product.
5. **Layout.** Leave fixed-height slots for ads so the page doesn't jump when they load (a ranking factor).
6. **Data terms.** FuelCheck's CC BY-SA licence allows commercial use with attribution, which is in place. Read the NSW API portal's own terms once before turning ads on, and keep AIP figures off ad pages until that licence question is settled.

## AI assistants (ChatGPT, Claude, Perplexity, Google AI Overviews)
What decides whether an assistant can find and quote Bowser, and where it stands (reviewed 2026-11-17):
- **Can they read it?** Most AI crawlers don't run script. Every search page is plain HTML, and the dashboard's footer now states today's prices and call as text. Done.
- **Are they allowed?** `robots.txt` allows everything. It also names the main AI crawlers and tokens; that changes nothing today (they were already allowed) but makes the intent explicit and gives one place to change it. Done.
- **Is the index fresh?** IndexNow (since 2026-11-21, `indexnow.py`): after each deploy, the pages whose sitemap date moved are submitted to api.indexnow.org, which Bing (ChatGPT search, Copilot) and others share. The key file is `/e102a05131cbd86e3a6af62c8547639e.txt`.
- **Can they find it?** Assistants lean on search indexes: Google's for Gemini and AI Overviews, Bing's for ChatGPT search and Copilot; others (Perplexity, Claude) use their own or other indexes and crawl directly. Google is set up; Bing is the owner step above.
- **Is the answer easy to lift?** Each page opens with one sentence that answers its question with a number and a place, and carries its date; the hub has short question-and-answer blocks; structured data says what each page is. Done.
- **`/llms.txt`:** a plain summary of the site, today's numbers, the main pages and the data files. It is a proposed convention that few crawlers read yet; it costs nothing and is there for those that do.
- **Can they trust it?** Sources are credited on every page, the forecast's track record is public, and About says who runs it. The weak point is the same as for Google: no other site links here yet.

## Competitors for forecast searches (reviewed 2026-11-20)
Desk research with a US-based search tool. These are the pages that kept coming up, not measured Google AU positions, and no People Also Ask box was seen. Check against Search Console queries in December 2026, once real data is in.

| Who | What they do for "will it go up / when to buy" | What Bowser does about it |
|---|---|---|
| **ACCC** (`accc.gov.au/…/petrol-price-cycles-in-the-5-largest-cities`) | A text buying tip per city (updated Mon/Wed/Fri), a 45-day chart, and a table of the last 5 cycles. Its Sydney table stops at a 27 Jan 2026 peak and it says cycles "have mostly not occurred" since late February. No structured data. | The cycle page shows a current stage, the latest jumps and an honest answer to "is the cycle still running?" (jumps are back but smaller: 8 in the last 12 months, typically 26c against 37c in normal years). |
| **Finder** (`finder.com.au/fuel`) | The closest product: a "Should you fill up today?" widget for 5 cities (cycle stage, predicted low, saving with a tank slider), station map, history charts. Article + Dataset + Person-author schema. Updated about monthly. | Forecast page now has the tank-savings table, a forecast chart, a Dataset block and question answers; daily freshness beats theirs. Their author pages and editorial policy are the E-E-A-T gap (see below). |
| **NRMA** (`mynrma.com.au` weekly fuel report, press releases) | A written Monday outlook ("expected to fall to the high 210s this week") and a press release for each long weekend. | Not copied yet: dated weekly outlook pages need saved snapshots (below). The Christmas page covers the biggest holiday. |
| **FuelRadar** (`fuelradar.com.au`) | Programmatic FuelCheck pages per city, suburb and fuel, plus "best day to buy fuel in {city}" pages. Prices up to months old on some suburb pages. | Bowser already has suburb, station and fuel pages with fresher data and a call; added a dedicated best-day page. |
| **PetrolSpy** | Map, cycle graphs, price-spike notifications in its app, paid API. | The app already has local price-rise alerts; web email alerts are not built. |
| **RACQ / RACV / RAC WA, FuelWatch** | Cycle explainers for their own state; FuelWatch publishes tomorrow's actual prices in WA. | Out of scope (no data outside NSW). The best-day page points to the ACCC and FuelWatch for other cities. |
| **Petrol Price Predictor** (connectingthedots.com.au) | Claims 30-day predictions per station in 4 states; shows no accuracy figures. | The accuracy page is the answer: a tested, public record. |
| **PetrolPulse** (`petrolpulse.com.au`), the closest rival | Homepage title "Fuel Price Forecast Australia — Should You Fill Up Today?". A fill-or-wait call for 8 capitals and 12 regional cities (`/petrol-prices/{city}`), oil + AUD + cycle signals, `/forecast-accuracy` (86% right on 8,471 replayed calls since April 2026, scored with lenient rules: a fill is right unless prices fall 3c+, a wait is right if any cheaper day follows, and days without a strong call are left out), a methodology page, founder byline and ABN, "Market Pulse" news, alerts, route planner, trip calculator, fuel shortage map, iOS and Android apps. No suburb or station pages; the Sydney page contradicts itself (600 vs 847 stations, 18–28 vs 35-day cycle). | Win on depth: crawlable suburb and station pages, a test back to 2021 with error in c/L, stricter scoring, a live log of every call. Lose on breadth (they cover every capital), authorship, and news cadence. |
| **Fuel Daddy** (`fueldaddy.com.au`) | 8,100+ stations in every state; suburb pages (`/locations-{state}/{suburb}/`), brands, a Costco page, an outage tracker, calculators, embeddable widgets, iOS app with price-drop alerts, "no ads". `/fuel-price-forecast/` places each of 32 cities within its last 14 days' range: a rule of thumb, with no test. On 20 Nov it said "Fill now" for Sydney while prices were falling. | Their forecast is a rule of thumb; ours is tested. They match us on suburb pages nationally. The widgets and outage tracker are the features to note. |
| **ConnectingTheDots** (`connectingthedots.com.au/services/data-analytics/petrol/`) | A marketing page for a 30-day per-station predictor (NSW, QLD, SA, WA metro); the app runs on a dynamic-DNS address. No accuracy, method or FAQ. Funded by donations. | Not a search threat. |
| **News** (CarExpert, Yahoo, 9News, SMH) | "Prices tipped to rise" articles quoting NRMA or the ACCC. | A pitch angle: the forecast with its public record (Owner to do, item 4). |

### Keyword research, 2026-11-22: "should I fill up" and fuel discounts
**Method.** Google Autocomplete for Australia (`suggestqueries.google.com`, `hl=en-AU&gl=au`): 52 seeds for the fill-up cluster and 30 for discounts, with A–Z expansions. Autocomplete only shows that a phrase is searched, not how often. Phrases are ranked by recurrence across seeds and by whether they appear on a short prefix (SP). "Who shows up" comes from a US-based search tool. It never returned PetrolPulse, Finder or Bowser, so it is **not** a Google Australia ranking. Check positions in Search Console, or in an Australian incognito window.

**The fill-up clusters**

| Cluster | Phrases | Best answer on the web today | Bowser page |
|---|---|---|---|
| Fill up today? | should i fill up today (SP), should i fill up petrol today (most recurrent), …now or wait, …diesel today, …today or tomorrow, should i fuel up now | PetrolPulse homepage (a "wait" call for 8 capitals, FAQPage). Finder's widget needs script. Fuel Daddy said "fill now" in 32 cities on 21 Nov while prices fell. | Dashboard (title already "Should you fill up today?"). Adding "sydney" or "nsw" gives no suggestions, so target the bare phrase. |
| Direction | will petrol go up tomorrow / this week / or down; is petrol going up; when will petrol go down (SP: "…go down **sydney**" #2) | Stale news, NRMA weekly report, ACCC PDFs: no current page owns it. | `/fuel-price-forecast/`. "Tomorrow" and "this week" beat "next week". |
| Event-driven | will petrol go up because of iran / the war / in the budget / overnight | News, 2023–25. | Not built: event pages (see Next). |
| Forecast | petrol price forecast sydney / next week, fuel price prediction nsw | ACCC, NRMA archive, news. | `/fuel-price-forecast/`. |
| Cycle | petrol cycle sydney (SP), …cycle sydney today / tomorrow, fuel price cycle tracker | ACCC (says cycles have "mostly not occurred" since Feb 2026). | `/petrol-price-cycle/`. |
| Best day / time | best day to buy petrol in sydney (SP), cheapest day to buy petrol sydney (SP), is petrol cheaper at night | ACCC, **FuelRadar** (new; says "usually cheapest on Tuesday"), Yahoo, CarsGuide. | `/best-day-to-buy-petrol/` (our data: Tuesday is the *dearest* day, 0.6c from the cheapest). |

**New since the 20 Nov review**
- **FuelRadar:** FuelCheck-based, showing up for "should I fill up today sydney" and the best-day searches.
- **PetrolPulse:** its accuracy page claims 86% on 7,392 calls under lenient scoring (a fill counts as right unless prices fall 3c+; a wait counts as right if any cheaper day follows).
- **Finder:** `/fuel` was retitled "Tracking Australia's fuel crisis" (updated 14 Oct).

**Discount clusters**, biggest first:
1. **Costco fuel:** about 150 variants: price today / sydney / 98, each Sydney site plus "opening hours", "do you need membership", "is costco fuel cheaper".
2. **7-Eleven fuel lock:** "how does it work", "max discount", "not working", plus "7 eleven fuel codes {month} 2026" every month.
3. **Woolworths fuel discount:** "locations", "near me", "ampol"; "everyday rewards fuel voucher".
4. **Generic:** "fuel discounts nsw", "fuel discount app", "fuel discounts for seniors".
5. **Coles fuel docket / Flybuys.**
6. **Smaller:** NRMA, seniors, Reddy Express, U-GO, BP.

**"Deals" wording barely registers**, so the hub leads with "fuel discounts".

**Who shows up for discounts:**
- OzBargain wiki: the most complete, but dense and without prices.
- Point Hacks: written around earning points.
- Canstar Blue: last updated May 2025.
- Bill Hero: a page per program, with Article, FAQPage and Offer markup, but no prices.
- Yep Savings: a page per Costco site with FuelCheck prices, but last updated 22 Oct.

**The gap:** no page shows which discount *and* what it costs today at the stations that take it, and none says "use it now or wait".

**How Bowser wins**
- A dated, tested answer in plain HTML on every page, against stale news and NRMA archive pages.
- The only lock-timing advice backed by a forecast.
- Live prices before and after each discount.
- Not done, on purpose: no competitor is named on any page. An accuracy figure scored PetrolPulse's way is a possible later addition, on our own page, without naming them.

**Built 2026-11-22** (branch `seo/fill-up-cluster`):
- forecast-page title for "this week", plus questions for "tomorrow" and "when will petrol go down";
- a "today" cycle-page title;
- a best-day answer on time of day, from the hike-timing analysis;
- the dashboard's screen-reader H1;
- the discounts hub retitled, with dated offers (`until` drops an offer on its end date);
- `/7-eleven-fuel-price-lock/`, `/woolworths-fuel-discount/`, `/coles-fuel-docket/`;
- the Costco brand page fixed: it led with Canberra's U91, which Sydney's Costcos don't sell.

**Next (not built)**
- Visible verdict text on the dashboard: needs a visual and CLS check, and the owner asked for a simpler dashboard.
- Event pages before long weekends and excise changes.
- A diesel call on the dashboard.
- A monthly "7-Eleven fuel codes" page.
- A seniors fuel discount page.
- Costco site pages (Auburn, Casula, Marsden Park): only if `/brands/costco/` doesn't rank, since they would compete with it.

### Keyword research, 2026-11-26: new clusters and new competitors
**Method.** Same as 22 Nov: Google Autocomplete for Australia (30 new seeds), a US-based search tool for who shows up, and a fetch of the live site. Autocomplete shows that a phrase is searched, not how often. Rank these against Search Console positions before building anything.

**The constraint.** The domain is nine days old, with about 1,500 pages "crawled, currently not indexed". The bottleneck is authority (links) and indexing, not page count. So: a few high-value pages, no new programmatic sets.

| Cluster | Phrases seen (en-AU) | What exists | Call |
|---|---|---|---|
| Price history | petrol price history sydney, petrol price trend / chart sydney, historical fuel prices nsw, petrol prices 2026 graph, petrol price data last 10 years | Nothing dedicated; the data is in `history.json` (the Christmas page already goes back to 2019) | **Build.** One `/petrol-price-history/` page (long chart, yearly medians, biggest jumps). Plus a "Sydney petrol in 2026" data story in early January: the Middle East shock, the April–August excise cut, cycles that stopped. It's a press and link asset for the January news lull. |
| E10 / octane | e10 vs 91 (price, australia, fuel efficiency), is e10 bad for my car, 95 vs 98 (petrol price) | On the "More guides" list | **Build** two guides. Bowser's angle is today's live price gap and the break-even point (E10 uses about 3% more fuel), which no explainer has. |
| Fuel excise | fuel excise increase (2026, australia, date) | Nothing | **Build before 1 Feb 2027** (next CPI indexation day). Rate and factor from the ATO page on the day; don't quote a number from memory. Secondary sources say 53.7c/L since 3 Aug 2026, after the temporary cut ended: unverified. |
| Fuel shortage | is there a fuel shortage in australia today, fuel shortage nsw today, fuel crisis nsw update, australia petrol days left | Not doing (no reliable signal) | **Check the signal, not the page.** Find out whether FuelCheck shows out-of-stock or withdrawn prices dependably. If it does, a "stations without fuel today" count fits the hub. If not, leave the topic alone. |
| Diesel forecast | diesel price forecast sydney / nsw / next week / australia 2026 | `/fuel-prices/diesel/` has prices; the forecast page is U91-led | Only once diesel calls are scored in `track.json`. Say plainly that the Sydney DL forecast under-called the November fall. |
| Highway / trip | fuel prices hume highway (today), fuel stations on the hume highway, fuel prices pacific highway, sydney to canberra fuel cost | Region pages (Goulburn, Albury, Port Macquarie, Coffs, Tweed) | **Don't build corridor pages:** they overlap the region pages and spread crawl. Link region pages to each other along each highway instead, with prices only (no forecast wording). Route planner stays in "Not doing". |
| App | fuel price app nsw, best fuel price app nsw, best fuel app australia | `/` (WebApplication) | Once Play is public: Play link in the Organization `sameAs` and the About page. Get listed in the review articles below (outreach). Don't build a "best app" page. |
| Noise | m1 servo (car parts), foreign "petrol prices january", costco fuel casula * (covered by the Costco rule above) | | Skip. |

**New competitors** (seen 2026-11-26, not measured Google AU positions)
- **FuelRadar:** now publishes a dated "Australia's cheapest fuel prices" post every day (`/blog/cheapest-fuel-prices-YYYY-MM-DD`). It competes on news cadence; Bowser's dated equivalent is the weekly outlook.
- **FuelNow** (`fuelnow.com.au/petrol-prices/sydney`): city price pages with medians and the cheapest station.
- **Petrolmate** (`petrolmate.com.au/city/nsw/sydney`): web-only map with a "cheapest in view" highlight and wholesale-cycle tracking; CyberShack recommends it for SA and QLD. Its Sydney page showed a 1 Nov average on 26 Nov (stale).
- Government: `fuelplan.gov.au/fuel-statistics` (ACCC weekly figures) now shows up for Sydney price searches.

**Outreach targets** (for `docs/OUTREACH.md`, once the Play listing is public): CHOICE "best apps for finding cheap fuel", CyberShack "best fuel price app in Australia, state by state", carsales editorial on fuel apps, NRMA "how to find the cheapest fuel prices Sydney". Each lists apps by state; Bowser's pitch is the only tested forecast. The owner sends these.

**Search, from secondary sources (unverified, check Search Central):** the November 2026 core update has finished and a December one is preannounced; sponsored ads are now in AI Mode in Australia; Google says structured data isn't required for AI features. Googlebot reads only the first 2 MB of HTML (uncompressed; Google's March 2026 crawler post). The dashboard is 1.19 MB, but its footer text and links come within the first 40 KB, before the inline station data, so nothing indexable is past the cut. If `stations.json` keeps growing, keep the data after the footer.

### Features competitors have that Bowser doesn't (not built)
In rough order of value:
1. **Web alerts** ("a jump is coming"): email or browser push from the site. PetrolSpy and FuelWatch have them; Bowser's alerts live only in the app.
2. **Weekly outlook pages** (NRMA style): one dated address a week with an archive. Needs a weekly snapshot of the forecast saved on the `data` branch, because the pages are rebuilt from today's data only and `track.json` keeps calls without their ranges.
3. **Long-weekend pages** (Easter, Anzac Day, King's Birthday, Labour Day, Australia Day), on the Christmas page's pattern.
4. **An interactive "fill up today?" widget** with a tank slider (Finder). The static tank table covers the search side; a slider means new script, which every page's CSP hash has to allow.
5. ~~A free embeddable cycle-stage badge~~ built 2026-11-24: `/badge/`, see `docs/OUTREACH.md`.
6. **Author and method pages** (Finder has named authors and a "why trust us" page): a named person behind Bowser on /about/ would help E-E-A-T.
7. **Longer history charts** (1 year, all time) on fuel and station pages; the data is already in `history.json`.
8. **A 7-Eleven fuel price lock guide** tied to the forecast ("lock now: a jump is likely").
9. **A fuel outage tracker** (PetrolPulse, Fuel Daddy: "233 stations out of fuel"): a search topic during the 2026 shortages. It needs a dependable out-of-stock signal from FuelCheck, which hasn't been checked.
10. **Trip cost calculator and route planner** (PetrolPulse, Fuel Daddy).
11. **Pages for other cities** (Melbourne, Brisbane, Adelaide, Perth): skipped. There's no data for them, so they'd be thin pages.

## Next
- **Regions** (done 2026-11-17: 23 region pages, the hub retitled for NSW). Watch which regions get searches and add centres to `REGIONS` where a town is missing.
- **Deep links into the dashboard** (`/?area=Parramatta`), so "Open the live map" on a suburb page lands on that suburb.
- **Point the app's Share link** at the station page instead of `/s/`, so shared links are indexable pages with a preview image.
- **More guides** as Search Console shows demand: E10 vs 91, 95 vs 98, how fuel excise works, fuel prices at Easter and Christmas.
- **A weekly "Sydney petrol price outlook" post**, generated from the forecast: fresh dated content that news search likes.
- The dashboard has no `<!doctype>` (it renders in quirks mode). Adding one is right but can shift the layout, so it needs a visual check of its own.

## Search Console readings
- **2026-11-21 (four days of data).** 75 queries, 2–5 impressions each, no clicks: normal for a domain this new. Station-name searches came first, many for country stations, and their pages were the thinnest (no forecast, no chart yet). Those pages now say more, the hub title leads with "Check" for "nsw fuel price check", and "cheapest petrol deals sydney" got its own guide. **Next reading:** turn on the Average position and CTR columns. Position says whether a query needs authority (links) or a better snippet (title and description).
- **2026-11-26 (first technical review, 15–26 Nov; read through the Search Console API, PostHog and PageSpeed).**
  - **Totals:** 366 queries, 391 pages with impressions, about 1,000 impressions, 3 clicks. Average position 18 on mobile, 44 on desktop. Almost all from Australia. Daily impressions went from 4 to about 190 by 22 Nov.
  - **Where impressions land:** station pages are 763 of them, across 346 pages, at an average position of 30. They come from station-name searches ("budget fairfield", "eg kingswood"), and a dozen are already at positions 2–12. Brands had 157 impressions (position 46), region and fuel pages 64 (24), suburb pages 12 (51).
  - **Index sample (24 URLs):** 13 indexed, 5 "crawled, currently not indexed", 6 "unknown to Google".
    - **`/fuel-price-forecast/` is crawled, currently not indexed** (crawled 24 Nov), even though it has 1,250 words, no noindex and links from every page. Request indexing by hand.
    - Most suburb pages sampled are unknown to Google: not yet discovered.
  - **Head terms go to the wrong page:** "fuel price sydney", "nsw fuel price check" and "petrol prices sydney" show `/brands/` (positions 48–80) instead of `/fuel-prices/`, whose title doesn't say Sydney.
  - **Visits (PostHog, 14 days):** 434 pageviews from about 300 people, 289 of them on the dashboard. Google sent 7; the rest came from direct, Reddit, Instagram and Facebook. Station pages had 2 visits.
  - **Speed:** the lab score is 97–100 on every page type; the dashboard's mobile LCP is 2.0 s and everything else is 0.8–1.1 s. There aren't enough Chrome users yet for field data.
  - **Checked and fine:** http→https and www redirect with a 301; canonicals match what Google chose; Speedway Auburn and Speedway Auburn Road are two real stations.
  - **Note:** the sitemap's "indexed 0" in the API is a figure Google no longer fills in; read the Pages report instead.
