import datetime as dt
import json
import struct

import pytest

import build_inventory as bi
import sample_export as sx

NOW = dt.datetime(2026, 11, 12, 18, 0, tzinfo=dt.timezone.utc)
FRESH = "2026-11-12T12:00:00Z"
STALE = "2026-11-11T17:00:00Z"
CONFIG = {"price_disclaimer": "Price includes the admin fee. Tax, title and license extra."}


@pytest.fixture
def rows(tmp_path):
    return bi.read_export(sx.write_csv(tmp_path / "export.csv"))


def build(rows, **kw):
    kw.setdefault("now", NOW)
    kw.setdefault("date", "2026-11-12")
    return bi.build(rows, **kw)


def by_stock(inv):
    return {c["stock"]: c for c in inv["cars"]}


# --- Acceptance 1: store, sold and in-transit filters --------------------------------

def test_keeps_only_kc_unsold_real_stock(rows):
    inv, report = build(rows)
    stocks = set(by_stock(inv))
    assert stocks == sx.KEPT_STOCKS
    assert not stocks & sx.FAR_STOCKS
    assert not stocks & sx.SOLD_STOCKS
    assert not stocks & sx.TRANSIT_STOCKS
    assert report["dropped"] == {"sold": 2, "delivered": 0, "bad_stock": 4, "far_store": 13,
                                 "excluded": 0, "duplicate": 0, "not_on_dealer_site": 0}
    assert inv["source_rows"] == len(sx.ROWS) and inv["kept"] == len(sx.KEPT_STOCKS)


# FAR_STORE tests, carried over with the regex from marketplace_picker.py.
@pytest.mark.parametrize("stock", [
    "L12345", "LT12345", "LX12345", "DLP1234", "DLX1234",          # Lawrence
    "F12345", "FT12345", "FX12345", "FP12345", "DF12345", "DFT1234", "DFX1234", "KF12345",  # Topeka
    "106671A", "BP12345", "BT12345", "BX12345", "DX12345",          # Independence
    "B1234", "B1234A", "DB1234", "T12345", "X12345", "P12345", "P12345A",
])
def test_far_store_matches_out_of_area(stock):
    assert bi.FAR_STORE.match(stock)


@pytest.mark.parametrize("stock", [
    "C51234", "DC50111", "CP60123", "CT60222", "CX60500", "C51199A",  # KC Cadillac
    "B12345", "DB12345",   # KC Cadillac uses 5 digits
    "T4321",               # KC Chevy uses 4
    "X123456",             # KC Chevy uses 6
    "P61234",              # KC uses P6####
])
def test_far_store_leaves_kc_alone(stock):
    assert not bi.FAR_STORE.match(stock)
    assert bi.STOCK_OK.match(stock)


@pytest.mark.parametrize("stock", ["GHJWPW*O", "GKXTRB", "", "C123", "ABCD12345", "C1234567"])
def test_stock_pattern_drops_order_codes(stock):
    assert not bi.STOCK_OK.match(stock)


@pytest.mark.parametrize("sold,kept", [("Yes", 0), ("YES", 0), (" yes ", 0), ("Y", 0), ("TRUE", 0),
                                       ("1", 0), ("Sold", 0), ("No", 1), ("", 1), ("0", 1), ("FALSE", 1)])
def test_sold_spellings(tmp_path, sold, kept):
    rows = bi.read_export(sx.write_csv(tmp_path / "e.csv", ["Vehicle", "Sold", "Stock Number"],
                                       [["2023 Cadillac XT5", sold, "CP60123"]]))
    assert build(rows)[0]["kept"] == kept


@pytest.mark.parametrize("delivered,kept", [("Yes", 0), ("yes", 0), ("Y", 0), ("No", 1), ("", 1)])
def test_delivered_cars_are_dropped(tmp_path, delivered, kept):
    rows = bi.read_export(sx.write_csv(tmp_path / "e.csv", ["Vehicle", "Sold", "Delivered", "Stock Number"],
                                       [["2023 Cadillac XT5", "No", delivered, "CP60123"]]))
    inv, report = build(rows)
    assert inv["kept"] == kept and report["dropped"]["delivered"] == 1 - kept


def test_exclude_list_holds_cars(rows, tmp_path):
    hold = tmp_path / "exclude.txt"
    hold.write_text("# another rep's deal\ncp60123\n\nC51199A  # proposal\n")
    inv, report = build(rows, exclude=bi.load_exclude(hold))
    assert not {"CP60123", "C51199A"} & set(by_stock(inv))
    assert report["dropped"]["excluded"] == 2


