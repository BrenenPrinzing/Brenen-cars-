#!/usr/bin/env python3
"""Write brenen.vcf (vCard 3.0) from site.config.json.

Usage: python tools/build_vcard.py [--config site.config.json] [--out brenen.vcf]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def e164(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return "+" + digits if digits else ""


def esc(text: str) -> str:
    return (str(text or "").replace("\\", "\\\\").replace("\n", "\\n")
            .replace(",", "\\,").replace(";", "\\;"))


def domain_set(config: dict) -> bool:
    d = str(config.get("domain") or "").strip()
    return bool(d) and d != "DOMAIN_TBD"


def vcard(config: dict) -> str:
    name = str(config["name"]).strip()
    first, _, last = name.partition(" ")
    lines = ["BEGIN:VCARD", "VERSION:3.0",
             f"N:{esc(last)};{esc(first)};;;",
             f"FN:{esc(name)}"]
    store = config.get("store") or {}
    if store.get("name"):
        lines.append(f"ORG:{esc(store['name'])}")
    if config.get("title"):
        lines.append(f"TITLE:{esc(config['title'])}")
    phone, sms = e164(config.get("phone")), e164(config.get("sms_phone"))
    if phone:
        lines.append(f"TEL;TYPE=CELL,VOICE:{phone}")
    if sms and sms != phone:
        lines.append(f"TEL;TYPE=CELL,TEXT:{sms}")
    if str(config.get("email") or "").strip():
        lines.append(f"EMAIL;TYPE=INTERNET:{esc(config['email'].strip())}")
    if domain_set(config):
        lines.append(f"URL:https://{config['domain'].strip()}/")
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, default=ROOT / "site.config.json")
    ap.add_argument("--out", type=Path, default=ROOT / "brenen.vcf")
    a = ap.parse_args(argv)
    config = json.loads(a.config.read_text(encoding="utf-8"))
    a.out.write_bytes(vcard(config).encode("utf-8"))
    print(f"Wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
