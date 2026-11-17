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
| fuel price forecast, will petrol prices go up/down this week, when to buy petrol sydney, petrol price prediction | `/fuel-price-forecast/` | The product. Updated five times a day with a public track record. |
| sydney petrol price cycle, petrol cycle sydney, cheapest day to buy petrol | `/petrol-price-cycle/` | Own data: days since the last jump, cycle length by year, the weekday myth with numbers. |
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

## Next
- **Regions** (done 2026-11-17: 23 region pages, the hub retitled for NSW). Watch which regions get searches and add centres to `REGIONS` where a town is missing.
- **Deep links into the dashboard** (`/?area=Parramatta`), so "Open the live map" on a suburb page lands on that suburb.
- **Point the app's Share link** at the station page instead of `/s/`, so shared links are indexable pages with a preview image.
- **More guides** as Search Console shows demand: E10 vs 91, 95 vs 98, how fuel excise works, fuel prices at Easter and Christmas.
- **A weekly "Sydney petrol price outlook" post**, generated from the forecast: fresh dated content that news search likes.
- The dashboard has no `<!doctype>` (it renders in quirks mode). Adding one is right but can shift the layout, so it needs a visual check of its own.
