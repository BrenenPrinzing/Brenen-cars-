import datetime as dt
import json
import urllib.error

import pytest

import build_inventory as bi
import check_dealer_prices as cdp
import sample_export as sx

BASE = "https://dealer.example"
TEMPLATES = {"used": "/searchused.aspx?q={stock}", "new": "/searchnew.aspx?q={stock}"}
CARFAX = "https://www.carfax.com/VehicleHistory/p/Report.cfx?partner=DLR_0&vin=1GYKNCRS0PZ000000"

# Invented pages in two common dealer-site shapes. Not copied from any real site.
JSONLD_PAGE = """<html><head><script type="application/ld+json">
{"@context":"https://schema.org","@type":"Car","name":"2023 Cadillac XT5",
 "sku":"CP60123","vehicleIdentificationNumber":"1GYKNCRS0PZ000000",
 "offers":{"@type":"Offer","price":"38995","priceCurrency":"USD"}}
</script></head><body>
<a href="%s">Show me the CARFAX</a></body></html>""" % CARFAX

CARD_PAGE = """<html><body>
<div class="vehicle-card" data-stocknum="CP60123" data-vin="1GYKNCRS0PZ000000" data-price="38995" data-msrp="45000">
  <h2>2023 Cadillac XT5</h2><span class="price">$38,995</span>
  <img src="x.jpg"><br>
  <a href="http://www.carfax.com/VehicleHistory/p/Report.cfx?vin=1GYKNCRS0PZ000000">CARFAX</a>
</div>
<div class="vehicle-card" data-stocknum="CP60200" data-price="29,900.00">
  <a href="https://www.carfax.com/VehicleHistory/p/Report.cfx?vin=OTHER">CARFAX</a>
</div>
<div class="vehicle-card" data-stocknum="CT60222" data-price="0"></div>
</body></html>"""


def test_parses_jsonld_listing():
    r = cdp.parse_listing(JSONLD_PAGE, "cp60123")
    assert r == {"status": "ok", "price": 38995, "carfax_url": CARFAX}


def test_parses_card_listing_and_keeps_cars_apart():
    r = cdp.parse_listing(CARD_PAGE, "CP60123")
    assert r["status"] == "ok" and r["price"] == 38995          # not the 45000 MSRP
    assert r["carfax_url"].startswith("https://www.carfax.com/") and "PZ000000" in r["carfax_url"]
    other = cdp.parse_listing(CARD_PAGE, "CP60200")
    assert other["price"] == 29900 and other["carfax_url"].endswith("vin=OTHER")


def test_matches_by_vin_when_stock_is_absent():
    page = JSONLD_PAGE.replace('"sku":"CP60123",', "")
    assert cdp.parse_listing(page, "CP60123", "1gyKNCRS0PZ000000")["price"] == 38995


@pytest.mark.parametrize("html,stock,status", [
    ("<html><body>No vehicles found</body></html>", "CP60123", "not_found"),
    (CARD_PAGE, "C99999", "not_found"),
    (CARD_PAGE, "CT60222", "no_price"),                               # $0
    (CARD_PAGE.replace('data-price="38995"', 'data-price="Call"'), "CP60123", "no_price"),
    (JSONLD_PAGE + CARD_PAGE.replace("38995", "37995"), "CP60123", "ambiguous"),
    ("<div data-stocknum='CP60123' data-price='38995.50'></div>", "CP60123", "no_price"),
    ("", "CP60123", "not_found"),
])
def test_any_doubt_hides_the_price(html, stock, status):
    assert cdp.parse_listing(html, stock) == {"status": status}


def test_jsonld_skips_msrp_and_payment_offers():
    page = """<script type="application/ld+json">{"@type":"Vehicle","sku":"C51234","offers":[
      {"@type":"Offer","name":"MSRP","price":121000},
      {"@type":"Offer","name":"Monthly payment","price":1599},
      {"@type":"Offer","price":118990}]}</script>"""
    assert cdp.parse_listing(page, "C51234")["price"] == 118990


