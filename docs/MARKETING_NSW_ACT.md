# Bowser: NSW + ACT search and marketing spec (marketer, 2026-11-24)

Research and spec only. Nothing in the repo was edited and nothing was posted. Code references are to `/Users/nathan.nguy/Documents/bowser-act` (main @ dbeca7f), `sydney/pipeline/seo_pages.py`. Live checks of checkbowser.app were made on 2026-11-24.

**Rule for every line below:** wherever "Sydney" describes the **forecast**, it stays (forecast, call, outlook, cycle, best day, Christmas, 7-Eleven lock timing, Sydney medians). Wherever it describes **coverage** (prices, stations, suburbs), it changes to "NSW and ACT". Never write anything that suggests Canberra has a forecast or a call.

## A0. Fix first: false or broken things on live ACT pages

These come before any retitling. Item 1 is a Misleading Claims risk.

1. **False copy on every ACT suburb page.** `suburb()`, in the "Where do these prices come from?" paragraph, says "every NSW service station must report its prices to the NSW Government… Bowser reads those prices several times a day **and adds a forecast**." That is wrong for the ACT on two counts.
   - In the ACT, reporting to FuelCheck is voluntary. The ACT Government said in 2023 that about 95% of stations had signed up. Validator (2026-11-24): still opt-in, no mandatory law found; a minister said in Sep 2026 that all ACT retailers now take part (one source, undated).
   - There is no forecast for ACT pages.

   Add an ACT/`out` branch: "ACT stations that report to NSW FuelCheck (reporting is voluntary in the ACT, so a few may be missing). Bowser reads these prices several times a day. Its forecast covers Sydney only, so this page shows prices only." For NSW stations outside Sydney, keep "must report" but also drop "and adds a forecast".
2. **ACT station pages drop `streetAddress` from the GasStation schema.** The regex `^(.*?),\s*(.+?)\s+NSW\s+(\d{4})$` doesn't match "4 LUXTON ST, BELCONNEN ACT 2617". Change it to `\s+(NSW|ACT)\s+(\d{4})$` and set `addressRegion` from that group.
3. **`state_of()` uses postcodes only, so Hume (ACT, postcode 2620) is labelled NSW.** 2620 covers both Queanbeyan (NSW) and Hume, Beard, Oaks Estate and Tharwa (ACT). Take the state from the address suffix and fall back to the postcode only when there is no address. Send this to the validator.
4. **Junk suburb pages:** `express-manuka-2603` and `fyshwick-wiluna-2609` look like station names leaking into the suburb field. The validator should fix the parsing. Don't target either page.
5. **ACT station pages link to "Cheapest Unleaded 91 in Sydney today".** For stations outside Sydney, replace this with "Cheapest {fuel} in Canberra" (the region page) and keep the Sydney link for Sydney stations only.

## A1. Page-by-page titles, descriptions, H1s and schema

The examples use today's live numbers. Every figure is filled at build time.

