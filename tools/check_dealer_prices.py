#!/usr/bin/env python3
"""Read-only build-time check of the dealer website's listed price for each kept car.

Usage:
    python tools/check_dealer_prices.py data/raw/<export.csv|.xlsx>
        [--out data/raw/price_checks.json] [--config site.config.json]
        [--exclude data/exclude.txt] [--delay 2.0] [--yes]

For each stock # the converter would keep, this reads the dealer site's public
listing page and records the listed price, the check time and the free Carfax
report link if the listing shows one. tools/build_inventory.py then publishes a
price only when it equals the export's Pricing to the dollar and the check is under
24 hours old.

Rules it follows (spec C1):
  - Runs only when you run it. Never from a visitor's browser.
  - Honors robots.txt. A robots block, or an unreadable robots.txt, hides the price.
  - Generic user agent, no login, no cookies, at most 1 request every 2 seconds.
  - Any doubt (no listing, two different prices, $0, failed fetch) hides the price.
  - Only the Carfax link is recorded. Report content is never fetched or stored.

Get the GSM's OK and check the dealer site's terms before the first run (spec 9).
Standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_inventory as bi  # noqa: E402

ROOT = bi.ROOT
USER_AGENT = "inventory-price-check/1.0"
MIN_DELAY = 2.0
TIMEOUT = 20
# Words that mean a number is not the selling price.
NOT_SELLING_PRICE = re.compile(r"msrp|retail|was|savings?|discount|rebate|payment|month|/mo|"
                               r"down|lease|apr|fee", re.I)


class Listing:
    """One vehicle block found on a dealer page."""

    def __init__(self):
        self.stock = ""
        self.vin = ""
        self.prices: set[int] = set()
        self.carfax: set[str] = set()


def _money(value) -> int | None:
    s = re.sub(r"[^0-9.]", "", str(value or ""))
    if not s:
        return None
    try:
        n = float(s)
    except ValueError:
        return None
    return int(n) if n == int(n) else None  # cents on a car price means a wrong field


def _carfax_link(href: str) -> str | None:
    href = (href or "").strip()
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith("http://"):
        href = "https://" + href[7:]
    return href if bi.is_carfax_url(href) else None


class _PageParser(HTMLParser):
    """Collects JSON-LD blocks and elements carrying stock/price data attributes."""

    STOCK_ATTRS = ("data-stocknum", "data-stock", "data-stocknumber", "data-stock-number")
    PRICE_ATTRS = ("data-price", "data-internetprice", "data-internet-price",
                   "data-saleprice", "data-sale-price")
    VIN_ATTRS = ("data-vin",)

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.jsonld: list[str] = []
        self._in_jsonld = False
        self._buf: list[str] = []
        self.listings: list[Listing] = []
        self.loose_carfax: list[str] = []
        self.text: list[str] = []
        self._stack: list[tuple[str, Listing | None]] = []  # (tag, listing opened here)

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
            "source", "track", "wbr"}

    def _current(self) -> Listing | None:
        for _, listing in reversed(self._stack):
            if listing:
                return listing
        return None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_jsonld, self._buf = True, []
        opened = None
        stock = next((a[k] for k in self.STOCK_ATTRS if a.get(k)), "")
        if stock:
            opened = Listing()
            opened.stock = stock.strip().upper()
            self.listings.append(opened)
        target = opened or self._current()
        if target:
            for k in self.VIN_ATTRS:
                if a.get(k):
                    target.vin = a[k].strip().upper()
            for k in self.PRICE_ATTRS:
                if k in a:
                    p = _money(a[k])
                    if p:
                        target.prices.add(p)
        if tag == "a":
            link = _carfax_link(a.get("href", ""))
            if link:
                if target:
                    target.carfax.add(link)
                else:
                    self.loose_carfax.append(link)
        if tag not in self.VOID:
            self._stack.append((tag, opened))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID and self._stack:
            self._stack.pop()

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._buf))
            self._in_jsonld = False
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break

    def handle_data(self, data):
        if self._in_jsonld:
            self._buf.append(data)
        elif not any(tag in ("script", "style", "noscript") for tag, _ in self._stack):
            self.text.append(data)


def _walk_jsonld(node, out: list[Listing]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_jsonld(item, out)
        return
    if not isinstance(node, dict):
        return
    types = node.get("@type", [])
    types = [types] if isinstance(types, str) else list(types)
    if any(t in ("Vehicle", "Car", "Product") for t in types):
        listing = Listing()
        listing.stock = str(node.get("sku") or node.get("stockNumber") or "").strip().upper()
        listing.vin = str(node.get("vehicleIdentificationNumber") or "").strip().upper()
        offers = node.get("offers")
        for offer in (offers if isinstance(offers, list) else [offers]):
            if isinstance(offer, dict):
                label = f"{offer.get('name', '')} {offer.get('description', '')}"
                if NOT_SELLING_PRICE.search(label):
                    continue
                p = _money(offer.get("price"))
                if p:
                    listing.prices.add(p)
        if listing.stock or listing.vin:
            out.append(listing)
    for value in node.values():
        if isinstance(value, (dict, list)):
            _walk_jsonld(value, out)


def labeled_price(text: str, label: str, stock: str, vin: str = ""):
    """Price printed right after the dealer's own price label, e.g. "Cable Dahmer Price $35,625".

    That is the number shoppers see, admin fee included. Returns an int, "ambiguous" when
    the page shows two different labeled prices, or None when the label or the car's
    stock # / VIN is not on the page.
    """
    if not label:
        return None
    text = " ".join(text.split())
    upper = text.upper()
    on_page = re.search(rf"(?<![A-Z0-9]){re.escape(stock)}(?![A-Z0-9])", upper) or (vin and vin in upper)
    if not on_page:
        return None
    found = {_money(m) for m in re.findall(rf"{re.escape(label)}\s*:?\s*\$\s*([\d,]+(?:\.\d+)?)", text, re.I)}
    found.discard(None)
    found.discard(0)
    if not found:
        return None
    return found.pop() if len(found) == 1 else "ambiguous"


def parse_listing(html: str, stock: str, vin: str = "", price_label: str = "") -> dict:
    """Find the selling price and Carfax link for one stock # in a dealer page.

    Returns {"status": "ok", "price": int, "carfax_url": str|None} or
    {"status": "not_found" | "no_price" | "ambiguous"}. Never guesses.
    """
    stock, vin = stock.strip().upper(), vin.strip().upper()
    parser = _PageParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # malformed page: treat as not readable
        return {"status": "not_found"}
    found = list(parser.listings)
    for block in parser.jsonld:
        try:
            _walk_jsonld(json.loads(block), found)
        except ValueError:
            continue
    mine = [l for l in found if l.stock == stock or (vin and l.vin == vin)]
    labeled = labeled_price(" ".join(parser.text), price_label, stock, vin)
    if labeled == "ambiguous":
        return {"status": "ambiguous"}
    if not mine and labeled is None:
        return {"status": "not_found"}
    if labeled is not None:
        prices = {labeled}          # the dealer's displayed, fee-inclusive price wins
    else:
        prices = set().union(*(l.prices for l in mine))
        prices.discard(0)
    if not prices:
        return {"status": "no_price"}
    if len(prices) > 1:
        return {"status": "ambiguous"}
    links = set().union(*(l.carfax for l in mine)) if mine else set()
    carfax = None
    if len(links) == 1:
        carfax = links.pop()
    elif not links and all(l.stock == stock or (vin and l.vin == vin) for l in found):
        loose = set(parser.loose_carfax)  # page shows only this car
        carfax = loose.pop() if len(loose) == 1 else None
    return {"status": "ok", "price": prices.pop(), "carfax_url": carfax}


def listing_url(base: str, template: str, stock: str) -> str:
    return base.rstrip("/") + template.replace("{stock}", urllib.parse.quote(stock))


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # read-only GET
        return resp.read(3_000_000).decode("utf-8", "replace")


def load_robots(base: str, fetcher=fetch) -> urllib.robotparser.RobotFileParser | None:
    """Return a parsed robots.txt, or None if it can't be read (treated as a block)."""
    try:
        text = fetcher(base.rstrip("/") + "/robots.txt")
    except urllib.error.HTTPError as e:
        if e.code == 404:  # no robots.txt means no restrictions
            text = ""
        else:
            return None
    except Exception:
        return None
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    return rp