# --- Field rules ---------------------------------------------------------------------

def test_condition_body_and_miles(rows):
    cars = by_stock(build(rows)[0])
    assert cars["C51234"]["condition"] == "New"
    assert cars["DC50111"]["condition"] == "Demo"
    assert cars["CP60123"]["condition"] == "Pre-owned"
    assert cars["C51199A"]["condition"] == "Pre-owned"   # trade-in with a letter suffix
    assert "miles" not in cars["C51234"]                 # never on new
    assert cars["DC50111"]["miles"] == 4300
    assert cars["CP60123"]["miles"] == 52800
    assert cars["CX60500"]["miles"] == 88000
    assert cars["C51234"]["body"] == "SUV"
    assert cars["C51240"]["body"] == "EV"
    assert cars["CT60222"]["body"] == "EV"               # Escalade IQ
    assert cars["P61234"]["body"] == "EV"                # iX
    assert cars["DC50111"]["body"] == "Sedan"
    assert cars["C51199A"]["body"] == "Truck"
    assert cars["T4321"]["body"] == "Truck"
    assert cars["CX60500"]["body"] == "Sedan"
    assert (cars["C51234"]["year"], cars["C51234"]["make"], cars["C51234"]["model"]) == \
        (2026, "Cadillac", "Escalade")
    assert cars["T4321"]["model"] == "Silverado 1500"


def test_ev_list():
    for model in ("LYRIQ", "OPTIQ", "VISTIQ", "Escalade IQ", "Escalade IQL",
                  "F-150 Lightning", "iX"):
        assert bi.body_for(model) == "EV", model
    assert bi.body_for("Escalade") == "SUV"
    assert bi.body_for("Escalade ESV") == "SUV"
    assert bi.body_for("F-150") == "Truck"
    assert bi.body_for("iX3") == "SUV"


def test_optional_columns_and_header_matching(tmp_path):
    headers = [" vehicle ", "SOLD", "stock number", "Trim", "MILEAGE", "vin",
               "Exterior Color", "interior  color", "Body", "Some New Column"]
    row = ["2023 Cadillac XT5", "No", "cp60123", "Luxury", "10,049", "1GYKNCRS0PZ000000",
           "Stellar Black", "Jet Black", "Crossover", "ignored"]
    rows = bi.read_export(sx.write_csv(tmp_path / "e.csv", headers, [row]))
    car = build(rows)[0]["cars"][0]
    assert car == {"stock": "CP60123", "year": 2023, "make": "Cadillac", "model": "XT5",
                   "trim": "Luxury", "condition": "Pre-owned", "body": "Crossover",
                   "photos": [], "miles": 10000, "ext_color": "Stellar Black",
                   "int_color": "Jet Black", "vin": "1GYKNCRS0PZ000000"}


def test_xlsx_gives_same_result_as_csv(tmp_path, rows):
    xrows = bi.read_export(sx.write_xlsx(tmp_path / "export.xlsx"))
    assert bi.dumps(build(xrows)[0]) == bi.dumps(build(rows)[0])


# --- Acceptance 2 and 12: banned keys, new arrivals ----------------------------------

BANNED = {"msrp", "payment", "leads", "last_lead", "deals", "age"}


def all_keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k.lower()
            yield from all_keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from all_keys(v)


def test_no_banned_keys_or_values(rows):
    inv, _ = build(rows)
    assert not BANNED & set(all_keys(inv))
    text = bi.dumps(inv)
    assert "121000" not in text and "10/26/2026" not in text   # Msrp and Last lead values


def test_new_arrival_set_from_age_without_publishing_age(rows):
    cars = by_stock(build(rows)[0])
    assert cars["C51234"].get("new_arrival") is True       # Age 3
    assert cars["CP60123"].get("new_arrival") is True      # Age 7
    assert "new_arrival" not in cars["C51199A"]            # Age 8
    assert "new_arrival" not in cars["CT60222"]            # Age blank
    assert "age" not in set(all_keys(cars))


def test_unknown_key_is_a_hard_error():
    inv = {"updated": "2026-11-12", "source_rows": 1, "kept": 1,
           "cars": [{"stock": "C51234", "msrp": 1}]}
    with pytest.raises(bi.BuildError):
        bi.validate(inv)
    with pytest.raises(bi.BuildError):
        bi.validate({"updated": "x", "cars": [], "leads": 3})


