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
| bowser, check bowser, bowser fuel app | `/` (dashboard) | Brand. |
| nsw fuel prices, sydney petrol prices, fuel prices sydney today, cheapest petrol sydney, petrol prices near me | `/fuel-prices/` | Today's median, the 15 cheapest, every suburb linked. |
| petrol prices {suburb}, cheapest fuel {suburb}, {suburb} fuel prices | `/fuel-prices/{suburb}-{postcode}/` (384 today) | Long tail. Low competition per suburb, large in total. The main traffic source. |
| {station name} fuel price, 7-eleven parramatta petrol price | `/station/{name}-{id}/` (864 today) | Very long tail; price history and a per-station forecast nobody else has. |
| newcastle fuel prices, central coast petrol prices, wollongong fuel prices, canberra petrol prices | `/fuel-prices/{region}/` (23) | Median, 20 cheapest, the gap to Sydney, every suburb in the region. |
| e10 price sydney, diesel price sydney, 98 petrol price, unleaded 91 price today | `/fuel-prices/{fuel}/` (5) | Median, 25 cheapest, 90-day chart, brand table. |
| costco fuel price, 7-eleven fuel price, ampol/bp/shell petrol price, cheapest petrol brand | `/brands/`, `/brands/{brand}/` (22) | "costco fuel price" and "7 eleven fuel price" are among the largest fuel searches in Australia. |
| fuel price forecast, petrol price forecast/prediction (sydney), petrol prices next week, will petrol go up/down this week or tomorrow, should I fill up today or wait | `/fuel-price-forecast/` | The product. Updated five times a day: a 60-day + 14-day chart, the call, tank savings, and question-style answers (FAQPage) with today's numbers. Every "next week / tomorrow / prediction" search belongs here, not on new pages. |
| how accurate is the fuel forecast, fuel price prediction accuracy | `/fuel-price-forecast/accuracy/` | No competitor publishes a track record (2026-11-20 review). Trust page for Google and for people deciding whether to believe the call. |
| sydney petrol price cycle, petrol cycle sydney, where are we in the petrol cycle, is the petrol cycle back | `/petrol-price-cycle/` | Own data: a cycle-stage card, the latest jumps, cycle length by year. The ACCC's Sydney table is stale (stops in January 2026). |
| best day to buy petrol (sydney), cheapest day to buy petrol, is tuesday the cheapest day for petrol, is petrol cheaper on weekends | `/best-day-to-buy-petrol/` | Split out of the cycle page on 2026-11-20 (FuelRadar ranks a dedicated page). The answer, "no day in Sydney", backed by Bowser's weekday figures. |
| petrol prices christmas (sydney), will petrol go up before christmas, petrol prices holidays | `/petrol-prices-christmas/` | Every Christmas since 2019 from Bowser's own history, plus this year's outlook. One evergreen address, so it builds links year on year. |
| nsw fuel check, fuelcheck nsw, fuel check app, fuelcheck prices | `/nsw-fuelcheck/` | See the next section. |

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
- **`sitemap.xml`** (every page, dated today) and **`robots.txt`** (allows everything except the app's per-station JSON files).
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
| **News** (CarExpert, Yahoo, 9News, SMH) | "Prices tipped to rise" articles quoting NRMA or the ACCC. | A pitch angle: the forecast with its public record (Owner to do, item 4). |

### Features competitors have that Bowser doesn't (not built)
In rough order of value:
1. **Web alerts** ("a jump is coming"): email or browser push from the site. PetrolSpy and FuelWatch have them; Bowser's alerts live only in the app.
2. **Weekly outlook pages** (NRMA style): one dated address a week with an archive. Needs a weekly snapshot of the forecast saved on the `data` branch, because the pages are rebuilt from today's data only and `track.json` keeps calls without their ranges.
3. **Long-weekend pages** (Easter, Anzac Day, King's Birthday, Labour Day, Australia Day), on the Christmas page's pattern.
4. **An interactive "fill up today?" widget** with a tank slider (Finder). The static tank table covers the search side; a slider means new script, which every page's CSP hash has to allow.
5. **A free embeddable cycle-stage badge** for local news and community sites: a source of links.
6. **Author and method pages** (Finder has named authors and a "why trust us" page): a named person behind Bowser on /about/ would help E-E-A-T.
7. **Longer history charts** (1 year, all time) on fuel and station pages; the data is already in `history.json`.
8. **A 7-Eleven fuel price lock guide** tied to the forecast ("lock now: a jump is likely").
9. **Pages for other cities** (Melbourne, Brisbane, Adelaide, Perth): skipped. There's no data for them, so they'd be thin pages.

## Next
- **Regions** (done 2026-11-17: 23 region pages, the hub retitled for NSW). Watch which regions get searches and add centres to `REGIONS` where a town is missing.
- **Deep links into the dashboard** (`/?area=Parramatta`), so "Open the live map" on a suburb page lands on that suburb.
- **Point the app's Share link** at the station page instead of `/s/`, so shared links are indexable pages with a preview image.
- **More guides** as Search Console shows demand: E10 vs 91, 95 vs 98, how fuel excise works, fuel prices at Easter and Christmas.
- **A weekly "Sydney petrol price outlook" post**, generated from the forecast: fresh dated content that news search likes.
- The dashboard has no `<!doctype>` (it renders in quirks mode). Adding one is right but can shift the layout, so it needs a visual check of its own.