# Shape of the store's detail page as Brenen photographed it: a retail price, the admin
# fee, then the fee-inclusive "Cable Dahmer Price". Invented markup, real wording.
LABEL = "Cable Dahmer Price"
FEE_PAGE = """<html><body><h1>2021 Cadillac CT5-V V-Series</h1><p>Stock: CP60123</p>
<div class="price" data-stocknum="CP60123" data-price="35005"><b>$35,625</b>
<span>CABLE DAHMER PRICE:</span> <a>Less</a>
<table><tr><td>Retail Price</td><td>$35,005</td></tr>
<tr><td>Administrative Fee</td><td>+$620</td></tr>
<tr><td>Cable Dahmer Price</td><td>$35,625</td></tr></table></div>
<a href="%s">CARFAX</a><script>var x = "Cable Dahmer Price $1";</script></body></html>""" % CARFAX


def test_fee_inclusive_label_price_wins_over_retail():
    r = cdp.parse_listing(FEE_PAGE, "CP60123", price_label=LABEL)
    assert r == {"status": "ok", "price": 35625, "carfax_url": CARFAX}
    assert cdp.parse_listing(FEE_PAGE, "CP60123")["price"] == 35005        # no label configured


def test_label_price_needs_the_cars_own_stock_or_vin_on_the_page():
    assert cdp.parse_listing(FEE_PAGE, "C99999", price_label=LABEL) == {"status": "not_found"}
    assert cdp.parse_listing(FEE_PAGE, "CP6012", price_label=LABEL) == {"status": "not_found"}
    no_attrs = FEE_PAGE.replace(' data-stocknum="CP60123" data-price="35005"', "")
    assert cdp.parse_listing(no_attrs, "CP60123", price_label=LABEL)["price"] == 35625


def test_two_different_label_prices_hide_the_price():
    page = FEE_PAGE + "<div>Similar: Stock CP60200 Cable Dahmer Price: $29,900</div>"
    assert cdp.parse_listing(page, "CP60123", price_label=LABEL) == {"status": "ambiguous"}


def test_carfax_link_must_be_on_carfax_host():
    page = CARD_PAGE.replace("http://www.carfax.com/", "https://carfax.com.evil.example/")
    assert cdp.parse_listing(page, "CP60123")["carfax_url"] is None
    assert not bi.is_carfax_url("http://www.carfax.com/x")
    assert bi.is_carfax_url("https://carfax.com/x")


def test_no_carfax_link_means_none():
    page = "<div data-stocknum='CP60123' data-price='38995'></div>"
    assert cdp.parse_listing(page, "CP60123") == {"status": "ok", "price": 38995,
                                                  "carfax_url": None}


# --- check_all: robots, rate limit, failures -----------------------------------------

class Net:
    def __init__(self, robots="User-agent: *\nDisallow: /admin/\n", pages=None):
        self.robots, self.pages, self.calls, self.sleeps = robots, pages or {}, [], []

    def fetch(self, url):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            if isinstance(self.robots, Exception):
                raise self.robots
            return self.robots
        page = self.pages.get(url)
        if page is None:
            raise urllib.error.URLError("down")
        return page

    def run(self, cars, **kw):
        clock = lambda: dt.datetime(2026, 11, 12, 12, 0, tzinfo=dt.timezone.utc)  # noqa: E731
        return cdp.check_all(cars, base=BASE, templates=TEMPLATES, fetcher=self.fetch,
                             sleep=self.sleeps.append, clock=clock, **kw)


CARS = [{"stock": "CP60123", "condition": "Pre-owned"},
        {"stock": "C51234", "condition": "New"},
        {"stock": "T4321", "condition": "Pre-owned"}]


def test_check_all_records_price_time_and_link():
    net = Net(pages={BASE + "/searchused.aspx?q=CP60123": JSONLD_PAGE,
                     BASE + "/searchnew.aspx?q=C51234": "<html></html>"})
    doc = net.run(CARS)
    c = doc["checks"]
    assert c["CP60123"] == {"status": "ok", "price": 38995, "carfax_url": CARFAX,
                            "checked_at": "2026-11-12T12:00:00Z",
                            "url": BASE + "/searchused.aspx?q=CP60123"}
    assert c["C51234"]["status"] == "not_found" and "price" not in c["C51234"]
    assert c["T4321"]["status"] == "fetch_failed"
    assert net.calls[0] == BASE + "/robots.txt"
    assert len(net.calls) == 4                       # robots + one GET per car, no retries


def test_waits_at_least_two_seconds_between_requests():
    net = Net()
    net.run(CARS, delay=0.1)                         # can't be set lower than 2
    assert net.sleeps == [2.0, 2.0]
    net2 = Net(robots="User-agent: *\nCrawl-delay: 5\n")
    net2.run(CARS)
    assert net2.sleeps == [5.0, 5.0]


