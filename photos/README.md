# Car photos

One folder per stock number. Two kinds of photo live here:

| File name | Where it comes from |
|---|---|
| `site-01.jpg`, `site-02.jpg`, ... | The store's listing photos. Muse pulls them once per car into the private inventory repo; `tools/sync_photos.py` resizes them, strips all EXIF data and copies them here. Never edit these by hand. |
| Anything else, e.g. `01.jpg` | Brenen's own shots. They show first in the carousel. |

Decision (Brenen, Nov 12, 2026): rule R5 has one exception. Public-facing inventory
may use the store's own public listing photos of each car. R5 still applies to
everything else. Only listing photos of cars in the inventory belong in this folder
under the `site-` name.

For your own photos: `.jpg` or `.webp`, longest side 1600px or less, location data
removed (the converter refuses to build if a photo still has GPS in its EXIF), named
in the order you want them shown.

When a car leaves the inventory its whole folder is removed, own photos included.
`.site-photos.json` is the sync tool's record of what it has already copied.
