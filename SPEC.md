# Contact Site spec: Brenen's contact page + inventory (standalone, not Keyhand)

Standalone project for the contact page linked from his socials. Not part of Keyhand: own repo, no Keyhand services or specs.

Status: draft v2, 2026-11-12 (v2 follows his MOTO(insite) example). Build: Claude Code. Approver: Brenen. Nothing goes public without his yes.

## 0. Starting point (decided Nov 12)
Start from the contact page Muse already built on muse.ai, not from scratch. Keep its content, links and look where they fit; adapt and extend it to this spec.
- Step 0 (Muse): export the page source (HTML, CSS, images, any data files) into the `brenen-cars` repo under `import/muse/`, or into a Drive folder "Contact Site - Muse export" if Muse can't reach GitHub. If muse.ai has no export, Muse sends a full list of the page's text, links (label + destination), images and colors instead.
- Step 1 (Claude Code): rebuild that page into this spec's structure. Keep R1 to R7: strip any form, tracker, analytics, cookie, embed or external script/font that breaks them, and list every removal in the PR. Swap the dealer-site inventory link for the site's own inventory section.

## 1. Goal
One link-in-bio contact page plus a small inventory site. Every "contact" action on either one goes straight to Brenen (text, call, email). It replaces the dealer-website inventory link on his muse.ai contact page, so buyers who browse never land on the store's site where any rep can take the lead.

## 2. Hard rules (acceptance-blocking)
- R1 No personal info stored or collected. No forms, inputs that submit, backend, database, analytics, cookies, pixels, or third-party scripts. Every contact action is an `sms:`, `tel:` or `mailto:` link to Brenen. Nothing leaves the visitor's device until they press Send in their own app.
- R2 KC stores only. Drop Lawrence, Topeka and Independence stock using the same stock-prefix rule as `marketplace_picker.py` (`FAR_STORE` regex, copied in, with its tests).
- R3 Prices only when verified; never payments. A price is published only if it exactly matches the dealer website's current listing for that stock # (which includes the admin fee), checked read-only at build time; otherwise the car shows "Text me for price". No payment estimates, ever (they trigger Truth in Lending / Reg Z disclosures). Msrp, Leads, Last lead, Deals and Age never reach the public JSON.
- R4 No Cadillac logo, fonts or trademarks styled as the brand. "Black gold" look-alike only. Plain-text mentions of make/model are fine.
- R5 Photos only if Brenen has the right to use them (his own shots in `photos/`). No hotlinking the store's site images unless the GSM OKs it in writing.
- R6 Raw exports never committed. `data/raw/` and `*.csv`/`*.xlsx` are gitignored, and a test fails if any is tracked or if `inventory.json` holds a banned key.
- R7 All contact details live in one config file (`site.config.json`), never hard-coded in HTML.

## 3. Pages (v2: one page, structure from his MOTO(insite) example)
Layout pattern from his MOTO(insite) and Frddy screenshots: pattern only, no MOTO or Frddy branding, copy or rep content. Black-gold theme. One page `/index.html` with these sections in order, plus car detail at `/car.html?stock=XXX`. v1's separate contact page and the page list fold into this page.