| Page | Current | Proposed | Sydney mentions |
|---|---|---|---|
| **Dashboard `/`**, title | Should you fill up today? Sydney fuel prices \| Bowser (52) | **No change.** SEO.md found that adding a place to "should I fill up today" gets no autocomplete suggestions, and a 70-character version is too long. | STAYS (forecast) |
| Dashboard, description | "…Bowser's call for Sydney: wait if you can. U91 is 202.9c/L (24 Nov), with live prices at 2,381 NSW stations." | "…call for Sydney: wait if you can. U91 is 202.9c/L (24 Nov). Live prices at {n} stations across NSW and the ACT (computed; today's 2,381 may already include the ACT)." (≤155) | Call: stays. Stations: change |
| Dashboard, other text | `WebSite.description` "Sydney fuel prices today…". Footer summary. Search error "No NSW suburb matches" | `WebSite.description`: "Fuel prices at every NSW and ACT station that reports to NSW FuelCheck, and a Sydney forecast of when to fill up." Search error: "No NSW or ACT suburb matches". The H1 `sr` text and the "Cheapest in Sydney" default list stay. | mixed |
| Dashboard schema | `Organization`, `WebSite`, `WebApplication`, no `areaServed` | Add `areaServed: [{"@type":"State","name":"New South Wales"},{"@type":"State","name":"Australian Capital Territory"}]` to `Organization` and `WebApplication` | — |
| **Hub `/fuel-prices/`**, title | Check NSW fuel prices today: cheapest petrol by suburb \| Bowser (61) | **Check NSW and ACT fuel prices: cheapest petrol by suburb \| Bowser** (65). Keep "Check": it came from the GSC query "nsw fuel price check". | change |
| Hub, description | "NSW and Sydney petrol prices for 24 Nov: Sydney U91 median…" | "NSW and ACT petrol prices for 24 Nov: Sydney U91 median 202.9c/L, Bowser's call: wait if you can. Cheapest fuel in 1,111 suburbs." | median and call stay |
| Hub, H1 and lead | "NSW fuel prices today" | **"NSW and ACT fuel prices today"**. Lead: "…{n} stations in {m} suburbs across NSW and the ACT… and for Sydney tells you whether to fill now or wait." | change; forecast clause stays |
| Hub, body | Region table: "main centres outside Sydney" | Rename to "Fuel prices outside Sydney (NSW and ACT)". Add an `id="canberra"` block above the table: Canberra median, cheapest station, the gap to Sydney and a link to the Canberra page. The Q&A gets "Does Bowser forecast Canberra prices? No…" (see the region row). | — |
| Hub, `Dataset` | name "NSW service station fuel prices and Sydney price forecast", `spatialCoverage` "New South Wales, Australia" | name "NSW and ACT service station fuel prices and Sydney price forecast". `spatialCoverage`: "New South Wales and the Australian Capital Territory, Australia". Description says "Sydney forecast" explicitly. | forecast stays |
| **Canberra page `/fuel-prices/canberra-and-queanbeyan/`** (keep the URL), title | Canberra and Queanbeyan fuel prices today \| Bowser (falls back from the 65-character version) | **Canberra fuel prices today: U91 from 211.9c \| Bowser** (52). Fallback: "Canberra fuel prices today \| Bowser". Implement as a per-region `title_name` override. | n/a |
| Canberra page, description | "Petrol prices in Canberra and Queanbeyan for 24 Nov: U91 from 211.9c/L at Metro Petroleum Crestwood, median 218.9c. Compare 76 stations, from NSW…" | "Canberra petrol prices for 24 Nov: U91 from 211.9c at {station}, median 218.9c (16c over Sydney). {n} ACT and Queanbeyan stations compared." | gap to Sydney stays |
| Canberra page, H1 | Canberra and Queanbeyan fuel prices today | Keep. It is accurate, since the page includes Queanbeyan, Googong, Jerrabomberra and Sutton. | — |
| Canberra page, body | Cheapest 20, suburbs A–Z, "fill-or-wait forecast… doesn't cover" paragraph | (a) **District sections** (H2 plus the 5 cheapest each) from a postcode map: Belconnen 2614–2617; Gungahlin 2911–2914; Inner North 2601, 2602, 2612; Inner South 2600, 2603, 2604; Fyshwick and Airport 2609; Woden 2605–2607; Weston Creek and Molonglo 2611; Tuggeranong 2900–2906; Queanbeyan and surrounds (NSW). (b) An **ACT vs Queanbeyan median** line. (c) An honest **FAQPage**: "What is the cheapest petrol in Canberra today?" and "Does Bowser forecast Canberra prices?", answered: "No. The forecast is built on Sydney prices and covers Sydney only. For Canberra, Bowser shows today's prices so you can compare stations." (d) Add an `ItemList` of the stations. Keep the existing no-forecast paragraph. | must say "Sydney only" |
| **Other region pages** (22) | fine | No change apart from the "outside Sydney" wording | — |
| **ACT suburb pages** (about 35) | title "Belconnen fuel prices today: U91 from 218.9c \| Bowser". Description "Petrol prices in Belconnen ACT 2617 for…" | Titles stay (good already). Description adds "Canberra": "Petrol prices in Belconnen, Canberra ACT 2617 for 24 Nov…" (only if it fits within 155). Body: the A0.1 copy fix, plus a link to "{district} on the Canberra page" (`#belconnen`). | — |
| **ACT station pages** | title fine. Description "Today's prices as reported to NSW FuelCheck." | Titles stay. Schema fixes A0.2 and A0.3. Breadcrumb: Fuel prices › Canberra › suburb › station (for ACT stations, add the region crumb). | — |
| **Fuel pages** (5) | "Unleaded 91 price in Sydney today…" | **Titles and H1s stay "Sydney"**: they are Sydney medians with the call. Only rename the "{fuel} prices outside Sydney" table to "…outside Sydney (NSW and ACT)". | STAY |
| **Guides** (forecast, accuracy, cycle, best day, Christmas, 7-Eleven lock, dockets, deals) | Sydney | **No change.** All of them are forecast or Sydney-cycle content. Exception: `/brands/costco/` gets one sentence noting that the Canberra Airport Costco sells U91, with a link. | STAY |
| **Footer nav** (every page) | "Sydney fuel prices" → `/fuel-prices/` | "NSW and ACT fuel prices" | change |
| **`llms.txt`** | "…fuel prices in New South Wales, Australia… {n} service stations" | "…fuel prices in New South Wales and the Australian Capital Territory, Australia. It shows today's price at {n} stations (including about {act_n} ACT stations that report to NSW FuelCheck)… and adds a forecast **for Sydney only**…" Heading becomes "Regions outside Sydney (NSW and ACT; prices only, no forecast)". Add an example ACT URL (`/fuel-prices/belconnen-2617/`). Keep "Forecasts… cover Sydney only". | forecast stays |
| **`robots.txt`** | — | No change | — |
| **`sitemap.xml`** | ACT pages present, `lastmod` from price dates | No change. Optionally raise the Canberra page's priority from 0.8 to 0.9. | — |
| **Play short description** (80) | "Sydney petrol price forecast: fill up today or wait? Cheapest fuel across NSW." | **"Sydney petrol price forecast: fill now or wait? Cheapest fuel in NSW and ACT."** (77) | forecast stays |
| **Play long description** | "The forecast covers Sydney; prices cover all of NSW." | "The forecast covers Sydney only. Prices cover NSW and the ACT stations that report to NSW FuelCheck." Bullet: "cheapest stations near you… across NSW and the ACT". The first line already says "or any government agency", which covers the ACT. Keep FuelCheck as the source link. The **validator** should confirm the licence and attribution for ACT records. | forecast stays, coverage changes |