# --- Acceptance 2 and 13: prices -----------------------------------------------------

def checks(**over):
    base = {
        "C51234": {"status": "ok", "price": 118990, "checked_at": FRESH,
                   "carfax_url": "https://www.carfax.com/VehicleHistory/p/Report.cfx?vin=X"},
        "CP60123": {"status": "ok", "price": 39995, "checked_at": FRESH},      # mismatch
        "DC50111": {"status": "ok", "price": 48500, "checked_at": STALE},      # 25 hours old
        "C51199A": {"status": "fetch_failed", "checked_at": FRESH},
        "T4321": {"status": "robots_blocked", "checked_at": FRESH},
        "CT60222": {"status": "ok", "price": 0, "checked_at": FRESH},          # $0
        "CX60500": {"status": "no_price", "checked_at": FRESH},
        "C51240": {"status": "ok", "price": 63990, "checked_at": FRESH},
    }
    base.update(over)
    return base


def test_price_only_on_exact_fresh_match(rows):
    inv, report = build(rows, price_checks=checks(), config=CONFIG)
    cars = by_stock(inv)
    assert {s for s, c in cars.items() if "price" in c} == {"C51234", "C51240"}
    assert cars["C51234"]["price"] == 118990
    hidden = dict(report["hidden_prices"])
    assert "mismatch" in hidden["CP60123"]
    assert "24 hours" in hidden["DC50111"]
    assert "fetch_failed" in hidden["C51199A"]
    assert "robots_blocked" in hidden["T4321"]
    assert hidden["CT60222"] == "no price on dealer site"
    assert inv["prices_checked_at"] == FRESH


def test_no_checks_means_no_prices(rows):
    inv, _ = build(rows)
    assert not any("price" in c for c in inv["cars"])
    assert "prices_checked_at" not in inv


def test_export_price_never_leaks_on_mismatch(rows):
    inv, _ = build(rows, price_checks=checks(), config=CONFIG)
    text = bi.dumps(inv)
    for hidden_price in ("38995", "39995", "48500", "41500", "33900"):
        assert hidden_price not in text


def test_build_fails_when_prices_exist_and_disclaimer_empty(rows):
    for config in ({}, {"price_disclaimer": ""}, {"price_disclaimer": "   "}, None):
        with pytest.raises(bi.BuildError, match="price_disclaimer"):
            build(rows, price_checks=checks(), config=config)
    build(rows, config={})  # no prices, no disclaimer needed


def test_carfax_link_only_from_ok_check_and_carfax_host(rows):
    c = checks(CP60123={"status": "ok", "price": 38995, "checked_at": FRESH,
                        "carfax_url": "https://evil.example/carfax.com/"},
               C51199A={"status": "fetch_failed", "checked_at": FRESH,
                        "carfax_url": "https://www.carfax.com/x"})
    cars = by_stock(build(rows, price_checks=c, config=CONFIG)[0])
    assert cars["C51234"]["carfax_url"].startswith("https://www.carfax.com/")
    assert "carfax_url" not in cars["CP60123"]
    assert "carfax_url" not in cars["C51199A"]


# --- Sync with the dealer site: drop cars it no longer lists -------------------------

def ok_checks(stocks, **over):
    c = {s: {"status": "ok", "price": 1, "checked_at": FRESH} for s in stocks}
    c.update(over)
    return c


def test_car_gone_from_dealer_site_is_dropped(rows):
    gone = {"status": "not_found", "checked_at": FRESH}
    c = ok_checks(sx.KEPT_STOCKS, CP60123=gone, T4321=gone)
    inv, report = build(rows, price_checks=c, config=CONFIG)
    assert set(by_stock(inv)) == sx.KEPT_STOCKS - {"CP60123", "T4321"}
    assert report["gone"] == ["CP60123", "T4321"] and report["dropped"]["not_on_dealer_site"] == 2
    assert inv["kept"] == len(sx.KEPT_STOCKS) - 2


def test_stale_not_found_does_not_drop(rows):
    c = ok_checks(sx.KEPT_STOCKS, CP60123={"status": "not_found", "checked_at": STALE})
    assert "CP60123" in by_stock(build(rows, price_checks=c, config=CONFIG)[0])


