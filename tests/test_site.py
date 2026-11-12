"""Static checks on the built pages, scripts and repo (spec acceptance 2, 4, 5, 7 to 9, 13, 14)."""
import json
import re
import shutil
import subprocess
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

import pytest

import build_inventory as bi
import build_site
import build_vcard

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
PAGES = [ROOT / "index.html", ROOT / "car.html"]
SCRIPTS = sorted((ROOT / "assets" / "js").glob("*.js"))
PHONE = build_vcard.e164(CONFIG["phone"])
SMS = build_vcard.e164(CONFIG["sms_phone"])


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def tags(path):
    parser = Tags()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.tags


def built(config):
    return {n: d.decode("utf-8") for n, d in build_site.build(config, ROOT / "src").items()}


# --- R7: pages are build output of the one config file -------------------------------

def test_committed_pages_match_config():
    for name, data in build_site.build(CONFIG, ROOT / "src").items():
        assert (ROOT / name).read_bytes() == data, f"{name} is stale: run tools/build_site.py"


def test_templates_hold_no_contact_details():
    for path in (ROOT / "src").glob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\d{3}[-.\s)]{1,2}\d{3}[-.\s]\d{4}|sms:\+?\d|tel:\+?\d|mailto:\w", text), path.name


def test_changing_the_number_changes_every_link():
    pages = built(dict(CONFIG, phone="913-555-0100", sms_phone="913-555-0100"))
    for name in ("index.html", "car.html", "brenen.vcf"):
        assert "8166011688" not in pages[name] and "816-601-1688" not in pages[name]
        assert "+19135550100" in pages[name]


# --- Acceptance 4: contact links ------------------------------------------------------

@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_contact_links_go_only_to_brenen(page):
    found = 0
    for tag, attrs in tags(page):
        href = attrs.get("href", "")
        scheme = href.split(":", 1)[0].lower() if ":" in href else ""
        if scheme == "sms":
            assert href.startswith(f"sms:{SMS}?&body="), href
        elif scheme == "tel":
            assert href == f"tel:{PHONE}", href
        elif scheme == "mailto":
            assert CONFIG["email"] and href == f"mailto:{CONFIG['email']}", href
        else:
            assert scheme in ("", "https"), f"unexpected link type: {href}"
            continue
        found += 1
    assert found >= 2