1. **Sticky header pill:** small headshot, "Brenen", Follow button, menu button. Follow opens a sheet of his social links (no accounts, no sign-in; see C3). Menu jumps to sections.
2. **Hero:** large headshot in a gold bracket frame, name, "Sales Consultant · Cable Dahmer Cadillac", gold "Value my car" button (prefilled trade-value text to him, see C4), "Save to contacts" (`brenen.vcf`), social icon row.
3. **Inventory:** "N listed" count (no "from $"), search plus chips (New, Pre-owned, Demo, Make, Body). Two-column card grid on phone: photo carousel (arrows, dots, photo count) from `photos/<STOCK>/`, or a "Photos coming soon" silhouette when none. Year make model, trim in grey, condition badge (New, Pre-owned, Demo), mileage for pre-owned and demo, stock #. No price (see C1). Card opens `car.html`; buttons "Text me about this car" and "Book a test drive".
4. **"Tools before money moves" carousel** (cards with dots): vehicle history, insurance, budget, trade-in value, recalls/research, guess today's car. Which ones ship and how each is wired: C4.
5. **"Not seeing it?":** "The lot turns over fast. Text Brenen what you're hunting and he'll reach out when a match lands." Button opens `sms:` prefilled "Hi Brenen, I'm hunting for: Year / Make / Model / Color / Must-haves:" (see C2). Below it "Landed this week": up to 5 newest arrivals (converter sets `new_arrival` when Age is 7 or less; Age itself never published).
6. **Book a test drive:** client-side day strip and time slots (next 14 days; default Mon, Tue, Thu, Fri, Sat, 9:00 AM to 6:00 PM, 30-min slots, Central; Wed and Sun struck out; past slots hidden; car chip when opened with `?stock=`). "Text Brenen to book" opens `sms:` prefilled with car, day and time. No name or phone fields, no calendar writes.
7. **"Talk to Brenen" dark card:** headshot, name, "Sales Consultant · Cable Dahmer Cadillac · Kansas City, MO", gold "Message Brenen" (`sms:`), Call (`tel:`), social icons, map pin (Open in Maps / Get directions, no embedded map), hours table.
8. **Footer:** car research link, free-tools list, "Inventory and availability change daily. Text to confirm.", "Independent page by Brenen Prinzing, sales consultant. Not an official Cadillac or GM site." No creator or dealer sign-up links, no cookie banner (no cookies).

`car.html`: all his photos, same details and buttons; unknown stock shows "This one may have sold" plus a text button.