def test_failed_fetch_or_robots_block_never_drops(rows):
    c = ok_checks(sx.KEPT_STOCKS, CP60123={"status": "fetch_failed", "checked_at": FRESH},
                  T4321={"status": "robots_blocked", "checked_at": FRESH},
                  C51240={"status": "no_price", "checked_at": FRESH})
    assert set(by_stock(build(rows, price_checks=c, config=CONFIG)[0])) == sx.KEPT_STOCKS


def test_broken_site_reader_cannot_empty_the_list(rows):
    c = {s: {"status": "not_found", "checked_at": FRESH} for s in sx.KEPT_STOCKS}
    inv, report = build(rows, price_checks=c)
    assert set(by_stock(inv)) == sx.KEPT_STOCKS and report["gone"] == []
    assert any("no cars were dropped" in w for w in report["warnings"])
    # Just under half found: still treated as a reader problem.
    some = ok_checks(list(sx.KEPT_STOCKS)[:4], **{s: c[s] for s in list(sx.KEPT_STOCKS)[4:]})
    assert set(by_stock(build(rows, price_checks=some, config=CONFIG)[0])) == sx.KEPT_STOCKS


# --- Muse's daily site list (inventory-store.csv) ------------------------------------

SITE_HEADERS = ["stock_number", "vin", "year", "make", "model", "trim", "condition", "price",
                "mileage", "exterior_color", "interior_color", "engine", "vdp_url", "photo_url"]
SITE_ROWS = [
    ["C51234", "1GYS9GKL9VR000001", "2027", "Cadillac", "Escalade", "Platinum Sport", "New", "131185", "279",
     "Black Raven", "Sheer Gray, Full Leather", "6.2L V8 engine", "https://dealer.example/new-1", "https://dealer.example/1.jpg"],
    ["CP60123", "1GYKNCRS0PZ000000", "2023", "Cadillac", "XT5", "Premium Luxury", "Certified Pre-Owned", "39615", "52849",
     "Stellar Black", "Jet Black", "3.6L V6", "https://dealer.example/used-2", "https://dealer.example/2.jpg"],
    ["CX60500", "1HGCV1F50KA000000", "2019", "Honda", "Accord", "EX-L", "Used", "", "88049",
     "White", "Black", "1.5L", "https://dealer.example/used-3", "https://dealer.example/3.jpg"],
    ["L12345", "5XYP5DHC0NG000000", "2022", "Kia", "Telluride", "SX", "Used", "39000", "30000",
     "Gray", "Black", "3.8L", "https://dealer.example/used-4", "https://dealer.example/4.jpg"],
]
FEE_CONFIG = dict(CONFIG, dealer_site={"admin_fee": 620})


def site_rows(tmp_path, extra_headers=(), extra=()):
    rows = [r + list(e) for r, e in zip(SITE_ROWS, extra)] if extra else SITE_ROWS
    return bi.read_export(sx.write_csv(tmp_path / "store.csv", SITE_HEADERS + list(extra_headers), rows))


def test_site_list_builds_cars_without_prices_or_dealer_urls(tmp_path):
    inv, report = build(site_rows(tmp_path), config=FEE_CONFIG, site_checked_at=FRESH)
    cars = by_stock(inv)
    assert set(cars) == {"C51234", "CP60123", "CX60500"}             # Lawrence unit dropped
    assert cars["C51234"] == {"stock": "C51234", "year": 2027, "make": "Cadillac", "model": "Escalade",
                              "trim": "Platinum Sport", "condition": "New", "body": "SUV", "photos": [],
                              "ext_color": "Black Raven", "int_color": "Sheer Gray, Full Leather",
                              "vin": "1GYS9GKL9VR000001"}             # no miles on new, no price
    assert cars["CP60123"]["condition"] == "Pre-owned" and cars["CP60123"]["miles"] == 52800
    text = bi.dumps(inv)
    assert "dealer.example" not in text and "131185" not in text and "engine" not in text.lower()
    assert dict(report["hidden_prices"])["C51234"] == "no DriveCentric price to compare"
    assert dict(report["hidden_prices"])["CX60500"] == "check no_price"
    assert not report["warnings"]


def test_site_price_shows_only_when_drivecentric_is_exactly_the_fee_less(tmp_path):
    rows = site_rows(tmp_path, ["dc_price"], [["130565"], ["38990"], ["21000"], ["38380"]])
    inv, report = build(rows, config=FEE_CONFIG, site_checked_at=FRESH)
    cars = by_stock(inv)
    assert cars["C51234"]["price"] == 131185                          # 130,565 + 620, site price shown
    assert "price" not in cars["CP60123"]                             # 38,990 + 620 != 39,615
    assert "38,990 + $620 fee vs site $39,615" in dict(report["hidden_prices"])["CP60123"]
    assert "130565" not in bi.dumps(inv)                              # DriveCentric price never published
    assert inv["prices_checked_at"] == FRESH


