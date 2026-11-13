# Notes from Muse (for Claude)

Muse pushes small, Brenen-approved updates to this repo from the Muse side.
Read this file after pulling main. Newest first.

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
