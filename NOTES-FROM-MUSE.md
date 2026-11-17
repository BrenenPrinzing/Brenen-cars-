# Notes from Muse (for Claude)

Muse pushes small, Brenen-approved updates to this repo from the Muse side.
Read this file after pulling main. Newest first.

## 2026-11-17 (later) — Phone retest: TWO defects remain, handed to Claude Code
Brenen retested on his iPhone inside the Facebook app's in-app browser after
7160e39. Social links behave now. Two defects remain, both webview-specific:

1. sms: buttons STILL do nothing in the FB webview. Tapping "Value my car"
   (hero gold button and the Tools > Trade-in value card; both are
   sms:+18167625779?&body=... built by lib.js smsHref) produces no Messages
   hand-off, no error, nothing. Same hrefs work in desktop Chrome (they
   resolve as links; no handler there to prove the hand-off). The "?&body="
   form is lib.js's deliberate iOS+Android shape. Whatever fix is chosen must
   keep the exact prefilled bodies (site.config.json messages.*) — the
   appraisal body (First name / Last name / Mobile number) feeds Brenen's
   manual VinCue flow.
2. "Save to contacts" BREAKS the FB webview. The hero link is
   <a href="brenen.vcf" download>. Tapping it in the FB webview navigates
   away from the page to a "Page not found / It may have been deleted or the
   link isn't working" dead end (screenshot in Muse's chat, 2026-11-17
   12:49 PM) and strands the visitor there. A fix must never strand a
   visitor: inside in-app browsers the control should work, degrade to
   something useful, or not be offered — while still working in real
   browsers (Safari/Chrome), where the .vcf download is the point.

Verified-good state (do not regress): commit 7160e39 live; external links
same-window (0 target=_blank in built pages); car.html specs render real
dt/dd text; scroll-margin-top 84px on [id]; build --check passes;
tests/test_site.py 35 passed; independent click-test passed socials,
search, filters, pagination, car-page nav + back link, booking slots,
Follow sheet open/close/reopen. First-pass marathon click-test that showed
near-total failure was the test browser degrading, NOT the site — the code
was read in full (app/ui/lib/car.js, site.css) and has no freeze/overlay.
Constraints: static GitHub Pages (no backend), NO-PI by design, never
hand-edit built pages, bump asset ?v= on any css/js change, tests gate.

## 2026-11-17 — Link audit fixes: same-window external links, car-page specs, anchor offset
Brenen reported the page "super broken" from his phone (inside Facebook's
in-app browser): Value my car did nothing, the Facebook link did nothing, and
the TikTok link trapped him on Facebook's leave-warning page. Full audit
(live click-test + code read of app/car/ui/lib + CSS) found:
- Every external link was emitted with target="_blank" (build_site.py ext(),
  the two Maps links in src/index.template.html, and the Carfax link in
  assets/js/ui.js). In-app browsers (Facebook/Instagram webviews) handle
  new-window links badly: dead taps and warning-page traps. All external
  links are now same-window; tests/test_site.py now asserts target != _blank
  instead of requiring _blank. Asset versions bumped (css v6, js v5) so
  returning visitors get the fixed files.
- Real bug on car.html: the specs list rendered "[object HTMLElement],..."
  because car.js passed rows.map(...) (array of arrays) into h(), which
  flattens only one level. Now rows.flatMap(...); specs render as dt/dd pairs.
- Anchor jumps landed with section headings hidden under the sticky header
  pill; site.css now sets scroll-margin-top: 84px on [id] elements.
Build --check passes; tests/test_site.py 35 passed. The sms: buttons keep the
"sms:NUMBER?&body=" form (lib.js: the iOS+Android compatible shape); inside
Facebook's webview, sms:/tel: hand-off is the webview's call, not the page's.

## 2026-11-16 — Cable Dahmer Difference section added to the home page
Brenen (2026-11-16): the Cable Dahmer Difference belongs on the contact page
somewhere easily seen. New "Why buy from Cable Dahmer?" section in
src/index.template.html, directly under the hero and above Inventory, listing
the store's five lines verbatim (5-Year Unlimited Mile Powertrain Warranty on
new vehicles; 14-Day exchange on select pre-owned purchases; Complimentary
Pick-Up and Delivery with service appointments; First complimentary dent
repair*; Complimentary annual Missouri State inspection) with a select-models
footnote. New .diff-list styles in assets/css/site.css; stylesheet version
bumped ?v=4 -> ?v=5 in both templates. Rebuilt, `--check` passes.

## 2026-11-13 — Agent line flipped back to 816-762-5779
Brenen (2026-11-13): the agent line is once again 816-762-5779 everywhere,
superseding 816-601-1688 (which held Nov 10-13). site.config.json updated,
pages rebuilt (`--check` passes), repo docs + tests updated to match. The
public site, vCard, and all call/text links now carry 816-762-5779.

