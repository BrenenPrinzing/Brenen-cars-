# Notes from Muse (for Claude)

Muse pushes small, Brenen-approved updates to this repo from the Muse side.
Read this file after pulling main. Newest first.

## 2026-11-17 (Claude, later) — Save to contacts: link removed outright in in-app browsers
Brenen's 1:16 PM retest (4 minutes after PR #7 went live at 1:12) still hit
"Page not found" on Save to contacts. Likely cause: GitHub Pages lets a browser
reuse the page for up to 10 minutes, so the Facebook browser may still have had
the old page. Unconfirmed, so the fix no longer relies on a click handler beating
the browser (or script Meta injects into its browser) to the link:
- In an in-app browser, wireInApp() now strips href and download from the .vcf
  link as the page loads. There is nothing left to navigate to. The control
  stays as a button that opens the "Save Brenen's number" panel.
- Its label changes to "Save my number" in in-app browsers only. That is the
  visible check: if the hero still says "Save to contacts" inside Facebook, the
  phone is showing the old page or the script did not run.
- The sms/tel/mailto fallback listener now runs in the capture phase. It still
  never blocks the link.
- js v8. Real browsers are unchanged (Playwright, Safari user agent: the .vcf
  still downloads, no panel).
Retest: close the Facebook browser tab, wait 10 minutes after the deploy, then
open brenenprinzing.com again from Facebook. The hero button should read "Save my
number". Tap it: the panel appears and the page stays put.

## 2026-11-17 (Claude) — In-app browser fallback for sms:/tel:/mailto: and Save to contacts
Fixes the two defects logged below. Only Facebook and Instagram in-app browsers
change (detected by user agent: FBAN / FBAV / FB_IAB / FBIOS / FB4A / Instagram;
Meta's chat app carries the same FB tokens). Safari, Chrome and Android browsers
behave exactly as before: no interception, the .vcf still downloads.
- New pure helpers in assets/js/lib.js: inAppBrowser(ua), contactFromHref(href),
  displayPhone(). New wireInApp(config) + helpPanel() in assets/js/ui.js, called
  from app.js and car.js. Panel styles at the end of site.css.
- Save to contacts, in-app: the tap no longer navigates (that was the "Page not
  found" strand). It opens a panel: "Save Brenen's number", the number, Copy
  number, Close, and how to open the page in the phone's browser (tap ••• then
  Open in external browser) to get the contact card itself.
- sms:/tel:/mailto:, in-app: the link still goes out exactly as written (same
  "?&body=" shape, same bodies; site.config.json messages.* untouched). If the
  page is still on screen 1.5 s later (Messages/Phone/Mail never took over:
  no visibilitychange-hidden, pagehide or blur), a panel shows the number and the
  EXACT prefilled message (read back from the link itself) with Copy message and
  Copy number buttons. If the hand-off works, the page goes to the background and
  no panel appears. If clipboard access is refused, the button selects the text
  for press-and-hold copy. Covers every contact link on both pages by event
  delegation (hero, Tools cards, car cards, booking CTA, Talk to Brenen, car.html).
- Why not a different sms: shape or JS location assignment: neither can be
  verified off-device, and either could break the working Safari/Android path.
  The watchdog guarantees a useful result whichever way the webview behaves.
- No storage, no network, no new outside resources; copy goes only to the
  visitor's own clipboard. Asset versions: css v7, js v7.
- Also treated as in-app: any iPhone/iPad web view whose user agent lacks the
  "Safari/" token (TikTok, LinkedIn and similar), so the fix does not hang on
  Meta's tags alone. Safari, Chrome, Firefox and Edge on iOS all carry it.
- Brenen's 1:08 PM retest still stranded on Save to contacts because PR #7 was
  not merged yet: main (and the live site) still served the old page. Retest
  only after the merge and the Pages deploy finish.
- Tests: tests/js/lib.test.mjs gained 3 tests for the new helpers (no existing
  test changed). build --check passes; pytest 165 passed (test_site.py 35);
  headless_check.mjs passes. A Playwright run with FB-iOS and Instagram user
  agents confirmed: Value my car -> panel with the byte-exact appraisal body,
  Copy message puts the exact body on the clipboard; Save to contacts -> no
  navigation, panel with the number; a simulated hand-off (blur) -> no panel;
  Safari UA -> .vcf downloads and no panel ever.
Brenen's iPhone retest (Facebook app -> open brenenprinzing.com):
1. Tap "Value my car". Either Messages opens with the appraisal text (the
   webview hand-off works), or within ~2 seconds a "Text Brenen" panel slides up
   with the number and the First name / Last name / Mobile number message, plus
   Copy message / Copy number. Never nothing.
2. Tap "Save to contacts". You stay on the page; a "Save Brenen's number" panel
   shows the number with Copy number. No "Page not found".
3. Tap Close; repeat step 1 from a car card's "Text me about this car" and from
   the Call button in Talk to Brenen.
4. Open the same page in Safari: Save to contacts still opens the contact card;
   Value my car opens Messages; no panel appears.

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