def check_all(cars: list[dict], *, base: str, templates: dict, fetcher=fetch,
              sleep=time.sleep, clock=None, delay: float = MIN_DELAY) -> dict:
    """cars: [{"stock", "condition", "vin"?}]. Returns the price_checks document."""
    clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
    delay = max(delay, MIN_DELAY)
    stamp = lambda: clock().strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    checks = {}
    robots = load_robots(base, fetcher)
    crawl_delay = robots.crawl_delay(USER_AGENT) if robots else None
    if crawl_delay:
        delay = max(delay, float(crawl_delay))
    first = True
    for car in cars:
        stock = car["stock"]
        template = templates["new"] if car.get("condition") in ("New", "Demo") else templates["used"]
        url = listing_url(base, template, stock)
        if robots is None:
            checks[stock] = {"status": "robots_unreadable", "checked_at": stamp()}
            continue
        if not robots.can_fetch(USER_AGENT, url):
            checks[stock] = {"status": "robots_blocked", "checked_at": stamp()}
            continue
        if not first:
            sleep(delay)
        first = False
        try:
            html = fetcher(url)
        except Exception as e:
            checks[stock] = {"status": "fetch_failed", "checked_at": stamp(),
                             "detail": type(e).__name__}
            continue
        result = parse_listing(html, stock, car.get("vin", ""), templates.get("price_label", ""))
        entry = {"status": result["status"], "checked_at": stamp(), "url": url}
        if result["status"] == "ok":
            entry["price"] = result["price"]
            if result.get("carfax_url"):
                entry["carfax_url"] = result["carfax_url"]
        checks[stock] = entry
    return {"source": base, "generated_at": stamp(), "checks": checks}