def test_robots_block_means_no_request():
    net = Net(robots="User-agent: *\nDisallow: /searchused.aspx\n",
              pages={BASE + "/searchnew.aspx?q=C51234": "<html></html>"})
    doc = net.run(CARS)
    assert doc["checks"]["CP60123"]["status"] == "robots_blocked"
    assert doc["checks"]["T4321"]["status"] == "robots_blocked"
    assert not any("searchused" in u for u in net.calls)


@pytest.mark.parametrize("error", [urllib.error.URLError("down"),
                                   urllib.error.HTTPError(BASE, 503, "x", {}, None)])
def test_unreadable_robots_blocks_everything(error):
    net = Net(robots=error)
    doc = net.run(CARS)
    assert {c["status"] for c in doc["checks"].values()} == {"robots_unreadable"}
    assert net.calls == [BASE + "/robots.txt"]


def test_missing_robots_file_allows_checks():
    net = Net(robots=urllib.error.HTTPError(BASE, 404, "x", {}, None),
              pages={BASE + "/searchused.aspx?q=CP60123": JSONLD_PAGE})
    assert net.run(CARS[:1])["checks"]["CP60123"]["status"] == "ok"


def test_request_is_plain_get_with_generic_agent(monkeypatch):
    seen = {}

    class Resp:
        def read(self, n):
            return b"<html></html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        seen.update(method=req.get_method(), headers=dict(req.header_items()), data=req.data)
        return Resp()

    monkeypatch.setattr(cdp.urllib.request, "urlopen", fake_urlopen)
    cdp.fetch(BASE + "/x")
    assert seen["method"] == "GET" and seen["data"] is None
    assert seen["headers"]["User-agent"] == cdp.USER_AGENT
    assert not {"Cookie", "Authorization"} & set(seen["headers"])
    assert "brenen" not in cdp.USER_AGENT.lower() and "@" not in cdp.USER_AGENT


# --- End to end through the CLI ------------------------------------------------------

def test_cli_needs_explicit_yes(tmp_path, capsys):
    sx.write_csv(tmp_path / "export.csv")
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"dealer_site": {"base_url": BASE}}))
    code = cdp.main([str(tmp_path / "export.csv"), "--config", str(cfg),
                     "--out", str(tmp_path / "out.json")])
    assert code == 2 and not (tmp_path / "out.json").exists()
    assert "GSM" in capsys.readouterr().out


def test_cli_checks_only_kept_cars_and_feeds_the_converter(tmp_path, monkeypatch):
    sx.write_csv(tmp_path / "export.csv")
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"dealer_site": {"base_url": BASE},
                               "price_disclaimer": "Fine print."}))
    net = Net(pages={BASE + "/searchused.aspx?q=CP60123": JSONLD_PAGE})
    monkeypatch.setattr(cdp, "fetch", net.fetch)
    monkeypatch.setattr(cdp.time, "sleep", lambda s: None)
    real = cdp.check_all
    monkeypatch.setattr(cdp, "check_all",
                        lambda cars, **kw: real(cars, fetcher=net.fetch, sleep=lambda s: None, **kw))
    out = tmp_path / "checks.json"
    assert cdp.main([str(tmp_path / "export.csv"), "--config", str(cfg), "--out", str(out),
                     "--exclude", str(tmp_path / "none.txt"), "--yes"]) == 0
    doc = json.loads(out.read_text())
    assert set(doc["checks"]) == sx.KEPT_STOCKS
    asked = " ".join(net.calls)
    assert not any(s in asked for s in sx.FAR_STOCKS | sx.SOLD_STOCKS)
    assert "searchnew.aspx?q=C51234" in asked and "searchnew.aspx?q=DC50111" in asked

    inv_path = tmp_path / "inventory.json"
    assert bi.main([str(tmp_path / "export.csv"), "--config", str(cfg), "--prices", str(out),
                    "--photos", str(tmp_path / "p"), "--exclude", str(tmp_path / "none.txt"),
                    "--out", str(inv_path)]) == 0
    cars = {c["stock"]: c for c in json.loads(inv_path.read_text())["cars"]}
    assert cars["CP60123"]["price"] == 38995 and cars["CP60123"]["carfax_url"] == CARFAX
    assert [s for s, c in cars.items() if "price" in c] == ["CP60123"]
