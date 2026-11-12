#!/usr/bin/env python3
"""Turn a DriveCentric inventory export into the public inventory/inventory.json.

Usage:
    python tools/build_inventory.py data/raw/<export.csv|.xlsx>
        [--out inventory/inventory.json] [--exclude data/exclude.txt]
        [--photos photos] [--config site.config.json]
        [--prices data/raw/price_checks.json] [--date YYYY-MM-DD] [--now ISO]

Only whitelisted fields reach the JSON. Msrp, Leads, Last lead, Deals and Age are
never written. A price is written only when the export's Pricing equals the dealer
site's listed price to the dollar and that check is under 24 hours old (see
tools/check_dealer_prices.py). No payments, ever.

Standard library only. Same input gives byte-identical output.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import struct
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent

# --- Rules copied from marketplace_picker.py (keep in step with it) -----------------
# Out-of-area stores, checked against all 815 group used cars (Oct 24, 2026: 0 errors):
#   Lawrence Kia: L, LT, LX, DLP, DLX   Topeka: F, FT, FX, FP, DF, DFT, DFX, KF
#   Independence (Chevy + Buick GMC): all-digit (106671A), BP, BT, BX, DX,
#   B####/DB#### (4 digits; KC Cadillac uses 5), T##### (5; KC Chevy uses 4),
#   X##### (5; KC Chevy uses 6), P1#### (KC uses P6####)
FAR_STORE = re.compile(r"^(L|DL|F|DF|KF|\d|BP|BT|BX|DX|B\d{4}(?!\d)|DB\d{4}(?!\d)"
                       r"|T\d{5}(?!\d)|X\d{5}(?!\d)|P1\d{4}(?!\d))")

TRUCKS = {"sierra", "silverado", "ram", "f-150", "f-250", "f-350", "tacoma",
          "tundra", "colorado", "canyon", "ranger", "frontier", "gladiator", "titan"}
SEDANS = {"ct4", "ct5", "ct6", "cts", "ats", "camry", "accord", "civic", "corolla",
          "altima", "malibu", "sentra", "elantra", "sonata", "3", "5", "c-class",
          "e-class", "is", "es", "giulia", "s60", "a4", "a6", "g70", "g80"}
# ------------------------------------------------------------------------------------

# Added for the site: electric models get their own body chip.
EV_MODELS = ("lyriq", "optiq", "vistiq", "escalade iq", "escalade iql",
             "f-150 lightning", "ix")

SOLD_YES = {"yes", "y", "true", "1", "sold", "delivered"}
STOCK_OK = re.compile(r"^[A-Z]{1,3}\d{4,6}[A-Z]?$")

CONDITION_ORDER = {"New": 0, "Demo": 1, "Pre-owned": 2}
NEW_ARRIVAL_DAYS = 7
PRICE_MAX_AGE = dt.timedelta(hours=24)
# Cars the dealer site no longer lists are dropped, but only when the check clearly
# worked: at least this share of the checked cars must have been found with a price.
MIN_FOUND_SHARE = 0.5
PHOTO_MAX_PX = 1600
PHOTO_EXT = {".jpg", ".jpeg", ".webp"}

# The only keys allowed in the public JSON. Anything else is a hard error.
ALLOWED_TOP_KEYS = frozenset({"updated", "source_rows", "kept", "prices_checked_at", "cars"})
ALLOWED_CAR_KEYS = frozenset({
    "stock", "year", "make", "model", "trim", "condition", "body", "miles",
    "ext_color", "int_color", "vin", "photos", "new_arrival", "price", "carfax_url",
})
BANNED_KEYS = frozenset({"msrp", "payment", "payments", "leads", "last_lead", "lastlead",
                         "deals", "age", "pricing"})


class BuildError(Exception):
    """A problem that must stop the build."""


# --- Reading the export -------------------------------------------------------------

def norm_header(name) -> str:
    """Case- and space-insensitive header key: 'Stock Number' -> 'stocknumber'."""
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def read_csv_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    return _rows_to_dicts(rows)


_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _col_index(ref: str) -> int:
    n = 0
    for ch in ref:
        if ch.isalpha():
            n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def read_xlsx_rows(path: Path) -> list[dict]:
    """Minimal .xlsx reader (first worksheet), so pandas/openpyxl stay optional."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", _NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))
        sheets = sorted(n for n in z.namelist()
                        if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        if not sheets:
            raise BuildError(f"{path.name}: no worksheet found")
        root = ET.fromstring(z.read(sheets[0]))
    rows = []
    for row in root.iter(f"{{{_NS['m']}}}row"):
        cells = {}
        for c in row.findall("m:c", _NS):
            idx = _col_index(c.get("r", "A"))
            kind = c.get("t")
            v = c.find("m:v", _NS)
            if kind == "s" and v is not None:
                val = shared[int(v.text)]
            elif kind == "inlineStr":
                val = "".join(t.text or "" for t in c.iter(f"{{{_NS['m']}}}t"))
            else:
                val = v.text if v is not None else ""
            cells[idx] = val or ""
        if cells:
            rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
    return _rows_to_dicts(rows)


def _rows_to_dicts(rows: list[list]) -> list[dict]:
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        return []
    headers = [norm_header(h) for h in rows[0]]
    out = []
    for r in rows[1:]:
        out.append({h: str(r[i]).strip() if i < len(r) else ""
                    for i, h in enumerate(headers) if h})
    return out


def read_export(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return read_csv_rows(path)
    if suffix == ".xlsx":
        return read_xlsx_rows(path)
    raise BuildError(f"Unsupported export type '{suffix}'. Use .csv or .xlsx.")


# --- Row rules ----------------------------------------------------------------------

def to_int(value) -> int:
    """'$52,800.00' -> 52800. Blank or junk -> 0."""
    s = re.sub(r"[^0-9.\-]", "", str(value or ""))
    try:
        return int(round(float(s)))
    except ValueError:
        return 0


def condition_for(stock: str) -> str:
    """New Cadillacs are C#####; demos (titled new) are DC#####; the rest pre-owned."""
    if re.fullmatch(r"C\d+", stock):
        return "New"
    if re.fullmatch(r"DC\d+", stock):
        return "Demo"
    return "Pre-owned"


def body_for(model: str) -> str:
    m = " ".join(model.lower().split())
    for ev in EV_MODELS:
        if m == ev or m.startswith(ev + " "):
            return "EV"
    first = m.split()[0] if m else ""
    if first in TRUCKS:
        return "Truck"
    if first in SEDANS:
        return "Sedan"
    return "SUV"


def split_vehicle(vehicle: str) -> tuple[int, str, str]:
    parts = str(vehicle).split(None, 2)
    year = int(parts[0]) if parts and parts[0].isdigit() else 0
    make = parts[1] if len(parts) > 1 else ""
    model = parts[2] if len(parts) > 2 else ""
    return year, make, model


def round_miles(miles: int) -> int:
    return int((miles + 50) // 100 * 100)


def load_exclude(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.split("#", 1)[0].strip().upper()
        if s:
            out.add(s)
    return out


def filter_rows(rows: list[dict], exclude: set[str]) -> tuple[list[dict], dict]:
    """Apply the keep rules. Returns (kept rows with 'stock' set, drop counts)."""
    dropped = {"sold": 0, "delivered": 0, "bad_stock": 0, "far_store": 0, "excluded": 0, "duplicate": 0}
    kept, seen = [], set()
    for row in rows:
        stock = row.get("stocknumber", "").strip().upper()
        if row.get("sold", "").strip().lower() in SOLD_YES:
            dropped["sold"] += 1
        elif row.get("delivered", "").strip().lower() in SOLD_YES:
            dropped["delivered"] += 1
        elif not STOCK_OK.match(stock):
            dropped["bad_stock"] += 1
        elif FAR_STORE.match(stock):
            dropped["far_store"] += 1
        elif stock in exclude:
            dropped["excluded"] += 1
        elif stock in seen:
            dropped["duplicate"] += 1
        else:
            seen.add(stock)
            kept.append(dict(row, stock=stock))
    return kept, dropped


# --- Photos -------------------------------------------------------------------------

def _tiff_has_gps(tiff: bytes) -> bool:
    if len(tiff) < 8 or tiff[:2] not in (b"II", b"MM"):
        return False
    e = "<" if tiff[:2] == b"II" else ">"
    (offset,) = struct.unpack(e + "I", tiff[4:8])
    if offset + 2 > len(tiff):
        return False
    (count,) = struct.unpack(e + "H", tiff[offset:offset + 2])
    for i in range(count):
        entry = tiff[offset + 2 + 12 * i: offset + 14 + 12 * i]
        if len(entry) < 12:
            break
        if struct.unpack(e + "H", entry[:2])[0] == 0x8825:  # GPSInfo IFD pointer
            return True
    return False


def photo_info(path: Path) -> dict:
    """Return {'gps': bool, 'width': int, 'height': int} from a JPEG or WebP file."""
    data = path.read_bytes()
    info = {"gps": False, "width": 0, "height": 0}
    if data[:2] == b"\xff\xd8":  # JPEG
        i = 2
        while i + 4 <= len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            if marker in (0xD9, 0xDA):
                break
            (size,) = struct.unpack(">H", data[i + 2:i + 4])
            seg = data[i + 4:i + 2 + size]
            if marker == 0xE1 and seg[:6] == b"Exif\x00\x00":
                info["gps"] = info["gps"] or _tiff_has_gps(seg[6:])
            if marker in (0xC0, 0xC1, 0xC2) and len(seg) >= 5:
                info["height"], info["width"] = struct.unpack(">HH", seg[1:5])
            i += 2 + size
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        i = 12
        while i + 8 <= len(data):
            tag = data[i:i + 4]
            (size,) = struct.unpack("<I", data[i + 4:i + 8])
            body = data[i + 8:i + 8 + size]
            if tag == b"EXIF":
                tiff = body[6:] if body[:6] == b"Exif\x00\x00" else body
                info["gps"] = info["gps"] or _tiff_has_gps(tiff)
            elif tag == b"VP8X" and len(body) >= 10:
                info["width"] = int.from_bytes(body[4:7], "little") + 1
                info["height"] = int.from_bytes(body[7:10], "little") + 1
            elif tag == b"VP8 " and len(body) >= 10 and not info["width"]:
                w, h = struct.unpack("<HH", body[6:10])
                info["width"], info["height"] = w & 0x3FFF, h & 0x3FFF
            elif tag == b"VP8L" and len(body) >= 5 and not info["width"]:
                bits = int.from_bytes(body[1:5], "little")
                info["width"] = (bits & 0x3FFF) + 1
                info["height"] = ((bits >> 14) & 0x3FFF) + 1
            i += 8 + size + (size & 1)
    return info


def list_photos(photos_dir: Path, stock: str, warnings: list[str]) -> list[str]:
    folder = photos_dir / stock
    if not folder.is_dir():
        return []
    out = []
    for p in sorted(folder.iterdir(), key=lambda x: x.name.lower()):
        if p.suffix.lower() not in PHOTO_EXT or not p.is_file():
            continue
        info = photo_info(p)
        if info["gps"]:
            raise BuildError(
                f"{p}: photo has GPS location in its EXIF data. Strip the EXIF "
                f"(export without location) and run again. Nothing was written.")
        if max(info["width"], info["height"]) > PHOTO_MAX_PX:
            warnings.append(f"{p}: {info['width']}x{info['height']} is over "
                            f"{PHOTO_MAX_PX}px. Resize it to keep the page fast.")
        out.append(f"photos/{stock}/{p.name}")
    return out


# --- Prices -------------------------------------------------------------------------

def parse_time(value: str) -> dt.datetime:
    t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def load_price_checks(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k).upper(): v for k, v in data.get("checks", {}).items()}


def check_fresh(check: dict | None, now: dt.datetime) -> bool:
    try:
        age = now - parse_time(check["checked_at"])
    except (KeyError, TypeError, ValueError):
        return False
    return dt.timedelta(minutes=-5) <= age < PRICE_MAX_AGE


def gone_from_dealer_site(kept: list[dict], price_checks: dict, now: dt.datetime):
    """Stocks to drop because the dealer site no longer lists them.

    Returns (stocks, warning). Nothing is dropped unless the same fresh check run found
    most of the other cars, so a broken page reader can never empty the list.
    """
    fresh = {r["stock"]: price_checks[r["stock"]] for r in kept
             if check_fresh(price_checks.get(r["stock"]), now)}
    missing = {s for s, c in fresh.items() if c.get("status") == "not_found"}
    if not missing:
        return set(), None
    found = sum(1 for c in fresh.values() if c.get("status") == "ok")
    if found / len(fresh) < MIN_FOUND_SHARE:
        return set(), (f"{len(missing)} of {len(fresh)} checked cars were not found on the dealer "
                       f"site and only {found} were. That looks like a problem reading the site, "
                       f"so no cars were dropped for it. Check a few by hand.")
    return missing, None


def admin_fee(config: dict | None) -> int:
    return to_int(((config or {}).get("dealer_site") or {}).get("admin_fee"))


def verified_price(export_price: int, check: dict | None, now: dt.datetime, fee: int = 0):
    """Return (price or None, reason). Publish only on an exact, fresh match.

    The dealer site lists the price with the admin fee; DriveCentric holds it without.
    A match is: DriveCentric price + fee == site price, to the dollar. The site price
    (fee included) is what gets published.
    """
    if not check:
        return None, "no dealer-site check"
    if check.get("status") != "ok":
        return None, f"check {check.get('status', 'failed')}"
    listed = check.get("price")
    if not isinstance(listed, int) or listed <= 0:
        return None, "no price on dealer site"
    if export_price <= 0:
        return None, "no DriveCentric price to compare"
    try:
        age = now - parse_time(check["checked_at"])
    except (KeyError, ValueError):
        return None, "check has no time"
    if age >= PRICE_MAX_AGE or age < dt.timedelta(minutes=-5):
        return None, "check is over 24 hours old"
    if listed != export_price + fee:
        plus = f" + ${fee:,} fee" if fee else ""
        return None, f"mismatch (DriveCentric ${export_price:,}{plus} vs site ${listed:,})"
    return listed, "match"


DC_FIELDS = ("pricing", "age", "deals", "sold", "delivered")


def merge_dc(site_rows: list[dict], dc_rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Add DriveCentric's price, age, deal count and sold flags to Muse's site rows.

    Matched by stock number. Returns (rows, stocks that are on the site list but not in
    the DriveCentric file). Unmatched cars stay listed, with no price.
    """
    dc = {r.get("stocknumber", "").strip().upper(): r for r in dc_rows}
    out, unmatched = [], []
    for row in site_rows:
        stock = row.get("stocknumber", "").strip().upper()
        match = dc.get(stock)
        if match is None:
            unmatched.append(stock)
            out.append(row)
        else:
            out.append({**row, **{k: match[k] for k in DC_FIELDS if k in match}})
    return out, unmatched


def site_check(row: dict, site_checked_at: str | None) -> dict | None:
    """Muse's daily site list carries the dealer site's own price in a `price` column.

    That row is the dealer-site check. The time comes from a `pulled_at` / `checked_at`
    column or from --site-checked-at; without a time the price stays hidden.
    """
    if "price" not in row:
        return None
    when = row.get("pulledat", "").strip() or row.get("checkedat", "").strip() or site_checked_at
    price = to_int(row.get("price"))
    check = {"status": "ok" if price > 0 else "no_price"}
    if price > 0:
        check["price"] = price
    if when:
        check["checked_at"] = when
    return check


def file_condition(row: dict) -> str | None:
    text = row.get("condition", "").strip().lower()
    if not text:
        return None
    return "New" if text == "new" else "Pre-owned"


def disclaimer_set(config: dict) -> bool:
    return bool(str(config.get("price_disclaimer") or "").strip())


# --- Build --------------------------------------------------------------------------

def build(rows: list[dict], *, exclude: set[str] = frozenset(), photos_dir: Path | None = None,
          price_checks: dict | None = None, config: dict | None = None,
          date: str | None = None, now: dt.datetime | None = None,
          site_checked_at: str | None = None) -> tuple[dict, dict]:
    """Return (inventory dict, report dict). Raises BuildError on any hard stop."""
    now = now or dt.datetime.now(dt.timezone.utc)
    price_checks = price_checks or {}
    warnings: list[str] = []
    kept, dropped = filter_rows(rows, set(exclude))
    cars, review, hidden_prices, check_times = [], [], [], []
    fee = admin_fee(config)
    gone, gone_warning = gone_from_dealer_site(kept, price_checks, now)
    if gone_warning:
        warnings.append(gone_warning)
    dropped["not_on_dealer_site"] = len(gone)
    kept = [r for r in kept if r["stock"] not in gone]

    for row in kept:
        stock = row["stock"]
        if row.get("vehicle", "").strip():
            year, make, model = split_vehicle(row["vehicle"])
        else:  # Muse's site list has the three as separate columns
            year, make, model = to_int(row.get("year")), row.get("make", "").strip(), row.get("model", "").strip()
        condition = condition_for(stock)
        car = {
            "stock": stock, "year": year, "make": make, "model": model,
            "trim": row.get("trim", "").strip(),
            "condition": condition,
            "body": row.get("body", "").strip() or body_for(model),
            "photos": list_photos(photos_dir, stock, warnings) if photos_dir else [],
        }
        miles = to_int(row.get("mileage"))
        if condition != "New" and miles > 0:
            car["miles"] = round_miles(miles)
        for key, col in (("ext_color", "exteriorcolor"), ("int_color", "interiorcolor"),
                         ("vin", "vin")):
            if row.get(col, "").strip():
                car[key] = row[col].strip()
        age_text = row.get("age", "").strip()
        if age_text and to_int(age_text) <= NEW_ARRIVAL_DAYS:
            car["new_arrival"] = True

        check = price_checks.get(stock) or site_check(row, site_checked_at)
        dc_price = to_int(row.get("pricing") or row.get("dcprice"))
        price, reason = verified_price(dc_price, check, now, fee)
        told = file_condition(row)
        if told and told != ("Pre-owned" if condition == "Pre-owned" else "New"):
            warnings.append(f"{stock}: stock number says {condition} but the file says "
                            f"{row.get('condition', '').strip()}. Shown as {condition}.")
        if price:
            car["price"] = price
            check_times.append(parse_time(check["checked_at"]))
        elif check:
            hidden_prices.append((stock, reason))
        carfax = (check or {}).get("carfax_url")
        if carfax and (check or {}).get("status") == "ok" and is_carfax_url(carfax):
            car["carfax_url"] = carfax

        if to_int(row.get("deals")) > 0:
            review.append((stock, " ".join(str(x) for x in (year, make, model) if x),
                           to_int(row.get("deals"))))
        cars.append(car)

    cars.sort(key=lambda c: (CONDITION_ORDER[c["condition"]], c["make"].lower(),
                             c["model"].lower(), -c["year"], c["stock"]))
    inventory = {
        "updated": date or now.astimezone(dt.timezone.utc).date().isoformat(),
        "source_rows": len(rows),
        "kept": len(cars),
        "cars": cars,
    }
    if check_times:
        inventory["prices_checked_at"] = (min(check_times).astimezone(dt.timezone.utc)
                                          .strftime("%Y-%m-%dT%H:%M:%SZ"))
        if not disclaimer_set(config or {}):
            raise BuildError(
                "Prices would be published but price_disclaimer in site.config.json is "
                "empty. Paste the dealer site's fine print there word for word, or run "
                "without --prices. Nothing was written.")
    validate(inventory)
    report = {"dropped": dropped, "review": review, "hidden_prices": hidden_prices,
              "gone": sorted(gone),
              "warnings": warnings,
              "priced": sum(1 for c in cars if "price" in c)}
    return inventory, report


def is_carfax_url(url: str) -> bool:
    return bool(re.match(r"^https://([a-z0-9-]+\.)*carfax\.com/", str(url)))


def validate(inventory: dict) -> None:
    """Hard error on any key outside the whitelist (R3, R6)."""
    extra = set(inventory) - ALLOWED_TOP_KEYS
    if extra:
        raise BuildError(f"inventory.json has keys that are not allowed: {sorted(extra)}")
    for car in inventory.get("cars", []):
        extra = set(car) - ALLOWED_CAR_KEYS
        if extra:
            raise BuildError(f"Car {car.get('stock')} has keys that are not allowed: "
                             f"{sorted(extra)}")
        if "price" in car and (not isinstance(car["price"], int) or car["price"] <= 0):
            raise BuildError(f"Car {car.get('stock')} has a bad price")


def dumps(inventory: dict) -> str:
    return json.dumps(inventory, indent=1, ensure_ascii=False) + "\n"


def print_report(inventory: dict, report: dict, out=None) -> None:
    out = out or sys.stdout
    d = report["dropped"]
    print(f"Read {inventory['source_rows']} rows, kept {inventory['kept']}.", file=out)
    print(f"Dropped: {d['sold']} sold, {d['delivered']} delivered, {d['far_store']} Lawrence/Topeka/Independence, "
          f"{d['bad_stock']} in-transit or odd stock codes, {d['excluded']} on the hold "
          f"list, {d['duplicate']} duplicates, {d.get('not_on_dealer_site', 0)} no longer on the "
          f"dealer site.", file=out)
    if report.get("gone"):
        print("No longer on the dealer site (dropped): " + ", ".join(report["gone"]), file=out)
    print(f"Prices shown: {report['priced']} of {inventory['kept']} "
          f"(the rest say \"Text me for price\").", file=out)
    if report["hidden_prices"]:
        print("\nPrices hidden:", file=out)
        for stock, reason in report["hidden_prices"]:
            print(f"  {stock}: {reason}", file=out)
    if report["review"]:
        print("\nREVIEW: these kept cars have a deal on them. If another rep's deal is "
              "in proposal, add the stock # to data/exclude.txt and run again:", file=out)
        for stock, vehicle, deals in report["review"]:
            print(f"  {stock}  {vehicle}  ({deals} deal{'s' if deals != 1 else ''})", file=out)
    for w in report["warnings"]:
        print(f"WARNING: {w}", file=out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("export", type=Path,
                    help="DriveCentric export or Muse's inventory-store file (.csv or .xlsx)")
    ap.add_argument("--out", type=Path, default=ROOT / "inventory" / "inventory.json")
    ap.add_argument("--exclude", type=Path, default=ROOT / "data" / "exclude.txt")
    ap.add_argument("--photos", type=Path, default=ROOT / "photos")
    ap.add_argument("--config", type=Path, default=ROOT / "site.config.json")
    ap.add_argument("--prices", type=Path, default=ROOT / "data" / "raw" / "price_checks.json",
                    help="output of tools/check_dealer_prices.py (prices stay hidden without it)")
    ap.add_argument("--dc-export", type=Path, help="DriveCentric export to pair with Muse's "
                    "site list: supplies the price to compare, Age and Deals")
    ap.add_argument("--site-checked-at", help="ISO time Muse pulled the site list, when the "
                    "file has no pulled_at column")
    ap.add_argument("--date", help="value for 'updated' (default: today, UTC)")
    ap.add_argument("--now", help="ISO time used for the 24-hour price check (default: now)")
    a = ap.parse_args(argv)
    try:
        rows = read_export(a.export)
        unmatched = []
        if a.dc_export:
            rows, unmatched = merge_dc(rows, read_export(a.dc_export))
        config = json.loads(a.config.read_text(encoding="utf-8")) if a.config.exists() else {}
        inventory, report = build(
            rows, exclude=load_exclude(a.exclude), photos_dir=a.photos,
            price_checks=load_price_checks(a.prices), config=config, date=a.date,
            now=parse_time(a.now) if a.now else None, site_checked_at=a.site_checked_at)
    except BuildError as e:
        print(f"BUILD FAILED: {e}", file=sys.stderr)
        return 1
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(dumps(inventory), encoding="utf-8", newline="\n")
    print_report(inventory, report)
    if unmatched:
        print(f"NOTE: {len(unmatched)} cars on the site list are not in the DriveCentric file "
              f"(listed with no price): " + ", ".join(unmatched[:20]))
    print(f"\nWrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
