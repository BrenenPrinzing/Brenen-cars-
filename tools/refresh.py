#!/usr/bin/env python3
"""One command to refresh the site's inventory from a DriveCentric export.

Usage:
    python tools/refresh.py data/raw/<export.csv|.xlsx> [--dealer-check]

Steps:
  1. With --dealer-check: read each kept car's listing on the dealer site (read-only,
     needs the GSM's OK). Verifies prices, picks up Carfax links, and finds cars the
     dealer site no longer lists so they can be dropped.
  2. Build inventory/inventory.json.
  3. Confirm the pages still match site.config.json.

It never commits or pushes. Review the report, then commit inventory/inventory.json.
A scheduled job can run this same command and commit the result.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_inventory  # noqa: E402
import build_site  # noqa: E402
import check_dealer_prices  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("export", type=Path)
    ap.add_argument("--dealer-check", action="store_true",
                    help="also check the dealer site (confirms the GSM has OK'd it)")
    ap.add_argument("--root", type=Path, default=build_inventory.ROOT, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    root = a.root
    prices = root / "data" / "raw" / "price_checks.json"
    common = ["--config", str(root / "site.config.json"), "--exclude", str(root / "data" / "exclude.txt")]
    if a.dealer_check:
        print("== Checking the dealer site ==")
        code = check_dealer_prices.main([str(a.export), "--out", str(prices), "--yes", *common])
        if code:
            print("Dealer check failed. Inventory was not rebuilt.", file=sys.stderr)
            return code
    else:
        print("Dealer site not checked (no --dealer-check): prices stay hidden unless a check "
              "from the last 24 hours exists, and sold cars are only caught by the export.")
    print("\n== Building inventory ==")
    code = build_inventory.main([str(a.export), "--out", str(root / "inventory" / "inventory.json"),
                                 "--photos", str(root / "photos"), "--prices", str(prices), *common])
    if code:
        return code
    print("\n== Checking pages ==")
    code = build_site.main(["--check", "--config", str(root / "site.config.json"),
                            "--src", str(root / "src"), "--out", str(root)])
    if code == 0:
        print("\nDone. Review the report above, then commit inventory/inventory.json and push.")
    return code


if __name__ == "__main__":
    sys.exit(main())