**Redirects and canonicals:** none. No existing URL changes. The host is static, so it can't serve 301s anyway. Every new thing below is an addition.

## A2. Decisions: Canberra pages

- **One page owns "canberra petrol prices": the existing `/fuel-prices/canberra-and-queanbeyan/`.** It has been indexed since 17 Nov and matches what Canberrans want: Queanbeyan and Fyshwick are where the cheap fuel is. Retitle it so it leads with "Canberra".
- **Don't build `/fuel-prices/canberra/`.** It would compete for the same query and split the signals. If a short address is wanted for sharing, use a `noindex` stub left out of the sitemap, with a canonical and a meta refresh to the Canberra page. That is optional.
- **Don't build `/fuel-prices/act/` now.** "act fuel prices" is served by the hub's `#canberra` block and the Canberra page. Revisit it only if GSC shows "act" queries landing on the wrong page.
- **Do add 2 district pages (phase 2, same pass if time allows):** `/fuel-prices/tuggeranong/` and `/fuel-prices/woden/` (Woden and Weston Creek). They own queries that no page answers today: there is no Tuggeranong or Woden suburb page, because the stations sit in Greenway, Wanniassa, Kambah, Phillip, Mawson and so on. **Do not add them to `REGIONS`.** `s["region"]` is a single value (the nearest REGIONS centre), so that would pull those stations off the Canberra page and out of its median. Use a separate postcode grouping instead: a `DISTRICTS` dict and an `s["district"]` field. A station keeps its Canberra region and also joins a district. The same field drives the A1 district sections. Pages are prices only, use the same no-forecast paragraph and need 5+ stations. District slugs must not collide with suburb slugs.
  - Belconnen and Gungahlin keep their existing suburb pages (`belconnen-2617`, `gungahlin-2912`), which link to their district section.
- **Internal links:**
  - hub `#canberra` → Canberra page;
  - Canberra page ↔ ACT suburbs and the district pages;
  - ACT station → Canberra page (A0.5);
  - fuel pages already link to it from the regions table.
  - Don't add Canberra links to Sydney suburb or station pages: they aren't relevant there.

## A3. ACT keyword targets

Volumes are unmeasured. Confirm them in GSC and Keyword Planner.

