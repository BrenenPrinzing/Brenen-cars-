# Muse page inventory (spec section 0)

Status on 2026-11-12: **no Muse export received.**

Where it was looked for:
- `import/muse/` in this repo: did not exist (the repo held only `SPEC.md`).
- Google Drive: no folder or file named "Contact Site - Muse export", and nothing
  matching "muse export" or a recent HTML export.

Because there was no page to inventory, nothing from muse.ai is in this build:

| What the Muse page has | Carried over | Notes |
|---|---|---|
| Text (name, title, tagline, bio) | Not available | Name, title and store come from SPEC.md. Tagline and bio are empty. |
| Links (label + destination) | Not available | Socials are empty, so the Follow button and social rows are hidden. |
| Images (headshot, banner) | Not available | Placeholder silhouette. No banner. |
| Colors and look | Not available | Black-gold tokens from SPEC.md section 5. |
| Forms, trackers, analytics, cookies, embeds, external scripts or fonts | Nothing to strip | Removal list is empty. R1 is enforced by tests either way. |
| Dealer-site inventory link | Not carried | The site's own Inventory section takes its place. |

## When the export arrives

1. Muse puts the page source in `import/muse/` (or sends the list of text, links,
   images and colors).
2. Fill this table in for real: every text block, link, image and color, and every
   form, tracker, cookie, embed and external script or font that gets stripped.
3. Content goes into `site.config.json` (tagline, bio, socials, extra_links,
   headshot, banner). Colors go into the tokens at the top of `assets/css/site.css`.
4. Run `python tools/build_site.py` and `python -m pytest`.

Nothing in the page structure needs to change for this: sections 3.1 to 3.8 are
already built to the spec.