## 2026-11-13 — Car photos still not live; inputs staged in the private repo
As of Fri Nov 13 ~8:10 AM CT, photos/ here still holds only README.md, so the
inventory on brenenprinzing.com renders with no car photos. Your sync step
has not landed yet.
Inputs are fully staged in the private contact-site-inventory repo:
photos/<STOCK>/01.jpg ... 05.jpg for all 221 cars that have galleries (Muse
verified the folder set and spot-checked byte sizes against its manifest
on Nov 12). Please run tools/sync_photos.py against that photos folder with
the repo's inventory-store.csv, then rebuild/push so the site-*.jpg files
land here.
Notes: stock GHFMJ2*O landed sanitized as GHFMJ2_O — fails the stock
pattern, skipped by design. 16 cars have no gallery anywhere — leave them
empty, do not backfill. Heads-up: the store list moved to 229 cars in the
Nov 13 daily sync (Drive copies updated); the matching GitHub CSV drop is
pending Brenen's approval, so the repo CSV may still show the prior 237
when you pull.


## 2026-11-12 — Muse now edits sources + runs build_site.py (your workflow, adopted)
You were right: Muse's hand edits to the built pages drifted from the
sources and `--check` failed. Found and fixed three drifts:
1. The `?v=2` push rebuilt `src/index.template.html` from a stale local
   copy and silently dropped the pager navs from the TEMPLATE (the built
   page kept them). Pager navs are now in the template properly.
2. The committed pages' embedded config JSON still carried the OLD
   trade message ("value on my car / Year-Make-Model") even though
   `site.config.json` has the appraisal wording — the pages had never
   been rebuilt after the config port. Rebuilt; the appraisal text now
   ships everywhere, including JS-driven links.
3. `car.html`'s Follow sheet never got TikTok/YouTube (the socials push
   only touched index.html by hand). The rebuild adds them from config.
Fix method, per your instruction: edited `src/` only, ran
`python tools/build_site.py` in a mirror, `--check` passes, and pushed
the regenerated `index.html` / `car.html` (vCard was already identical).
Going forward Muse changes `site.config.json` or `src/` and rebuilds —
no more hand edits to built pages.


## 2026-11-12 — 6 cars per page
Brenen: 6 divides evenly into the grid rows. `PAGE_SIZE` 5 → 6 in
`assets/js/app.js`; asset versions bumped to `?v=4`.


## 2026-11-12 — 5 cars per page; pager tabs are a single-line carousel
Brenen: 10 per page still felt long, and the wrapped tab rows ate space.
`PAGE_SIZE` is now 5 in `assets/js/app.js`, and `.pager` is a single
horizontally scrolling row (same pattern as the filter chips, scrollbar
hidden, buttons `flex: none`). Asset versions bumped to `?v=3`.


## 2026-11-12 — Asset URLs versioned (?v=2) to beat phone caches
Brenen's phone kept serving the pre-pagination app.js/site.css from cache.
`site.css`, `app.js` and `car.js` references in both templates and both built
pages now carry `?v=2`. Bump the number on any future CSS/JS change so
returning visitors always get the fresh files.

## 2026-11-12 — Inventory is paged: numbered tabs top and bottom
Brenen flagged the inventory rendering as one long scroll list. His standing
design (from the Muse page) is a paged grid with numbered pager tabs above
and below. Implemented in your architecture: `src/index.template.html` and
the built `index.html` gained `#inv-pager-top` / `#inv-pager-bottom` navs,
`assets/js/app.js` slices the filtered list (page resets when filters
change), and `assets/css/site.css` styles `.pager-btn` like the filter
chips (gold when current). Page size started at 10; see the newer entry
above for 5 per page + the single-line carousel.
(Entry restored by Muse — the ?v=2 push accidentally overwrote it.)

## 2026-11-12 — Socials: TikTok + YouTube (commit a50500e8)
Added TikTok (https://www.tiktok.com/@brenen.cadillackc) and YouTube
(https://www.youtube.com/@Brenen.CadillacKC) to the Follow sheet, both
social-row lists, `site.config.json` socials, and `link_allow_hosts`.
Verified live on brenenprinzing.com.

## 2026-11-12 — Value-my-car text now asks for the VinCue fields (commit 676029f0)
The Value-my-car SMS prefill no longer asks for vehicle details. It now asks:
"Hi Brenen, I'd like an appraisal on my car. / First name: / Last name: /
Mobile number:" — exactly the three fields VinCue's Text Inspection Link
needs. Brenen's flow is manual: the customer texts those, Brenen enters them
in VinCue himself, VinCue texts the customer their self-inspection link.
A fully automated version (Google Form + Sheet + 15-minute checker) was
specced and Brenen shelved it — do not build it unless he revives it.

Standing rule for this site: every contact action routes to Brenen directly.
No dealer-website links anywhere (Brenen removed them 2026-11-12 — they were
giving his leads to the store).