| Query | Intent | Target page |
|---|---|---|
| canberra petrol prices, canberra fuel prices (today), petrol prices canberra | Local prices now | Canberra page |
| cheapest petrol / fuel canberra, cheapest unleaded canberra | Find the cheapest | Canberra page (cheapest 20, FAQ) |
| canberra diesel price, e10 / 98 canberra | Price for one fuel | Canberra page. Phase 3: per-fuel anchors. Don't create Canberra fuel pages yet. |
| act fuel prices, fuel prices act | Territory-wide prices | Hub `#canberra`, then the Canberra page |
| belconnen / gungahlin fuel prices, petrol {suburb} | Local | Existing suburb pages |
| tuggeranong / woden petrol prices | District | New district pages (A2) |
| queanbeyan petrol prices, fyshwick fuel | Local, "cross the border" | `queanbeyan-2620`, `fyshwick-2609` |
| costco fuel canberra | Brand | Costco Canberra Airport station page, plus `/brands/costco/` |
| {brand} {suburb} canberra (e.g. "7-eleven kambah") | Station | Station pages |
| will petrol go down canberra, canberra fuel forecast | Forecast | **Don't target.** No page should promise this. The FAQ answer says Bowser doesn't forecast Canberra. |

**Competitors.** The source was a US-based search tool, the same caveat as SEO.md, so these are not measured positions in Google Australia.
- **FuelRadar:** city, ACT suburb and fuel pages, with "usually cheapest on Sunday". Its prices are snapshots of uncertain date: don't quote them.
- **PetrolPulse:** `/petrol-prices/canberra`, 69 stations, and it claims a Canberra fill-or-wait call. It has no suburb pages.
- **Others:** Region Canberra/RiotACT and the Canberra Times (news), the NRMA ACT fuel pricing report, PetrolSpy, and FuelCheck itself.

**Where Bowser wins:** crawlable suburb and station pages, district grouping, and an honest Queanbeyan/Fyshwick gap. Don't copy anyone's content.

## B. Marketing plan, NSW + ACT

**Value proposition for Canberra (be honest about it):** the cheapest stations near you, and how much crossing to Queanbeyan or Fyshwick saves. Price history only becomes usable around **7 Dec**: Bowser only started keeping prices outside Sydney on 17 Nov (FuelCheck has covered the ACT since Nov 2022), and charts need 20 days. **No forecast for Canberra**, and every post says so.

**Data angles.** Every number comes from the live site on the day: [TBF] means to be filled from live data. Never invent figures.
- The Canberra median vs Sydney's [TBF]. Today's live page showed a gap of about 16c on U91; recheck before using it.
- ACT median vs Queanbeyan median, and the cheapest district vs the dearest [TBF].
- How many ACT prices are over 7 days old [TBF]: an honest data-quality line.
- After 7 Dec: how often ACT stations move their prices, i.e. whether Canberra has a cycle at all [TBF]. This is a good press angle if the data supports it.

### 4-week sequence

