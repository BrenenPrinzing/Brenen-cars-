#!/usr/bin/env python3
"""Render index.html, car.html and brenen.vcf from src/*.template.html + site.config.json.

Usage: python tools/build_site.py [--check]

R7: contact details live only in site.config.json. The HTML files are build output,
so the contact links still work with JavaScript off. Run this after any config edit.
--check exits 1 if the committed pages are out of date.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_vcard  # noqa: E402

ROOT = build_vcard.ROOT
PAGES = ("index.html", "car.html")
PLACEHOLDER_HEADSHOT = "assets/img/headshot-placeholder.svg"
OFF = ' class="off"'
SECTIONS = [("#inventory", "Inventory"), ("#tools", "Tools"), ("#hunting", "Not seeing it?"),
            ("#book", "Book a test drive"), ("#contact", "Talk to Brenen")]
# Keys the pages' JavaScript needs. Nothing else from the config is shipped.
PUBLIC_KEYS = ("name", "first_name", "sms_phone", "booking", "price_disclaimer", "messages")
TRACKING_PARAM = re.compile(r"^(utm_|fbclid|gclid|msclkid|mc_|ref$|ref_|aff|affiliate|partner|cid$)", re.I)


class ConfigError(Exception):
    pass


def sms_href(config: dict, body: str) -> str:
    return "sms:" + build_vcard.e164(config["sms_phone"]) + "?&body=" + urllib.parse.quote(body, safe="")


def tel_href(config: dict) -> str:
    return "tel:" + build_vcard.e164(config["phone"])


def check_link(url: str, config: dict, what: str) -> str:
    """Outside links must be https, on the allow-list, with no tracking parameters."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https":
        raise ConfigError(f"{what}: {url} must be an https link")
    if parts.hostname not in config.get("link_allow_hosts", []):
        raise ConfigError(f"{what}: host {parts.hostname} is not in link_allow_hosts")
    for key, _ in urllib.parse.parse_qsl(parts.query, keep_blank_values=True):
        if TRACKING_PARAM.match(key):
            raise ConfigError(f"{what}: {url} carries a tracking parameter ({key})")
    return url


def social_links(config: dict) -> list[tuple[str, str]]:
    out = []
    for label, url in (config.get("socials") or {}).items():
        if not str(url or "").strip():
            continue
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or not parts.hostname:
            raise ConfigError(f"socials.{label}: {url} must be an https link")
        out.append((label, url))
    return out


