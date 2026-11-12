# Brenen's contact page and inventory

One link-in-bio page (`index.html`) plus a car detail page (`car.html`). Every contact
button opens a text, call or email to Brenen. The site stores nothing and collects
nothing: no forms, no cookies, no analytics, no outside scripts or fonts.

Full spec: [SPEC.md](SPEC.md). Status of the Muse page import: [MUSE_INVENTORY.md](MUSE_INVENTORY.md).

**Not live.** GitHub Pages is off. The domain is `brenenprinzing.com` (in `CNAME` and
`site.config.json`); nothing points to this repo until Pages is turned on and the DNS
records below are added. Going live waits for Brenen's yes and the GSM's OK.

## How to refresh inventory (3 steps)

1. Save the DriveCentric export into `data/raw/` (that folder is never committed).
2. Run the converter:

   ```
   python tools/build_inventory.py data/raw/<export file>
   ```

   Read the terminal report. Every unsold car is listed, including ones with a deal on
   them (Brenen, Nov 12: rely on "Text to confirm"). To hold a specific car, add its
   stock number to `data/exclude.txt` and run again. `--list-deals` prints the cars
   that have a deal.
3. Commit `inventory/inventory.json` (and any new `photos/`) and push.

### Showing prices (optional, needs the GSM's OK first)

Prices stay hidden ("Text me for price") unless all of this is true:

1. `price_disclaimer` in `site.config.json` holds the dealer site's fine print, copied
   word for word by Brenen. The build fails if a price would show without it.
2. The read-only dealer-site check was run in the last 24 hours:

   ```
   python tools/check_dealer_prices.py data/raw/<export file> --yes
   python tools/build_inventory.py data/raw/<export file>
   ```

3. The export's price equals the dealer site's listed price to the dollar.

Any mismatch, missing price, $0, robots.txt block or failed fetch hides that car's
price and is listed in the terminal report. The page also hides every price once the
check is over 24 hours old. No payment estimates, ever.

The checker reads one listing page per kept car, at most one request every 2
seconds, with a generic user agent and no login. It also picks up the free Carfax
report link when the listing shows one; the site only links out to it.

> The price parser has only been tested against made-up sample pages. This build
> environment could not reach the dealer site. Before trusting it, run the check once
> with the GSM's OK and compare a few cars by hand. If it can't read the page it
> reports "not found" and hides the price; it never guesses.

## Keeping the page in sync with the dealer site

One command does the whole refresh:

```
python tools/refresh.py data/raw/<export file>                  # export only
python tools/refresh.py data/raw/<export file> --dealer-check   # plus the dealer site
```

- The **export** is the source for what's on the lot, what's new and what has a deal
  on it.
- With `--dealer-check`, every kept car's listing on the dealer site is read once. A
  car the dealer site **no longer lists is dropped** from the page, so a car that sold
  after the export doesn't linger. The same pass verifies prices and Carfax links.
- Safety: cars are dropped only when the same check found at least half of the
  checked cars. If most come back "not found", that is treated as a problem reading
  the site, nothing is dropped, and the report says so. A failed fetch or a
  robots.txt block never drops a car.
- Only pass `--dealer-check` once the GSM has OK'd read-only checks of the dealer site.

Between refreshes the page looks after itself: it shows the "Updated" date, warns
when the list is 3 or more days old, and hides every price after 24 hours.

### Muse's daily site list (the normal source from Nov 12)

Each morning Muse pulls the live inventory from the dealer site and saves it to the
private Drive folder "Daily Inventory Export". The converter reads Muse's
`inventory-store.csv` directly:

```
python tools/build_inventory.py data/raw/inventory-store.csv \
    --dc-export data/raw/inventory-dc.csv --site-checked-at <time Muse pulled the site>
python -m pytest
```

`inventory-dc.csv` is the DriveCentric export Muse used that morning. Paired by stock
number, it supplies the price to compare, Age (for "Landed this week") and Deals (for
the review list), and drops anything DriveCentric marks sold or delivered.

That file is already the dealer site's own list, so sold cars are gone from it. The
converter still applies every rule: KC stock only, hold list, whitelisted fields. It
never publishes the file's `vdp_url`, `photo_url` (the site serves its own copies of the
photos, never links to the dealer's) or `engine`.

**Price rule (Brenen, Nov 12).** A price shows only when the pull is under 24 hours
old and:
- **Pre-owned:** DriveCentric's price is exactly $620 (`dealer_site.admin_fee`, the
  Administrative Fee) less than the site price.
- **New and demo:** DriveCentric's price equals the site price to the dollar. The site
  adds no fee to these.

The site price is the one shown. Anything else says "Text me for price".

Commit `inventory/inventory.json` only. Never commit anything from `data/raw/`.

`tools/check_dealer_prices.py` and `tools/refresh.py --dealer-check` remain as a
fallback for building from a raw DriveCentric export. They have never run against
the real site.

## What Brenen still needs to send

These are still empty in `site.config.json`. Nothing was invented.