def print_report(doc: dict, export_prices: dict, out=None) -> None:
    out = out or sys.stdout
    ok = match = 0
    problems = []
    for stock, c in sorted(doc["checks"].items()):
        if c["status"] != "ok":
            problems.append(f"  {stock}: {c['status'].replace('_', ' ')}")
            continue
        ok += 1
        mine = export_prices.get(stock, 0)
        if mine == c["price"]:
            match += 1
        else:
            problems.append(f"  {stock}: mismatch (export ${mine:,} vs site ${c['price']:,})")
    print(f"Checked {len(doc['checks'])} cars: {ok} listed with a price, {match} match "
          f"the export exactly.", file=out)
    if problems:
        print("Price will be hidden (\"Text me for price\") for:", file=out)
        print("\n".join(problems), file=out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("export", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "raw" / "price_checks.json")
    ap.add_argument("--config", type=Path, default=ROOT / "site.config.json")
    ap.add_argument("--exclude", type=Path, default=ROOT / "data" / "exclude.txt")
    ap.add_argument("--delay", type=float, default=MIN_DELAY,
                    help="seconds between requests (minimum 2)")
    ap.add_argument("--yes", action="store_true",
                    help="confirm the GSM has OK'd read-only checks of the dealer site")
    a = ap.parse_args(argv)
    try:
        rows = bi.read_export(a.export)
        config = json.loads(a.config.read_text(encoding="utf-8"))
    except (bi.BuildError, OSError, ValueError) as e:
        print(f"CHECK FAILED: {e}", file=sys.stderr)
        return 1
    dealer = config.get("dealer_site") or {}
    base = str(dealer.get("base_url") or "")
    if not base.startswith("https://"):
        print("CHECK FAILED: dealer_site.base_url is missing in site.config.json.",
              file=sys.stderr)
        return 1
    if not a.yes:
        print(f"This reads listing pages on {base} (read-only, 1 request every "
              f"{max(a.delay, MIN_DELAY):g} seconds).\nSpec 9: get the GSM's OK and check the "
              f"site's terms first. Run again with --yes once you have it.")
        return 2
    kept, _ = bi.filter_rows(rows, bi.load_exclude(a.exclude))
    cars = [{"stock": r["stock"], "condition": bi.condition_for(r["stock"]),
             "vin": r.get("vin", "")} for r in kept]
    templates = {"used": dealer.get("used_path", "/searchused.aspx?q={stock}"),
                 "new": dealer.get("new_path", "/searchnew.aspx?q={stock}"),
                 "price_label": dealer.get("price_label", "")}
    doc = check_all(cars, base=base, templates=templates, delay=a.delay)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print_report(doc, {r["stock"]: bi.to_int(r.get("pricing")) for r in kept})
    print(f"\nWrote {a.out} (gitignored). Now run tools/build_inventory.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
