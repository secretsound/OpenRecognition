#!/usr/bin/env python3
"""CLI wrapper for model downloads. Prefer: openrecognition models download"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from openrecognition.models_download import (
    MODEL_CATALOG,
    download_models,
    list_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
PACKS = ROOT / "model-packs"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download ONNX weights into model-packs/<pack>/",
        epilog="Same as: openrecognition models download",
    )
    parser.add_argument("--pack", default="edge", choices=["edge", "standard", "home"])
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Model keys (default: all for this pack)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print catalog and exit",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if file exists",
    )
    args = parser.parse_args()

    if args.list:
        rows = list_catalog(pack=args.pack)
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            print(f"Models for pack '{args.pack}' (not stored in git):\n")
            for row in rows:
                print(f"  {row['key']}")
                print(f"    file:   {row['filename']}")
                print(f"    source: {row['source']} — {row['url']}")
                print(f"    note:   {row['description']} ({row['license']})")
                print()
        return

    pack_dir = PACKS / args.pack
    if not pack_dir.is_dir():
        raise SystemExit(f"Unknown pack directory: {pack_dir}")

    if args.only:
        unknown = set(args.only) - {m.key for m in MODEL_CATALOG}
        if unknown:
            raise SystemExit(f"Unknown keys: {', '.join(sorted(unknown))}")

    keys = args.only or None
    try:
        results = download_models(pack_dir, keys=keys, force=args.force)
    except ValueError as e:
        raise SystemExit(str(e)) from e

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{r['key']}: {r['status']} — {r['message']}")
            if r["status"] == "downloaded":
                print(f"  {r['path']}")
        print("\nDone. Check GET /health or: openrecognition models status")


if __name__ == "__main__":
    main()
