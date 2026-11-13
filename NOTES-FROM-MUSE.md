# Notes from Muse (for Claude)

Muse pushes small, Brenen-approved updates to this repo from the Muse side.
Read this file after pulling main. Newest first.

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
