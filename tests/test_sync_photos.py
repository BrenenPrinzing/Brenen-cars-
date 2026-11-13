import json

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

import build_inventory as bi  # noqa: E402
import sync_photos as sp  # noqa: E402

STOCKS = {"C51234", "CP60123"}


def photo(path, size=(2400, 1800), color=(30, 60, 90), gps=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", size, color)
    if gps:
        exif = Image.Exif()
        exif[0x8825] = {1: "N", 2: (39.0, 5.0, 0.0)}
        exif[0x010F] = "PhoneMaker"
        im.save(path, "JPEG", exif=exif)
    else:
        im.save(path, "JPEG")
    return path


@pytest.fixture
def dirs(tmp_path):
    src, dest = tmp_path / "muse", tmp_path / "photos"
    for i in range(1, 8):
        photo(src / "C51234" / f"{i:02d}.jpg", color=(i * 30, 0, 0))
    photo(src / "CP60123" / "01.jpg", gps=True)
    photo(src / "L12345" / "01.jpg")                       # out-of-area, not in the kept set
    (src / "C51234" / "notes.txt").write_text("x")
    return src, dest


def test_copies_resized_stripped_and_capped(dirs):
    src, dest = dirs
    r = sp.sync(src, dest, STOCKS)
    assert r["written"] == 6 and r["cars"] == 2
    names = sorted(p.name for p in (dest / "C51234").iterdir())
    assert names == [f"site-0{i}.jpg" for i in range(1, 6)]            # capped at 5
    assert not (dest / "L12345").exists()
    for p in dest.glob("*/*.jpg"):
        info = bi.photo_info(p)
        assert not info["gps"] and max(info["width"], info["height"]) == 960
        with Image.open(p) as im:
            assert not im.getexif()
        assert p.stat().st_size < 200_000
    assert bi.photo_info(src / "CP60123" / "01.jpg")["gps"]             # source really had GPS


def test_second_run_reuses_everything(dirs):
    src, dest = dirs
    sp.sync(src, dest, STOCKS)
    before = {p: p.stat().st_mtime_ns for p in dest.glob("*/*.jpg")}
    r = sp.sync(src, dest, STOCKS)
    assert r["written"] == 0 and r["reused"] == 6
    assert before == {p: p.stat().st_mtime_ns for p in dest.glob("*/*.jpg")}


def test_changed_source_photo_is_redone(dirs):
    src, dest = dirs
    sp.sync(src, dest, STOCKS)
    photo(src / "CP60123" / "01.jpg", color=(200, 200, 200))
    r = sp.sync(src, dest, STOCKS)
    assert r["written"] == 1 and r["reused"] == 5


def test_sold_car_folder_removed_and_own_photos_kept(dirs):
    src, dest = dirs
    photo(dest / "C51234" / "01.jpg", size=(800, 600))                  # Brenen's own shot
    sp.sync(src, dest, STOCKS)
    assert (dest / "C51234" / "01.jpg").exists()
    r = sp.sync(src, dest, {"C51234"})                                  # CP60123 sold
    assert r["removed"] == 1 and not (dest / "CP60123").exists()
    manifest = json.loads((dest / sp.MANIFEST).read_text())
    assert set(manifest) == {f"C51234/site-0{i}.jpg" for i in range(1, 6)}


def test_fewer_source_photos_drops_extras(dirs):
    src, dest = dirs
    sp.sync(src, dest, STOCKS)
    for i in range(3, 8):
        (src / "C51234" / f"{i:02d}.jpg").unlink()
    sp.sync(src, dest, STOCKS)
    assert sorted(p.name for p in (dest / "C51234").iterdir()) == ["site-01.jpg", "site-02.jpg"]


def test_bad_file_is_skipped_not_fatal(dirs):
    src, dest = dirs
    (src / "CP60123" / "00.jpg").write_bytes(b"not an image")
    r = sp.sync(src, dest, STOCKS)
    assert any("CP60123/00.jpg" in s for s in r["skipped"])
    assert (dest / "CP60123" / "site-01.jpg").exists()


def test_converter_lists_own_photos_before_site_photos(dirs, tmp_path):
    src, dest = dirs
    photo(dest / "C51234" / "01.jpg", size=(800, 600))
    sp.sync(src, dest, STOCKS)
    rows = [{"vehicle": "2026 Cadillac Escalade", "stocknumber": "C51234", "sold": "No"}]
    car = bi.build(rows, photos_dir=dest)[0]["cars"][0]
    assert car["photos"][0] == "photos/C51234/01.jpg"
    assert car["photos"][1:] == [f"photos/C51234/site-0{i}.jpg" for i in range(1, 6)]


def test_cars_not_in_drivecentric_get_no_photos(dirs, tmp_path):
    import sample_export as sx
    src, dest = dirs
    sx.write_csv(tmp_path / "store.csv", ["Vehicle", "Sold", "Stock Number"],
                 [["2026 Cadillac Escalade", "No", "C51234"], ["2023 Cadillac XT5", "No", "CP60123"]])
    sx.write_csv(tmp_path / "dc.csv", ["Vehicle", "Stock Number"], [["2026 Cadillac Escalade", "C51234"]])
    stocks = sp.kept_stocks(tmp_path / "store.csv", None, tmp_path / "dc.csv")
    assert stocks == {"C51234"}
    sp.sync(src, dest, stocks)
    assert (dest / "C51234").is_dir() and not (dest / "CP60123").exists()
