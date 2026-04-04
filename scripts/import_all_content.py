#!/usr/bin/env python3
"""
One-click import for local or CI.

Default:
  - If rankjee_full.json exists in project root → import_content_bundle (full paths/skills/questions).
  - Else → import every batch*.json with import_questions (sorted).

Usage (from project root):
  python3 scripts/import_all_content.py
  python3 scripts/import_all_content.py --also-batches   # bundle first, then batch*.json
  python3 scripts/import_all_content.py --batches-only
  python3 scripts/import_all_content.py --bundle-only

Requires: DJANGO_SETTINGS_MODULE=rankjee.settings (set below).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rankjee.settings")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import rankjee_full.json and/or batch*.json")
    parser.add_argument(
        "--also-batches",
        action="store_true",
        help="After rankjee_full.json, also run import_questions on each batch*.json",
    )
    parser.add_argument(
        "--batches-only",
        action="store_true",
        help="Only import batch*.json (ignore rankjee_full.json)",
    )
    parser.add_argument(
        "--bundle-only",
        action="store_true",
        help="Only import rankjee_full.json (error if missing)",
    )
    args = parser.parse_args()

    import django

    django.setup()

    from django.core.management import call_command

    bundle = ROOT / "rankjee_full.json"

    if args.batches_only:
        batches = sorted(ROOT.glob("batch*.json"))
        if not batches:
            print("No batch*.json files found.")
            sys.exit(1)
        for f in batches:
            print(f"→ import_questions {f.name}")
            call_command("import_questions", str(f))
        print("Done (batches only).")
        return

    if args.bundle_only:
        if not bundle.is_file():
            print(f"Missing {bundle}")
            sys.exit(1)
        print(f"→ import_content_bundle {bundle.name}")
        call_command("import_content_bundle", str(bundle))
        print("Done (bundle only).")
        return

    # Default
    if bundle.is_file():
        print(f"→ import_content_bundle {bundle.name}")
        call_command("import_content_bundle", str(bundle))
        if args.also_batches:
            for f in sorted(ROOT.glob("batch*.json")):
                print(f"→ import_questions {f.name}")
                call_command("import_questions", str(f))
    else:
        print(f"No {bundle.name}; importing batch*.json only.")
        batches = sorted(ROOT.glob("batch*.json"))
        if not batches:
            print("No batch*.json found either. Create rankjee_full.json (export_content_bundle) or batch files.")
            sys.exit(1)
        for f in batches:
            print(f"→ import_questions {f.name}")
            call_command("import_questions", str(f))

    print("Done.")


if __name__ == "__main__":
    main()