### 3.4 Choices for Brenen (example conflicts with his standing rules; the safe default ships until he picks)
- **C1 Prices: DECIDED Nov 12.** Prices shown only when they match the dealer site listing (admin fee included), with fine print disclosing the admin fee etc., like the example footer. Price source, so it can't drift:
  - `tools/check_dealer_prices.py` runs at build time only (never from visitors' browsers). For each kept stock #, it reads the dealer site's public listing page read-only (honors robots.txt and the site's terms, generic user agent, 1 request every 2 seconds, no login) and records the listed price and the check time.
  - Publish `price` only if the export's Pricing equals the site's listed price to the dollar and the check is under 24 hours old. Any mismatch, missing price, $0, robots block or failed fetch hides the price for that car ("Text me for price") and lists it in the terminal report.
  - The page hides every price if `inventory.json` is over 24 hours old.
  - Fine print: `price_disclaimer` in site.config.json, copied word for word by Brenen from the dealer site (admin fee amount, tax, title, license). Shown in the footer and under every price. Build fails if prices exist and the disclaimer is empty.
  - No payments, no "from $" headline, no "sale" language. Payment estimates stay out because they trigger Reg Z disclosures.
- **C2 "What you're hunting" alerts.** The example collects the shopper's contact info to notify them, which is customer PI his rule bars. Default: a prefilled text to him, so the request lands in his own phone and the site stores nothing. Option B: a form plus an alert service, which stores customer PI; hold until he and Claude talk.
- **C3 Follow, sign-in, favorites, cookies.** The example uses accounts and sign-in/visit cookies. Default: Follow opens his socials; no sign-in, no favorites, no cookies or analytics. Option B: favorites saved only on the shopper's own device (localStorage, nothing sent). Option C: cookieless visit counts (Cloudflare Web Analytics, free).
- **C4 Third-party tools.** All are outside links, no API, nothing embedded. Costs to confirm before build.
  - Vehicle history: DECIDED Nov 12. Per car, the same read-only build check picks up the free Carfax report link the dealer site shows on that listing, and the page links out to it ("View Carfax report"). Never copy, screenshot or re-host report content, since Carfax limits reports to the dealer's subscription. No link found, hide the button. Free fallback for all cars: NICB VINCheck (theft and total-loss check only).
  - Insurance compare: a link to a comparison site (e.g. The Zebra or Insurify). Free to the shopper, but that site collects the shopper's info itself and may pay referral fees. Option: leave out.
  - Budget: a payment calculator conflicts with C1. Default: leave out.
  - Trade-in value: default texts him (he appraises). Option: also link Kelley Blue Book or Edmunds (free to the shopper, but their instant offers can route the shopper to other dealers).
  - Recalls/research: NHTSA recall lookup and fueleconomy.gov, free government sites.
  - Guess today's car: built in-house, client-side, from KC inventory names (and his photos when he has them), six guesses, new car daily from a date seed. Free; no score saved unless C3 Option B.

## 4. Data flow
DriveCentric export (CSV/XLSX, by Brenen or later Muse) -> `data/raw/` (gitignored) -> `python tools/build_inventory.py data/raw/<file>` -> `inventory/inventory.json` (whitelisted fields only) -> commit + push -> GitHub Pages deploys.

Converter rules (`tools/build_inventory.py`, Python 3, pandas optional, stdlib csv required for CSV):
- Input columns seen in the Oct 27 export: Vehicle, Sold, Delivered, Trim, Stock Number, Pricing, Msrp, Mileage, Leads, Last lead, Deals, Age. Optional if present: VIN, Exterior Color, Interior Color, Body. Unknown columns ignored. Header match is case/space-insensitive.
- Keep a row only if: Sold != Yes; stock matches `^[A-Z]{1,3}\d{4,6}[A-Z]?$` (drops in-transit/order codes like `GHJWPW*O` and letter-only codes); not `FAR_STORE`; not listed in `data/exclude.txt` (Brenen's manual hold list, one stock # per line, for cars with another rep's deal in proposal).
- Split Vehicle into year/make/model (same as picker). Condition: `C\d+` = New, `DC\d+` = Demo, else Pre-owned (same as picker's `is_preowned`). Body from picker's TRUCKS/SEDANS sets, EV list added (LYRIQ, OPTIQ, VISTIQ, Escalade IQ/IQL, F-150 Lightning, iX), else SUV.
- Mileage shown only for Pre-owned/Demo, rounded to nearest 100 ("~52,800 mi").
- Output: `{"updated": "YYYY-MM-DD", "source_rows": n, "kept": n, "cars": [{stock, year, make, model, trim, condition, body, miles?, ext_color?, int_color?, vin?, photos: []}]}`. Allowed keys are a constant; anything else is a hard error.
- Photos: `photos/<STOCK>/*.jpg|webp` committed by Brenen; converter lists them. Max 1600px, stripped EXIF (converter warns if EXIF GPS found and refuses to build).
- Prints a review list to the terminal (not to the site): rows with Deals > 0, so Brenen can add any proposal-stage deals to `exclude.txt`.
- Idempotent: same input -> byte-identical JSON (sorted by condition, make, model, year desc).

## 5. File layout (new repo, assumed name `brenen-cars`)
```
site.config.json        name, title, tagline, bio, phone, sms_phone, email, store {name,address,maps_query}, hours[], booking {days, start, end, slot_min, tz}, socials{}, extra_links[], banner, headshot
index.html              the one page (sections 3.1 to 3.8)
car.html                car detail
brenen.vcf              generated from config by tools/build_vcard.py
inventory/inventory.json
assets/css/site.css     tokens: --bg #0b0b0c, --panel #151517, --gold #c9a24a, --gold-2 #e6c878, --text #f3efe6, --muted #a29d92
assets/js/*.js          vanilla ES modules, no framework, no CDN
assets/fonts/           self-hosted open-license fonts (e.g. Cormorant Garamond + Inter), not Cadillac fonts
assets/img/             banner, headshot, silhouettes, icons (SVG)
photos/<STOCK>/         Brenen's own car photos
tools/build_inventory.py, tools/build_vcard.py
data/exclude.txt        manual hold list
data/raw/               gitignored
tests/                  pytest
.github/workflows/ci.yml   runs tests on push; Pages deploy from main
README.md               "How to refresh inventory" in 3 steps
```

## 6. Acceptance tests (pytest, plus a headless check if cheap)
1. Converter on the Oct 27 export keeps 0 rows from Lawrence/Topeka/Independence, 0 Sold=Yes, 0 in-transit codes.
2. `inventory.json` contains none of: msrp, payment, leads, last_lead, deals, age. `price` appears only on cars whose dealer-site check matched within 24 hours; a mismatch fixture hides it.
3. Running the converter twice gives identical output.
4. Every `<a>` that contacts someone is `sms:`, `tel:` or `mailto:` to the config numbers/email; no other phone or email string appears in built HTML/JS.
5. No `<form>`, no `<input type=submit>`, no `fetch`/`XMLHttpRequest` to any origin other than same-origin `inventory.json`, no external `<script>`/`<link>` hosts, no cookies or `localStorage` writes.
6. Booking: Wed and Sun disabled; slots 9:00 to 5:30 start times; past slots today hidden (America/Chicago); sms body includes date, time and stock when passed.
7. `brenen.vcf` is valid vCard 3.0 and matches config.
8. No `*.csv`/`*.xlsx` tracked in git; `data/raw/` ignored.
9. Lighthouse-style budget: page weight under 500 KB without car photos; works with JS off for the contact links (booking needs JS; show plain "Text me to book" link in `<noscript>`).
10. Visual check at 375px and 1280px: no horizontal scroll; tap targets 44px+; text contrast AA on black.

11. Carousel works with 0, 1 and many photos; "Photos coming soon" when 0.
12. "Landed this week" shows only `new_arrival` cars; JSON has no age field.
13. No payment text, no favorites, no sign-in, no cookie banner. Every shown price has the disclaimer; build fails if prices exist with an empty disclaimer. Carfax button only where a dealer link was found, and it links out (no report content in the repo).
14. Every tool-card link points to a host on the config allow-list, with no tracking parameters added.

## 7. Hosting and domain (decided Nov 12)
- Live address: his own domain, e.g. BrenenPrinzing.com (exact name his pick). His socials point there. The muse.ai page is only the content source for the export, not the live link.
- Host: GitHub Pages from the public `brenen-cars` repo: free, HTTPS, no server, deploys on push. Public is safe because raw exports never get committed and only verified public prices are (R3, R6).
- Custom domain: repo gets a `CNAME` file holding the domain (placeholder `DOMAIN_TBD` until bought). DNS at his registrar: apex A records to GitHub Pages' IPs and a `www` CNAME to his `<username>.github.io`, per GitHub's Pages docs at setup time; then turn on "Enforce HTTPS".
- Buying the domain is Brenen's step, on his own registrar account, about $10 to $20 a year for a .com. Nobody else buys it. Turning on Pages and pointing DNS wait for his yes and the GSM's OK.
- Alternative if he wants the repo private: Cloudflare Pages (free, one more account).

## 8. Automation (flag)
- Inventory refresh, daily. By hand: upload export, run converter, review deals list, push, ~5 min. Today (no site): 0, but stale data costs leads.
- v1: Brenen drops the export to Claude Code: "refresh inventory" -> ~1 min of his time. ~25 hrs/yr vs a manual page edit.
- v2: Muse pulls the DriveCentric export daily (needs login, Muse's lane) and uploads it to a private drop; a scheduled job builds and pushes. ~5 hrs/yr more saved. Difficulty 3/5. Blocked on where the private drop lives (not this public repo).

## 9. Risks
- GSM approval: the site shows store inventory (and photos, if any) outside the store's site. Get the GSM's OK before going public.
- Ad rules: Cadillac/GM co-op and dealer ad rules plus Missouri and FTC rules apply to anything public. Mitigated by prices only when they match the dealer site, the dealer's own fee disclaimer, no payment claims, no "sale" language, and the availability disclaimer.
- Read-only pulls from the dealer site: check its terms and robots.txt first and get the GSM's OK; if either says no, prices and Carfax links stay hidden and the site still works.
- Stale inventory: sold cars stay up until refresh. Mitigated by the date stamp, 3-day banner and "text to confirm" copy.
- Another rep's deal: the export shows a deal count, not the stage. v1 relies on `exclude.txt` and the review list.
- sms: links behave slightly differently on iOS vs Android (`sms:NUMBER?&body=` works on both); desktop users get tel/mailto fallbacks.

## 10. Open questions for Brenen
1. ANSWERED Nov 12: the 816 line, 816-762-5779 (the number in his marketplace_picker.py listings); use it for sms_phone and phone. Brenen confirms the digits to Claude Code.
2. Email to show (default: none, text and call only).
3. Headshot and banner photo.
4. Social links (IG, TikTok, FB, YouTube, LinkedIn: which ones and URLs).
5. Tagline and bio line.
6. Store showroom hours for the hours card (default: your selling days and test-drive hours).
7. A fresh DriveCentric export; add color and VIN columns if the export allows.
8. Yes to create the repo and turn on GitHub Pages once the GSM OKs it.
10. The domain name to buy (e.g. BrenenPrinzing.com).
9. Picks for C1 to C4 (defaults stand until you choose).