def test_no_other_phone_or_email_anywhere():
    allowed = {re.sub(r"\D", "", PHONE)[-10:], re.sub(r"\D", "", SMS)[-10:]}
    files = PAGES + SCRIPTS + [ROOT / "assets/css/site.css", ROOT / "brenen.vcf"]
    for path in files:
        text = urllib.parse.unquote(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"(?<![\d.])(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)", text):
            assert re.sub(r"\D", "", m.group())[-10:] in allowed, f"{path.name}: {m.group()}"
        for m in re.finditer(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
            assert CONFIG["email"] and m.group() == CONFIG["email"], f"{path.name}: {m.group()}"


def test_email_button_follows_the_config():
    assert "mailto:" not in built(dict(CONFIG, email=""))["index.html"]
    assert f'href="mailto:{CONFIG["email"]}"' in (ROOT / "index.html").read_text()
    pages = built(dict(CONFIG, email="someone@example.com"))
    assert 'href="mailto:someone@example.com"' in pages["index.html"]
    assert "EMAIL;TYPE=INTERNET:someone@example.com" in pages["brenen.vcf"]


# --- Acceptance 5 (R1): nothing collected, nothing sent -------------------------------

@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_no_forms_embeds_or_outside_resources(page):
    for tag, attrs in tags(page):
        assert tag not in ("form", "iframe", "embed", "object", "frame", "base"), tag
        if tag == "input":
            assert attrs.get("type") in ("search",), attrs
            assert "name" not in attrs
        if tag == "button":
            assert attrs.get("type") == "button"
        for key in ("src", "srcset", "poster", "action", "formaction", "ping"):
            if key in attrs:
                assert not re.match(r"^(https?:)?//", attrs[key]), f"{tag} {key}={attrs[key]}"
        if tag == "link":
            assert not re.match(r"^(https?:)?//", attrs.get("href", "")), attrs
        if tag == "script":
            assert attrs.get("type") in ("module", "application/json")
            if attrs.get("type") == "module":
                assert attrs.get("src", "").startswith("assets/js/")
        assert not any(k.startswith("on") for k in attrs), f"inline handler on {tag}"
        assert "style" not in attrs
        if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy":
            assert "default-src 'self'" in attrs["content"] and "form-action 'none'" in attrs["content"]
    assert any(t == "meta" and a.get("http-equiv") == "Content-Security-Policy" for t, a in tags(page))


def test_scripts_fetch_only_the_inventory_file_and_store_nothing():
    fetches = []
    for path in SCRIPTS:
        text = path.read_text(encoding="utf-8")
        for banned in ("XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource", "localStorage",
                       "sessionStorage", "indexedDB", "document.cookie", "cookieStore",
                       "navigator.geolocation", "eval(", "innerHTML", "import("):
            assert banned not in text, f"{path.name} uses {banned}"
        assert not re.search(r"https?://", text), f"{path.name} names an outside URL"
        for m in re.finditer(r"^import .*? from '([^']+)'", text, re.M):
            assert m.group(1).startswith("./")
        fetches += re.findall(r"fetch\(([^,)]*)", text)
    assert fetches == ["'inventory/inventory.json'"]


def test_css_loads_only_local_files():
    css = (ROOT / "assets/css/site.css").read_text()
    assert "@import" not in css
    for url in re.findall(r"url\(([^)]+)\)", css):
        assert url.strip("\"'").startswith("../fonts/"), url


def test_fonts_are_self_hosted_open_license():
    fonts = ROOT / "assets" / "fonts"
    assert {p.name for p in fonts.glob("*.woff2")} == {
        "jost-latin-wght-normal.woff2", "marcellus-latin-400-normal.woff2"}
    for name in ("LICENSE-Jost.txt", "LICENSE-Marcellus.txt"):
        assert "SIL Open Font License" in (fonts / name).read_text()


# --- Acceptance 13: no payments, sign-in, favorites, cookie banner --------------------

def test_no_payment_signin_favorite_or_cookie_text():
    pattern = re.compile(r"payment|per month|/mo\b|monthly|financ|lease|\bsale\b|on sale|from \$|"
                         r"sign[ -]?in|log[ -]?in|favorite|wishlist|garage|cookie|subscribe|newsletter|guess", re.I)
    for path in PAGES + SCRIPTS:
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"<meta http-equiv[^>]+>", "", text)
        hit = pattern.search(text) or re.search(r"\bAPR\b", text)
        assert not hit, f"{path.name}: '{hit.group()}'"


def test_price_never_shows_without_its_disclaimer():
    ui = (ROOT / "assets/js/ui.js").read_text()
    block = ui[ui.index("export function priceBlock"):ui.index("export function carFacts")]
    assert "shownPrice(car, inventory, nowMs, config.price_disclaimer)" in block
    assert "config.price_disclaimer })" in block          # fine print under every price
    assert ui.count("formatPrice(") == 1                  # the only place a price is drawn
    assert "price-disclaimer" not in (ROOT / "index.html").read_text()   # empty until Brenen pastes it
    pages = built(dict(CONFIG, price_disclaimer="Fee <b> & tax."))
    assert 'id="price-disclaimer">Fee &lt;b&gt; &amp; tax.</p>' in pages["index.html"]


def test_carfax_button_links_out_only():
    ui = (ROOT / "assets/js/ui.js").read_text()
    assert "if (!isCarfaxUrl(car.carfax_url)) return null;" in ui
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout
    assert not re.search(r"carfax", tracked, re.I)        # no report content in the repo


# --- Acceptance 14: tool links --------------------------------------------------------

def test_outside_links_are_on_the_allow_list_without_tracking():
    allowed = set(CONFIG["link_allow_hosts"])
    seen = set()
    for page in PAGES:
        for tag, attrs in tags(page):
            href = attrs.get("href", "")
            if tag != "a" or not href.startswith("http"):
                continue
            parts = urllib.parse.urlsplit(href)
            assert parts.scheme == "https" and parts.hostname in allowed, href
            assert attrs.get("rel") == "noopener noreferrer" and attrs.get("target") == "_blank"
            for key, _ in urllib.parse.parse_qsl(parts.query):
                assert not build_site.TRACKING_PARAM.match(key), href
            seen.add(parts.hostname)
    assert {"www.nicb.org", "www.nhtsa.gov", "www.fueleconomy.gov", "www.google.com"} <= seen


