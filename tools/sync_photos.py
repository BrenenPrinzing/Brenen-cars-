#!/usr/bin/env python3
"""Copy the dealer-site car photos Muse pulled into the site's photos/ folder.

Usage:
    python tools/sync_photos.py <muse photos dir> --inventory <inventory-store.csv>
        [--dest photos] [--max-per-car 5] [--max-px 960]

Muse's layout (private inventory repo):   photos/<STOCK>/01.jpg, 02.jpg, ...
Written here (public site repo):          photos/<STOCK>/site-01.jpg, site-02.jpg, ...

For every car the converter would keep, up to --max-per-car photos are resized to
--max-px on the longest side and re-encoded as JPEG, which drops all EXIF data
(including GPS). A photo is only reprocessed when Muse's copy changes, so each car
is done once. Folders for cars no longer listed are removed.

Files without the `site-` prefix are Brenen's own shots: they are never touched while
the car is listed, and they sort first in the carousel.

Brenen's Nov 12, 2026 exception to R5 covers only this: the store's public listing
photos of cars in the inventory. R5 still applies to every other image (see README).
Needs Pillow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_inventory as bi  # noqa: E402

PREFIX = "site-"
MANIFEST = ".site-photos.json"
SOURCE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SOURCE_BYTES = 25_000_000


def kept_stocks(inventory_csv: Path, exclude: Path | None, dc_export: Path | None = None) -> set[str]:
    rows = bi.read_export(inventory_csv)
    if dc_export:
        rows, _ = bi.merge_dc(rows, bi.read_export(dc_export))   # held cars get no photos
        bi.check_held(rows)
    kept, _ = bi.filter_rows(rows, bi.load_exclude(exclude))
    return {r["stock"] for r in kept}


def convert(src: Path, dest: Path, max_px: int, quality: int) -> None:
    from PIL import Image, ImageOps
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((max_px, max_px), Image.LANCZOS)
        clean = Image.frombytes("RGB", im.size, im.tobytes())   # no metadata carried over
    dest.parent.mkdir(parents=True, exist_ok=True)
    clean.save(dest, "JPEG", quality=quality, optimize=True, progressive=True)


def sync(source: Path, dest: Path, stocks: set[str], max_per_car: int = 5, max_px: int = 960,
         quality: int = 74) -> dict:
    manifest_path = dest / MANIFEST
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    new, report = {}, {"written": 0, "reused": 0, "removed": 0, "skipped": [], "cars": 0}

    for stock in sorted(stocks):
        folder = source / stock
        if not bi.STOCK_OK.match(stock) or not folder.is_dir():
            continue
        files = sorted((p for p in folder.iterdir()
                        if p.is_file() and not p.is_symlink() and p.suffix.lower() in SOURCE_EXT),
                       key=lambda p: p.name.lower())[:max_per_car]
        done = 0
        for src in files:
            if src.stat().st_size > MAX_SOURCE_BYTES:
                report["skipped"].append(f"{stock}/{src.name}: too large")
                continue
            digest = hashlib.sha1(src.read_bytes()).hexdigest() + f":{max_px}:{quality}"
            rel = f"{stock}/{PREFIX}{done + 1:02d}.jpg"
            out = dest / rel
            if old.get(rel) == digest and out.exists():
                report["reused"] += 1
            else:
                try:
                    convert(src, out, max_px, quality)
                except Exception as e:   # unreadable or not really an image
                    report["skipped"].append(f"{stock}/{src.name}: {type(e).__name__}")
                    continue
                report["written"] += 1
            new[rel] = digest
            done += 1
        report["cars"] += 1 if done else 0

    # Remove site photos that are no longer wanted, and whole folders of unlisted cars.
    if dest.is_dir():
        for folder in sorted(p for p in dest.iterdir() if p.is_dir()):
            if folder.name not in stocks:
                shutil.rmtree(folder)
                report["removed"] += 1
                continue
            for f in folder.glob(f"{PREFIX}*.jpg"):
                if f"{folder.name}/{f.name}" not in new:
                    f.unlink()
            if not any(folder.iterdir()):
                folder.rmdir()
    dest.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(new, indent=0, sort_keys=True) + "\n")
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("source", type=Path, help="Muse's photos folder (photos/<STOCK>/NN.jpg)")
    ap.add_argument("--inventory", type=Path, required=True, help="Muse's inventory-store.csv")
    ap.add_argument("--dest", type=Path, default=bi.ROOT / "photos")
    ap.add_argument("--exclude", type=Path, default=bi.ROOT / "data" / "exclude.txt")
    ap.add_argument("--dc-export", type=Path, help="DriveCentric export: cars not in it yet are "
                    "held, so their photos are not copied")
    ap.add_argument("--max-per-car", type=int, default=5)
    ap.add_argument("--max-px", type=int, default=960)
    a = ap.parse_args(argv)
    if not a.source.is_dir():
        print(f"No photos folder at {a.source}. Nothing to sync.")
        return 0
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("sync_photos.py needs Pillow: pip install pillow", file=sys.stderr)
        return 1
    try:
        stocks = kept_stocks(a.inventory, a.exclude, a.dc_export)
    except bi.BuildError as e:
        print(f"PHOTO SYNC STOPPED: {e}", file=sys.stderr)
        return 1
    r = sync(a.source, a.dest, stocks, a.max_per_car, a.max_px)
    print(f"Photos: {r['cars']} cars have photos. {r['written']} new or changed, "
          f"{r['reused']} reused, {r['removed']} folders removed for cars no longer listed.")
    for s in r["skipped"]:
        print(f"SKIPPED {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