| Week | Actions |
|---|---|
| 1 (after the copy, SEO and A0 fixes ship) | GSC: URL Inspection → Request indexing for the Canberra page, the hub and 5 large ACT suburbs. Resubmit the sitemap. Create a GSC page filter for ACT pages (see the regex note below the table). Record baseline impressions. Confirm IndexNow fired for the ACT pages. |
| 2 | **Owner:** post on r/canberra (draft 1) after reading the live sidebar. Hold the comment reply (draft 2) for a "petrol is expensive" thread. |
| 3 | Once charts exist (from about 7 Dec), write a short data note: "Does Canberra have a petrol cycle?" (Bowser's own numbers, [TBF]). **Owner:** pitch it to Region Canberra/RiotACT, the Canberra Times and ABC Radio Canberra (see the press section). |
| 4 | GSC review: which ACT queries show impressions and at what position. Decide whether to build Tuggeranong/Woden if not built yet, and per-fuel Canberra anchors. **Owner:** if allowed, a second community, r/queanbeyan (draft 3), or a Whirlpool motoring thread. |

**GSC ACT filter.** Station URLs end in the FuelCheck ID, not the postcode (for example `eg-ampol-belconnen-18816`), so a postcode regex misses most ACT station pages and catches Sydney stations whose ID happens to look like a postcode. Build the filter from `stations.json`: ACT station IDs plus ACT suburb slugs, including 2620 Hume. Alternatively, ask the validator for the list. Paste it into GSC's "Custom (regex)" page filter as plain text, for example:

```
canberra|tuggeranong|woden|/fuel-prices/[a-z0-9-]+-(26(0[0-9]|1[0-7])|29(0[0-9]|1[0-9]))/|/station/[a-z0-9-]+-(18816|18773|...)/
```

NSW continues in parallel, with no change to earlier plans. Don't repeat subs already posted to. Hold the r/sydney, r/AussieFrugal and r/CostOfLivingAU drafts for a forecast jump day, forecast first.

### Community drafts

Text only. The owner decides whether and when to post. Each is unique. **Rules check is unverified:** Reddit blocked automated reads. A mirror of the r/canberra wiki says posts must be "of unique relevance to Canberra" and that "profiles with a history of commercial advertising will be banned". The **owner must read each sub's sidebar first**, use the personal account with normal history, and message the mods if unsure.

**Draft 1: r/canberra post.** Title: "Made a page that ranks Canberra servos on FuelCheck by today's price (plus Queanbeyan), here's what it shows". Post only if the district sections shipped in week 1; otherwise drop the last paragraph's question.

> I've been building a fuel price site for NSW and recently it started picking up the ACT stations that report to FuelCheck, so I made a Canberra page. Today the cheapest U91 in the whole area was [TBF]c at [TBF], and the typical Canberra price was [TBF]c, so on a 50L tank that's about $[TBF] just from picking the right servo. Queanbeyan/Fyshwick vs the rest of the ACT was [TBF]c apart.
>
> Being upfront: I built it, it's free, no ads or account. It does NOT predict Canberra prices. There's a fill-or-wait forecast but it only covers Sydney, so for Canberra it's just today's prices sorted cheapest first, by suburb and district. A few prices are a week+ old, those are flagged.
>
> Curious if the district grouping makes sense to locals (is Fyshwick its own thing or part of the inner south in your head?). checkbowser.app/fuel-prices/canberra-and-queanbeyan/

**Draft 2: r/canberra comment reply** (on a "why is petrol so expensive here" thread):

> For what it's worth I checked this morning. Canberra median U91 was [TBF]c vs Sydney's [TBF]c, but the spread inside Canberra is pretty wide too, [TBF]c between cheapest and dearest. [TBF suburb] was cheapest. (I run a little prices site that pulls the FuelCheck feed, happy to share the link if anyone wants it.)

Add the link only if someone asks.

**Draft 3: r/queanbeyan** (check that the sub exists and is active first):

> Quick one for anyone commuting into Canberra. Queanbeyan servos were [TBF]c cheaper than the ACT median for U91 today, roughly $[TBF] a tank. I made a page that lists Canberra and Queanbeyan servos together, cheapest first (I built it, free, prices only, no forecast for this area). checkbowser.app/fuel-prices/canberra-and-queanbeyan/

### Press and blog angles (owner sends; contact is checkbowser@gmail.com, no GitHub links)
- **Region Canberra / RiotACT:** "Canberra paid [TBF]c more than Sydney for petrol this month; Queanbeyan saves [TBF]" or, after 7 Dec, "Does Canberra have a petrol cycle? A month of station data says [TBF]." They regularly run fuel-price stories.
- **Canberra Times, ABC Radio Canberra:** the same data, timed to a price spike or a long weekend (Christmas).
- Always say "prices only for Canberra; the forecast covers Sydney".

### Listings
- **Google Business Profile: skip.** Bowser has no physical location or service area that qualifies, and a fake address breaks the rules.
- **Worth asking (owner):** the ACT Government's FuelCheck page and the data.nsw "apps using this data" showcase, if either lists third-party apps.

### Measuring success
- **GSC (the main measure):** impressions, clicks and position for the ACT page filter and for queries containing canberra, act, queanbeyan, tuggeranong, woden or belconnen. Check weekly.
  - Week-4 targets: the Canberra page indexed, ACT queries showing impressions, and a position recorded for "canberra petrol prices". No click target yet, because the domain is too new.
- **PostHog** records page *type* only, by design (the privacy promise), so it can't separate ACT from NSW. Use it only for overall "region" pageview trends. **Don't add a suburb or state to events.**
- **Reddit:** referral sessions show up in PostHog only as referrer totals. Note upvotes and comments by hand in the subreddit log.

## Owner actions (accounts, posting, identity)
1. Post the Reddit drafts after checking the rules; choose the account.
2. Send the press pitches from checkbowser@gmail.com.
3. Update the Play listing (short and long description) **only after the current closed-test review clears**, ideally with the next release. Edits trigger a new review.
4. Request indexing in GSC (it can be done by a session with access, but it's the owner's account).
5. Contact the ACT and NSW showcase pages if they exist.

## Open questions for the data validator
- Is ACT reporting still voluntary?
- What licence and attribution apply to ACT records in the NSW API?
- Hume and 2620 state detection.
- Junk suburb names.
- The number of stale ACT prices.