@pytest.mark.parametrize("url", ["https://tracker.example/x", "http://www.nhtsa.gov/recalls",
                                 "https://www.nhtsa.gov/recalls?utm_source=site",
                                 "https://www.nhtsa.gov/recalls?ref=abc"])
def test_build_rejects_bad_tool_links(url):
    tools = [dict(CONFIG["tools"][2], url=url)]
    with pytest.raises(build_site.ConfigError):
        build_site.build(dict(CONFIG, tools=tools), ROOT / "src")


def test_no_insurance_budget_or_guess_game():
    ids = {t["id"] for t in CONFIG["tools"]}
    assert ids == {"trade", "history", "recalls", "mpg"}


# --- Placeholders: nothing invented ---------------------------------------------------

def test_placeholders_until_brenen_sends_them():
    index = (ROOT / "index.html").read_text()
    assert "assets/img/headshot-placeholder.svg" in built(dict(CONFIG, headshot="", headshot_small=""))["index.html"]
    assert "banner-img" not in built(dict(CONFIG, banner=""))["index.html"]
    assert CONFIG["price_disclaimer"] == ""
    assert CONFIG["bio"] == ""
    bare = built(dict(CONFIG, socials={}))["index.html"]
    assert "social-row" not in bare and ">Follow<" not in bare
    assert (ROOT / "CNAME").read_text() == CONFIG["domain"] + "\n" == "brenenprinzing.com\n"


def test_muse_page_content_is_carried_over():
    index = (ROOT / "index.html").read_text()
    for text in ("Cable Dahmer Cadillac · Kansas City", "1151 W 104th St, Kansas City, MO 64114",
                 "passionate about helping people find their perfect vehicle",
                 "not the main store line", "Test drive hours", "No test drives",
                 "have the vehicle pulled up and ready when you arrive"):
        assert text in index, text
    assert "query=Cable+Dahmer+Cadillac+1151+W+104th+St+Kansas+City+MO+64114" in index
    assert ">Follow</summary>" in index
    for url in ("https://www.facebook.com/61595422784900", "https://www.instagram.com/brenen.cadillackc"):
        assert index.count(f'href="{url}"') == 3          # follow sheet, hero row, contact card


def test_muse_page_removals_stay_removed():
    text = "".join(p.read_text() for p in PAGES + SCRIPTS + [ROOT / "assets/css/site.css"])
    for gone in ("fonts.googleapis.com", "fonts.gstatic.com", "m.me/", "Messenger", "preconnect",
                 "createObjectURL", "execCommand"):
        assert gone not in text, gone


def test_socials_must_be_https():
    with pytest.raises(build_site.ConfigError):
        build_site.build(dict(CONFIG, socials={"X": "javascript:alert(1)"}), ROOT / "src")


def test_page_has_every_section_in_order():
    index = (ROOT / "index.html").read_text()
    marks = ['class="pill"', 'id="top"', 'id="inventory"', 'id="tools"', 'id="hunting"',
             'id="book"', 'id="contact"', 'class="foot"']
    positions = [index.index(m) for m in marks]
    assert positions == sorted(positions)
    for text in ("Value my car", "Save to contacts", "Tools before money moves", "Not seeing it?",
                 "The lot turns over fast.", "Landed this week", "Book a test drive",
                 "Open in Maps", "Get directions",
                 "Inventory and availability change daily. Text to confirm.",
                 "Independent page by Brenen Prinzing, sales consultant. Not an official Cadillac or GM site."):
        assert text in index, text
    hunting = urllib.parse.unquote(re.search(r'href="(sms:[^"]+)">Text Brenen what', index).group(1))
    assert hunting.endswith("Hi Brenen, I'm hunting for:\nYear / Make / Model / Color / Must-haves:")


