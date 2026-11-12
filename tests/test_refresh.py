import json
import shutil

import check_dealer_prices as cdp
import refresh
import sample_export as sx
from test_check_dealer_prices import BASE
from test_site import ROOT


def make_root(tmp_path):
    root = tmp_path / "site"
    shutil.copytree(ROOT / "src", root / "src")
    for name in ("site.config.json", "index.html", "car.html", "brenen.vcf"):
        shutil.copy(ROOT / name, root / name)
    cfg = json.loads((root / "site.config.json").read_text())
    cfg["dealer_site"]["base_url"] = BASE
    (root / "data" / "raw").mkdir(parents=True)
    sx.write_csv(root / "data" / "raw" / "export.csv")
    return root, root / "data" / "raw" / "export.csv"


def test_refresh_without_dealer_check_makes_no_requests(tmp_path, monkeypatch, capsys):
    root, export = make_root(tmp_path)
    monkeypatch.setattr(cdp, "fetch", lambda url: (_ for _ in ()).throw(AssertionError(url)))
    assert refresh.main([str(export), "--root", str(root)]) == 0
    inv = json.loads((root / "inventory" / "inventory.json").read_text())
    assert {c["stock"] for c in inv["cars"]} == sx.KEPT_STOCKS
    assert not any("price" in c for c in inv["cars"])
    assert "Dealer site not checked" in capsys.readouterr().out


def test_refresh_with_dealer_check_drops_cars_no_longer_listed(tmp_path, monkeypatch, capsys):
    root, export = make_root(tmp_path)
    sold_since_export = {"CP60123", "T4321"}

    def fake_fetch(url):
        if url.endswith("/robots.txt"):
            return ""
        stock = url.rsplit("=", 1)[1]
        if stock in sold_since_export:
            return "<html><body>No vehicles found</body></html>"
        return f"<div data-stocknum='{stock}' data-price='12345'></div>"

    real = cdp.check_all
    monkeypatch.setattr(cdp, "check_all",
                        lambda cars, **kw: real(cars, fetcher=fake_fetch, sleep=lambda s: None, **kw))
    assert refresh.main([str(export), "--dealer-check", "--root", str(root)]) == 0
    inv = json.loads((root / "inventory" / "inventory.json").read_text())
    assert {c["stock"] for c in inv["cars"]} == sx.KEPT_STOCKS - sold_since_export
    assert not any("price" in c for c in inv["cars"])        # 12345 never matches the export
    out = capsys.readouterr().out
    assert "No longer on the dealer site (dropped): CP60123, T4321" in out