def test_site_price_needs_a_pull_time_under_24_hours(tmp_path):
    rows = site_rows(tmp_path, ["dc_price"], [["130565"], ["38995"], [""], [""]])
    assert not any("price" in c for c in build(rows, config=FEE_CONFIG)[0]["cars"])
    assert not any("price" in c for c in build(rows, config=FEE_CONFIG, site_checked_at=STALE)[0]["cars"])
    timed = site_rows(tmp_path, ["dc_price", "pulled_at"], [["130565", FRESH], ["38995", STALE], ["", FRESH], ["", FRESH]])
    cars = by_stock(build(timed, config=FEE_CONFIG)[0])
    assert cars["C51234"]["price"] == 131185 and "price" not in cars["CP60123"]


def test_fee_rule_applies_to_drivecentric_exports_too(rows):
    c = checks(C51234={"status": "ok", "price": 119610, "checked_at": FRESH},      # 118,990 + 620
               C51240={"status": "ok", "price": 63990, "checked_at": FRESH})       # equal, so no match
    cars = by_stock(build(rows, price_checks=c, config=FEE_CONFIG)[0])
    assert cars["C51234"]["price"] == 119610 and "price" not in cars["C51240"]


def test_site_list_paired_with_drivecentric_file(tmp_path, capsys):
    sx.write_csv(tmp_path / "store.csv", SITE_HEADERS, SITE_ROWS)
    sx.write_csv(tmp_path / "dc.csv", sx.HEADERS, [
        ["2027 Cadillac Escalade", "No", "No", "Platinum Sport", "C51234", "130565.0", "0.0", "279", "2", "", "1", "3"],
        ["2023 Cadillac XT5", "No", "Yes", "Premium Luxury", "CP60123", "38995.0", "0.0", "52849", "0", "", "0", "40"],
    ])
    (tmp_path / "cfg.json").write_text(json.dumps(FEE_CONFIG))
    out = tmp_path / "inv.json"
    assert bi.main([str(tmp_path / "store.csv"), "--dc-export", str(tmp_path / "dc.csv"),
                    "--config", str(tmp_path / "cfg.json"), "--out", str(out), "--photos", str(tmp_path / "p"),
                    "--exclude", str(tmp_path / "x.txt"), "--prices", str(tmp_path / "none.json"),
                    "--site-checked-at", FRESH, "--now", "2026-11-12T18:00:00Z"]) == 0
    cars = {c["stock"]: c for c in json.loads(out.read_text())["cars"]}
    assert cars["C51234"]["price"] == 131185 and cars["C51234"]["new_arrival"] is True
    assert "CP60123" not in cars                              # DriveCentric says delivered
    assert "price" not in cars["CX60500"]                     # not in the DriveCentric file
    printed = capsys.readouterr().out
    assert "REVIEW" in printed and "C51234" in printed        # deal count carried over
    assert "CX60500" in printed and "not in the DriveCentric file" in printed
    text = out.read_text().lower()
    assert not {"deals", "leads", "msrp", '"age"'} & {w for w in ("deals", "leads", "msrp", '"age"') if w in text}


def test_condition_disagreement_is_reported(tmp_path):
    rows = bi.read_export(sx.write_csv(tmp_path / "s.csv", SITE_HEADERS, [
        ["C51234"] + SITE_ROWS[0][1:6] + ["Used"] + SITE_ROWS[0][7:]]))
    inv, report = build(rows)
    assert inv["cars"][0]["condition"] == "New"
    assert any("C51234" in w and "Used" in w for w in report["warnings"])


# --- Acceptance 3: idempotent --------------------------------------------------------

def test_same_input_gives_identical_bytes(tmp_path):
    sx.write_csv(tmp_path / "export.csv")
    (tmp_path / "cfg.json").write_text(json.dumps(CONFIG))
    (tmp_path / "checks.json").write_text(json.dumps({"checks": checks()}))
    args = [str(tmp_path / "export.csv"), "--config", str(tmp_path / "cfg.json"),
            "--prices", str(tmp_path / "checks.json"), "--photos", str(tmp_path / "photos"),
            "--exclude", str(tmp_path / "none.txt"), "--date", "2026-11-12",
            "--now", "2026-11-12T18:00:00Z"]
    assert bi.main(args + ["--out", str(tmp_path / "a.json")]) == 0
    assert bi.main(args + ["--out", str(tmp_path / "b.json")]) == 0
    a, b = (tmp_path / "a.json").read_bytes(), (tmp_path / "b.json").read_bytes()
    assert a == b and a.endswith(b"\n")


