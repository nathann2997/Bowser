# Outreach: links for checkbowser.app (roadmap item 9)

A new domain earns trust mostly through links from other sites. Item 9 has three parts:

| Part | Who | Status |
|---|---|---|
| Embeddable cycle-stage badge | built (`seo_pages.py` `badge_svg`, `/badge/`) | live after the merge and the next daily run |
| News pitch when a jump is forecast | **the owner sends**: it goes out under their name | kit below |
| NSW Government showcase listing | **the owner submits**: it is under their identity | text below |

Nothing here is sent automatically. Anything that writes to the outside world as Bowser (email, issues, social
posts) is the owner's to send.

## 1. The badge

- The image is at `https://checkbowser.app/badge/sydney.svg`: 360 × 104, with fixed colours, so it reads the same on light and dark pages.
  - It shows where Sydney is in the price cycle, from `seo_pages.cycle_stage()`, the same function as the cycle page. So the two never disagree.
  - It shows the day it is for, so a stalled feed shows its age.
  - It credits "Data: NSW FuelCheck".
- If the stage can't be worked out, it shows Bowser's U91 call. If that fails too, it shows a plain "See today's cycle stage" badge.
- `export_api.py` writes the image after the search pages, apart from them. A failed page build never breaks the image on the sites that show it, and the address must never change.
- The badge page, `https://checkbowser.app/badge/`, has a preview and the code to copy. That code is an `<img>` in a link to `/petrol-price-cycle/`.
  - It has no script and no tracking. Embeds aren't counted, on purpose.
  - It's linked from every page's footer, from the cycle page and from `llms.txt`.
- **Where to offer it:** local and suburban news sites, community Facebook pages with a website, car clubs, and motoring and personal-finance blogs.
  - Offer it in the same email as the pitch below, or on its own: "a free widget your readers might find useful".

## 2. News pitch when a jump is forecast

**When:** the badge and the cycle page show **"A jump looks likely soon"**. That means Bowser's U91 chance of a 5c-plus jump within 7 days is 35% or more (`JUMP_LIKELY` in `seo_pages.py`).
- That is the only trigger. Don't pitch on other days: a pitch is news only while the jump hasn't happened.
- Check the forecast page that morning before sending, and that https://checkbowser.app/badge/ loads.

**Who to send it to:**
- Motoring and consumer reporters at news.com.au, 9News, 7News, SMH/The Age (consumer affairs), Daily Telegraph, ABC Sydney, CarExpert, Drive and Yahoo Finance.
- Their "Prices tipped to rise" stories usually quote NRMA or the ACCC. Bowser's angle is a forecast with a public track record.

**Rules for honesty:**
- Quote the track record as it stands that day, from `https://checkbowser.app/fuel-price-forecast/accuracy/`. Never write "predicts jumps" or a hit rate from memory.
- The model is weaker on rises driven by wholesale prices: it has said Wait ahead of some 5c+ jumps (`docs/RULE_ANALYSIS_2026-10.md`, finding 3). So frame a forecast as a chance, never as a certainty.
- Say it is a forecast, for planning, not financial advice. Say who you are: independent, not NRMA or the government.

**Template** (copy, then fill the brackets from the forecast and accuracy pages that morning):

> **Subject:** Sydney petrol: a price jump looks likely this week ([chance]% chance, says a forecast with a public track record)
>
> Hi [name],
>
> Sydney's petrol price cycle looks close to its next jump. Bowser, an independent forecast built on the NSW Government's FuelCheck prices, puts the chance of a 5c-plus jump in the Unleaded 91 price within a week at [chance]%. Today is day [N] since the last jump, against a usual cycle of about [gap] days. The Sydney median is [price]c a litre.
>
> What makes it different from "prices tipped to rise": every call is scored in public a week later. [Track record sentence from /fuel-price-forecast/accuracy/, for example "Following its fill-or-wait call over the past year saved about [x]c a litre against filling up whenever you check."] It isn't always right, and the record shows that too.
>
> Happy to explain how the cycle works, or send a chart. Today's forecast: https://checkbowser.app/fuel-price-forecast/
> If it's useful for your readers, there's also a free badge for your site that shows where Sydney is in the cycle: https://checkbowser.app/badge/
>
> [Your name]
> Bowser · checkbowser.app · checkbowser@gmail.com

**After a pitch:**
- Log who, when and the result somewhere private (not in this repo: it is public), so the same reporter isn't pitched twice in one cycle.
- If a story runs, ask, once and politely, for a link to the forecast page.

**Not built, the owner's call:** an automatic heads-up when the trigger fires.
- Options:
  - A GitHub issue opened by the daily run. It's public on this repo, and needs `issues: write` in the locked `daily.yml`.
  - An email through a mail service. That needs an account and a secret.
- For now, check the cycle page or the badge.

## 3. NSW Government showcase listing

**Checked 2026-11-24:**
- API.NSW has a showcase at https://api.nsw.gov.au/Showcase, with tabs for Mobile app and Website.
  - Its "Built with our APIs" section lists FuelCheck apps (Fuel Check NSW, Fuel Check Tasmania, the my nrma app).
  - The page gives no way to submit.
- Data.NSW's FuelCheck dataset page has no apps section. Its contact is Fair Trading.
- The only route is the API.NSW contact form, https://api.nsw.gov.au/Support:
  - Choose "Others - please specify".
  - Name, email and details, with a captcha.
- The API terms set no attribution wording of their own. They defer to the data's licence: CC BY-SA 3.0 AU, as Bowser already credits it.

**Text for the form** (the owner submits it, from checkbowser@gmail.com):

> I'd like to ask whether Bowser can be listed in the API.NSW Showcase, under Website and Mobile app. Bowser (https://checkbowser.app) is a free, independent site and Android app built on the NSW FuelCheck API. It shows today's prices at every NSW station on a map, and adds a forecast for Sydney that says whether to fill up now or wait, with every call scored in public a week later. Prices are credited to NSW FuelCheck (© State of New South Wales, NSW Fair Trading, CC BY-SA 3.0 AU). It has no accounts, no cookies and no advertising. Google Play: [link once the app is public]. Happy to send screenshots or a short description in whatever format the showcase uses. Contact: checkbowser@gmail.com.

**Wait until the app is public on Google Play.** A listing with a working store link is stronger, and the showcase has a Mobile app tab.
