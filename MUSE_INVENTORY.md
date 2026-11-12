# Muse page inventory (spec section 0)

Source: `Contact_page_export.html`, the single-file export of Muse's muse.ai contact
page, sent by Brenen in chat on 2026-11-12. One HTML file with inline CSS and one
inline script. No images, no data files.

The export is committed at `import/muse/Contact_page_export.html` (Brenen confirmed on
2026-11-12 that the number and email on it are business lines and fine to publish).
The site never loads that file.

## Kept

| On the Muse page | Where it is now |
|---|---|
| Name, "Sales Consultant", "Cable Dahmer Cadillac" | Hero, contact card, footer |
| Eyebrow "Cable Dahmer Cadillac · Kansas City" | Top of the hero (`eyebrow`) |
| Tagline "I'm passionate about helping people find their perfect vehicle. Reach me directly below — you'll talk to me, not the main store line." | Hero (`tagline`), word for word |
| Address 1151 W 104th St, Kansas City, MO 64114 | Map card and vCard (`store.address`, `store.adr`) |
| "BP" monogram avatar | Replaced by Brenen's photo; the monogram stays as the fallback |
| Phone 816-601-1688 (text, call, copy, footer, vCard) | Same number everywhere, from `site.config.json` |
| Email address ("Prefer email?" link, footer, vCard) | Email button in the contact card, and in the vCard |
| Live status pill ("Test drives available today until 6:00 PM — text me to book yours", and the before-open and next-day versions) | Hero, same wording, same Central-time logic |
| Text button with prefilled "Hi Brenen, I'm interested in a vehicle you have listed. Can we set up a test drive?" | "Message Brenen" and "Text Brenen about a car" |
| Call button | "Call" in the contact card |
| Get Directions link (Google Maps search, same query) | "Open in Maps" and "Get directions" |
| Facebook Page link | Follow sheet and social rows (`socials`) |
| Instagram link (@brenen.cadillackc) | Follow sheet and social rows (`socials`) |
| Test drive hours: Mon, Tue, Thu, Fri, Sat 9:00 AM to 6:00 PM; Wed and Sun "No test drives"; today highlighted | Hours table, same label and wording, today highlighted |
| Note "Text or call ahead and I'll have the vehicle pulled up and ready when you arrive. Ask for Brenen Prinzing, Sales Consultant, so you're connected directly to me." | Under the hours table (`hours_note`) |
| Copy phone button | "Copy number" in the contact card |
| Save contact (vCard built in the browser) | "Save to contacts", a real `brenen.vcf` file built from the config, with the address |
| Fonts: Marcellus (headings) and Jost (text) | Same two fonts, now self-hosted in `assets/fonts/` (both SIL Open Font License) |
| Gold accent, gold divider, rounded cards, pill buttons | Same look on the spec's black-gold tokens |

## Removed or changed (R1 to R7)

| Item on the Muse page | Why | What replaced it |
|---|---|---|
| Google Fonts: two `preconnect` links and the stylesheet from `fonts.googleapis.com` / `fonts.gstatic.com` | External font and third-party request (R1) | The same fonts served from this site |
| "Message on Messenger" button (`m.me` link) | R1: every contact action must be `sms:`, `tel:` or `mailto:`. Messenger sends the shopper to a third party | Removed. The Facebook Page link stays as a social link |
| Copy email button | Not needed next to the Email button | Email button |
| Inline `<script>` and inline `style` attribute | The site's Content-Security-Policy allows only its own files | Logic moved to `assets/js/`, styles to `assets/css/site.css` |
| Contact details typed into the HTML | R7 | All in `site.config.json` |
| Light theme (`prefers-color-scheme` switch) | Spec section 3: black-gold theme | Dark only |
| Dealer-site inventory link | The export has none | The site's own Inventory section |

Not found on the Muse page, so nothing to strip: forms, trackers, analytics, cookies,
pixels, embeds or iframes.

## Answered by Brenen on 2026-11-12

1. Phone: the agent line is now the Muse number, 816-601-1688. Used for calls and texts.
2. Email: show it.
3. Messenger: stays removed.

## Still open

- Banner: Brenen asked for the Facebook Page banner. This build environment cannot
  reach facebook.com, so the image has to be sent as a file. `banner` stays empty.