def test_row_order_does_not_change_output(rows):
    assert bi.dumps(build(list(reversed(rows)))[0]) == bi.dumps(build(rows)[0])


def test_sorted_by_condition_make_model_year(rows):
    cars = build(rows)[0]["cars"]
    conditions = [c["condition"] for c in cars]
    assert conditions == sorted(conditions, key=bi.CONDITION_ORDER.get)
    pre = [(c["make"].lower(), c["model"].lower()) for c in cars if c["condition"] == "Pre-owned"]
    assert pre == sorted(pre)


# --- Review list ---------------------------------------------------------------------

def test_review_list_prints_kept_cars_with_deals(rows, capsys):
    inv, report = build(rows)
    assert {r[0] for r in report["review"]} == {"DC50111", "C51199A"}   # sold ones not listed
    bi.print_report(inv, report)
    out = capsys.readouterr().out
    assert "C51199A" in out and "exclude.txt" in out
    assert "deals" not in bi.dumps(inv).lower()


# --- Photos --------------------------------------------------------------------------

def jpeg(width=800, height=600, gps=False):
    out = b"\xff\xd8"
    if gps is not None:
        tag = 0x8825 if gps else 0x010F
        tiff = b"II*\x00\x08\x00\x00\x00" + struct.pack("<H", 1) + \
            struct.pack("<HHII", tag, 4, 1, 26) + b"\x00\x00\x00\x00"
        body = b"Exif\x00\x00" + tiff
        out += b"\xff\xe1" + struct.pack(">H", len(body) + 2) + body
    sof = b"\x08" + struct.pack(">HH", height, width) + b"\x03" + b"\x01\x11\x00" * 3
    out += b"\xff\xc0" + struct.pack(">H", len(sof) + 2) + sof
    return out + b"\xff\xd9"


def test_photos_listed_in_name_order(rows, tmp_path):
    folder = tmp_path / "photos" / "C51234"
    folder.mkdir(parents=True)
    (folder / "02.jpg").write_bytes(jpeg())
    (folder / "01.jpg").write_bytes(jpeg(gps=None))
    (folder / "notes.txt").write_text("x")
    cars = by_stock(build(rows, photos_dir=tmp_path / "photos")[0])
    assert cars["C51234"]["photos"] == ["photos/C51234/01.jpg", "photos/C51234/02.jpg"]
    assert cars["C51240"]["photos"] == []


def test_gps_photo_refuses_to_build(rows, tmp_path):
    folder = tmp_path / "photos" / "C51234"
    folder.mkdir(parents=True)
    (folder / "01.jpg").write_bytes(jpeg(gps=True))
    with pytest.raises(bi.BuildError, match="GPS"):
        build(rows, photos_dir=tmp_path / "photos")


def test_webp_gps_refuses_to_build(rows, tmp_path):
    tiff = b"MM\x00*\x00\x00\x00\x08" + struct.pack(">H", 1) + \
        struct.pack(">HHII", 0x8825, 4, 1, 26) + b"\x00\x00\x00\x00"
    vp8x = b"VP8X" + struct.pack("<I", 10) + b"\x08\x00\x00\x00" + \
        (799).to_bytes(3, "little") + (599).to_bytes(3, "little")
    exif = b"EXIF" + struct.pack("<I", len(tiff)) + tiff
    body = b"WEBP" + vp8x + exif
    folder = tmp_path / "photos" / "C51234"
    folder.mkdir(parents=True)
    (folder / "01.webp").write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)
    info = bi.photo_info(folder / "01.webp")
    assert info == {"gps": True, "width": 800, "height": 600}
    with pytest.raises(bi.BuildError, match="GPS"):
        build(rows, photos_dir=tmp_path / "photos")


def test_oversize_photo_warns(rows, tmp_path):
    folder = tmp_path / "photos" / "C51234"
    folder.mkdir(parents=True)
    (folder / "01.jpg").write_bytes(jpeg(width=4032, height=3024))
    _, report = build(rows, photos_dir=tmp_path / "photos")
    assert any("1600px" in w for w in report["warnings"])