def ext(url: str, label: str, cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    return f'<a{c} href="{escape(url)}" target="_blank" rel="noopener noreferrer">{escape(label)}</a>'


def context(config: dict) -> dict:
    for key in ("name", "first_name", "title", "phone", "sms_phone", "messages", "booking", "store"):
        if not config.get(key):
            raise ConfigError(f"site.config.json is missing '{key}'")
    for key in ("phone", "sms_phone"):
        if not re.fullmatch(r"\+1\d{10}", build_vcard.e164(config[key])):
            raise ConfigError(f"{key} must be a 10-digit US number")
    store, msgs = config["store"], config["messages"]
    first = config["first_name"]
    headshot = str(config.get("headshot") or "").strip()
    socials = social_links(config)

    social_items = "".join(f"<li>{ext(url, label)}</li>" for label, url in socials)
    follow = ""
    social_row = ""
    if socials:
        follow = ('<details class="sheet"><summary class="btn btn-gold btn-sm">Follow</summary>'
                  f'<div class="sheet-panel"><p class="sheet-title">Follow {escape(first)}</p>'
                  f'<ul class="sheet-links">{social_items}</ul></div></details>')
        social_row = f'<ul class="social-row" aria-label="Social links">{social_items}</ul>'

    menu = "".join(f'<li><a href="index.html{href}">{escape(label)}</a></li>'
                   for href, label in SECTIONS)

    tools = []
    for tool in config.get("tools", []):
        if tool.get("url"):
            link = ext(check_link(tool["url"], config, f"tools.{tool['id']}"), tool["label"],
                       "btn btn-line")
        elif tool.get("action") == "sms_trade":
            link = (f'<a class="btn btn-line" href="{escape(sms_href(config, msgs["trade"]))}">'
                    f'{escape(tool["label"])}</a>')
        elif tool.get("action") == "guess":
            link = f'<button class="btn btn-line" type="button" data-action="guess">{escape(tool["label"])}</button>'
        else:
            raise ConfigError(f"tools.{tool.get('id')}: needs a url or a known action")
        tools.append(f'<article class="tool-card"><h3>{escape(tool["title"])}</h3>'
                     f'<p>{escape(tool["text"])}</p>{link}</article>')

    free_tools = "".join(f"<li>{ext(t['url'], t['title'])}</li>"
                         for t in config.get("tools", []) if t.get("url"))
    extra = "".join(f"<li>{ext(check_link(l['url'], config, 'extra_links'), l['label'])}</li>"
                    for l in config.get("extra_links", []))

    hours = "".join(
        f'<tr{OFF if h["hours"].strip().lower() in ("off", "closed") else ""}>'
        f'<th scope="row">{escape(h["day"])}</th><td>{escape(h["hours"])}</td></tr>'
        for h in config.get("hours", []))

    query = urllib.parse.quote_plus(store.get("address") or store.get("maps_query") or store["name"])
    maps_open = check_link(f"https://www.google.com/maps/search/?api=1&query={query}", config, "maps")
    maps_dir = check_link(f"https://www.google.com/maps/dir/?api=1&destination={query}", config, "maps")

    email = str(config.get("email") or "").strip()
    email_btn = (f'<a class="btn btn-line" href="mailto:{escape(email)}">Email</a>' if email else "")
    disclaimer = str(config.get("price_disclaimer") or "").strip()
    place = " · ".join(x for x in (config["title"], store["name"], store.get("city")) if x)

    public = {k: config[k] for k in PUBLIC_KEYS if k in config}
    config_json = json.dumps(public, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c")

    return {
        "name": escape(config["name"]),
        "first_name": escape(first),
        "role": escape(f'{config["title"]} · {store["name"]}'),
        "place": escape(place),
        "store_name": escape(store["name"]),
        "headshot": escape(headshot or PLACEHOLDER_HEADSHOT),
        "headshot_alt": escape(config["name"] if headshot else "Photo coming soon"),
        "banner": (f'<img class="banner-img" src="{escape(config["banner"])}" alt="">'
                   if str(config.get("banner") or "").strip() else ""),
        "tagline": f'<p class="tagline">{escape(config["tagline"])}</p>' if config.get("tagline") else "",
        "bio": f'<p class="bio">{escape(config["bio"])}</p>' if config.get("bio") else "",
        "phone_display": escape(config["phone"]),
        "sms_general": escape(sms_href(config, msgs["general"])),
        "sms_trade": escape(sms_href(config, msgs["trade"])),
        "sms_hunting": escape(sms_href(config, msgs["hunting"])),
        "sms_book": escape(sms_href(config, msgs["book"])),
        "tel": escape(tel_href(config)),
        "email_btn": email_btn,
        "follow": follow,
        "social_row": social_row,
        "menu": menu,
        "tools": "".join(tools),
        "free_tools": free_tools + extra,
        "hours_label": escape(config.get("hours_label") or "Hours"),
        "hours": hours,
        "address": f'<p class="address">{escape(store["address"])}</p>' if store.get("address") else "",
        "maps_open": escape(maps_open),
        "maps_dir": escape(maps_dir),
        "price_disclaimer": (f'<p class="fine" id="price-disclaimer">{escape(disclaimer)}</p>'
                             if disclaimer else ""),
        "config_json": config_json,
    }


def render(template: str, ctx: dict) -> str:
    def sub(match):
        key = match.group(1)
        if key not in ctx:
            raise ConfigError(f"template uses unknown value '{key}'")
        return ctx[key]
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", sub, template)


def build(config: dict, src: Path) -> dict[str, bytes]:
    ctx = context(config)
    partials = {}
    for name in ("header", "footer"):
        partials[name] = render((src / f"_{name}.html").read_text(encoding="utf-8"), ctx)
    ctx.update(partials)
    out = {}
    for page in PAGES:
        template = (src / page.replace(".html", ".template.html")).read_text(encoding="utf-8")
        out[page] = render(template, ctx).encode("utf-8")
    out["brenen.vcf"] = build_vcard.vcard(config).encode("utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, default=ROOT / "site.config.json")
    ap.add_argument("--src", type=Path, default=ROOT / "src")
    ap.add_argument("--out", type=Path, default=ROOT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    try:
        files = build(json.loads(a.config.read_text(encoding="utf-8")), a.src)
    except ConfigError as e:
        print(f"BUILD FAILED: {e}", file=sys.stderr)
        return 1
    stale = [n for n, data in files.items()
             if not (a.out / n).exists() or (a.out / n).read_bytes() != data]
    if a.check:
        if stale:
            print("Out of date: " + ", ".join(stale) + ". Run python tools/build_site.py",
                  file=sys.stderr)
            return 1
        print("Pages match site.config.json.")
        return 0
    for name, data in files.items():
        (a.out / name).write_bytes(data)
    print("Wrote " + ", ".join(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