| Setting | Now | What it does when filled |
|---|---|---|
| `bio` | empty | A second line under the tagline. |

Already filled: headshot and banner (Brenen's images), domain, price fine print
(typed from Brenen's photo of the dealer site; he should proofread it), phone, email, and from Muse's page the
tagline, store address, Facebook and Instagram links, test drive hours and the hours note. Details in [MUSE_INVENTORY.md](MUSE_INVENTORY.md).

The phone and text number is 816-601-1688 (Brenen's agent line) for both `phone` and `sms_phone`.

After any change to `site.config.json`:

```
python tools/build_site.py
```

That rewrites `index.html`, `car.html` and `brenen.vcf`. Don't edit those three by
hand; edit `site.config.json` or the templates in `src/`.

## Car photos

Decision (Brenen, Nov 12, 2026): rule R5 has one exception. The public-facing
inventory may use the store's own public listing photos of each car, the same ones
used in Brenen's Marketplace listings. **R5 still applies to everything else:** any
other image on the site (headshot, banner, anything not a listing photo of a car in
the inventory) must be Brenen's own or one he has the right to use.

How they get here:

1. **Muse** pulls each car's photos once from the dealer site into the private repo
   `contact-site-inventory`, as `photos/<STOCK>/01.jpg`, `02.jpg`, ... (up to 5, in the
   order the listing shows them). Muse re-pulls a car only when its listing photos
   change, and can delete the folder when the car leaves the list.
2. **The daily refresh** runs `tools/sync_photos.py` before the converter. It resizes
   each photo to 960px, strips all EXIF data, and writes `photos/<STOCK>/site-NN.jpg`.
   A photo is only reprocessed when Muse's copy changes. Folders for cars no longer
   listed are removed.

```
python tools/sync_photos.py <inventory repo>/photos --inventory <inventory repo>/inventory-store.csv
```

Brenen's own shots can still go in `photos/<STOCK>/` under any other file name; they
show first. See [photos/README.md](photos/README.md). The sync tool needs Pillow
(`pip install pillow`).

Size: about 60 KB a photo, so roughly 70 MB for 236 cars at 5 photos each. Old photos
stay in the repo's git history after a car sells; if the repo grows past a few
hundred MB the history can be trimmed.

## Tests

```
pip install pytest
python -m pytest
```

Needs Python 3.10 or newer. Node 20+ is used for the booking tests and skipped if
missing. The tests cover the store, sold and in-transit filters, the banned fields,
price rules, the contact-link and no-tracking rules, booking times and the vCard.

Optional browser check (needs Playwright):

```
python -m http.server 8765
node tests/headless_check.mjs http://127.0.0.1:8765
```

## Domain and DNS (do not do this yet)

Order of steps, all Brenen's, after the GSM's OK:

1. **Buy the domain** at a registrar of his choice, on his own account (about $10 to
   $20 a year for a .com).
2. **Domain in the repo: done.** `CNAME` and `site.config.json` hold `brenenprinzing.com`.
3. **Add these DNS records at the registrar.**

   | Type | Host / Name | Value |
   |---|---|---|
   | A | `@` | `185.199.108.153` |
   | A | `@` | `185.199.109.153` |
   | A | `@` | `185.199.110.153` |
   | A | `@` | `185.199.111.153` |
   | CNAME | `www` | `brenenprinzing.github.io` |

   Optional, for IPv6:

   | Type | Host / Name | Value |
   |---|---|---|
   | AAAA | `@` | `2606:50c0:8000::153` |
   | AAAA | `@` | `2606:50c0:8001::153` |
   | AAAA | `@` | `2606:50c0:8002::153` |
   | AAAA | `@` | `2606:50c0:8003::153` |

   Remove any parking or forwarding records the registrar added for `@` and `www`.
   Check the values against GitHub's "Managing a custom domain for your GitHub Pages
   site" page on the day, in case GitHub has changed them.
4. **Turn on GitHub Pages**: repo Settings, Pages, Source "Deploy from a branch",
   branch `main`, folder `/ (root)`. Enter the domain under "Custom domain".
5. Wait for the DNS check to pass (minutes to a day), then tick **Enforce HTTPS**.
6. Remove the `noindex` line from `src/index.template.html` if he wants the page to
   show up in search, and rebuild.

If he'd rather keep the repo private, Cloudflare Pages is the alternative (spec 7).

## Layout

```
site.config.json        every contact detail and setting (R7)
src/                    page templates
index.html, car.html    built pages (tools/build_site.py)
brenen.vcf              built contact card
inventory/inventory.json  public inventory (whitelisted fields only)
assets/                 css, js (vanilla modules), self-hosted fonts, placeholder images
photos/<STOCK>/         Brenen's own car photos
tools/                  sync_photos.py, refresh.py, build_inventory.py, check_dealer_prices.py, build_site.py, build_vcard.py
data/exclude.txt        manual hold list
data/raw/               exports and price checks (gitignored)
import/muse/            where Muse's page export would go
tests/                  pytest, plus Node tests for the page logic
```