def test_booking_and_contact_work_without_javascript():
    index = (ROOT / "index.html").read_text()
    assert re.search(r'<a class="btn btn-gold" id="book-cta" href="sms:\+1\d{10}\?&amp;body=[^"]+">Text Brenen to book</a>', index)
    assert "<noscript>" in index and "<noscript>" in (ROOT / "car.html").read_text()


# --- Acceptance 7: vCard --------------------------------------------------------------

def test_vcard_is_valid_3_0_and_matches_config():
    raw = (ROOT / "brenen.vcf").read_bytes()
    assert raw == build_vcard.vcard(CONFIG).encode()
    assert raw.endswith(b"END:VCARD\r\n") and b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    lines = raw.decode().strip().split("\r\n")
    assert lines[0] == "BEGIN:VCARD" and lines[1] == "VERSION:3.0" and lines[-1] == "END:VCARD"
    fields = dict(line.split(":", 1) for line in lines)  # URL value keeps its own colon
    assert fields["FN"] == CONFIG["name"]
    assert fields["N"] == "Prinzing;Brenen;;;"
    assert fields["ORG"] == CONFIG["store"]["name"] and fields["TITLE"] == CONFIG["title"]
    assert fields["TEL;TYPE=CELL,VOICE"] == PHONE == "+18166011688"
    assert fields["EMAIL;TYPE=INTERNET"] == CONFIG["email"]
    assert fields["ADR;TYPE=WORK"] == ";;1151 W 104th St;Kansas City;MO;64114;USA"
    assert fields["URL"] == "https://brenenprinzing.com/"
    assert not any(k.startswith("PHOTO") for k in fields)
    assert all(len(line.encode()) <= 75 for line in lines)


# --- Acceptance 2, 8 (R6): repo hygiene -----------------------------------------------

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def test_no_raw_exports_tracked():
    tracked = git("ls-files").stdout.splitlines()
    assert tracked
    bad = [f for f in tracked if f.lower().endswith((".csv", ".xlsx", ".xls")) or f.startswith("data/raw/")]
    assert not bad, bad
    for path in ("data/raw/export.csv", "data/raw/price_checks.json", "anything.csv", "inventory.xlsx"):
        assert git("check-ignore", "-q", path).returncode == 0, f"{path} is not ignored"


def test_committed_inventory_has_only_allowed_keys():
    inventory = json.loads((ROOT / "inventory" / "inventory.json").read_text())
    bi.validate(inventory)
    text = json.dumps(inventory).lower()
    for key in ("msrp", "payment", "leads", "last_lead", "deals", '"age"'):
        assert key not in text
    if any("price" in c for c in inventory["cars"]):
        assert CONFIG["price_disclaimer"].strip() and inventory.get("prices_checked_at")
    for car in inventory["cars"]:
        for photo in car["photos"]:
            assert (ROOT / photo).is_file() and photo.startswith(f"photos/{car['stock']}/")
        if "carfax_url" in car:
            assert bi.is_carfax_url(car["carfax_url"])


def test_no_store_images_or_brand_assets():
    tracked = git("ls-files").stdout.splitlines()
    images = [f for f in tracked if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))]
    assert all(f.startswith("photos/") or f in ("assets/img/headshot.jpg", "assets/img/headshot-sm.jpg", "assets/img/banner.jpg")
               for f in images), images
    for f in images:                                       # no location data in any committed photo
        assert not bi.photo_info(ROOT / f)["gps"], f
    assert not [f for f in tracked if re.search(r"cadillac|crest|gm[-_]logo", f, re.I)]


# --- Acceptance 9: weight -------------------------------------------------------------

def test_page_weight_under_500_kb_without_photos():
    files = PAGES + SCRIPTS + [ROOT / "assets/css/site.css"]
    files += list((ROOT / "assets/fonts").glob("*.woff2")) + list((ROOT / "assets/img").iterdir())
    total = sum(p.stat().st_size for p in files)
    assert total < 500 * 1024, f"{total / 1024:.0f} KB"


# --- JavaScript unit tests (booking, prices, arrivals) --------------------------------

@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_javascript_unit_tests():
    run = subprocess.run(["node", "--test", "tests/js/lib.test.mjs"], cwd=ROOT,
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-2000:]
