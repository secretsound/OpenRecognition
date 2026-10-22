#!/usr/bin/env python3
"""CLI wrapper for model downloads. Prefer: openrecognition models download"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from openrecognition.config import settings
from openrecognition.models_download import (
    MODEL_CATALOG,
    download_models,
    list_catalog,
)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download ONNX weights into the models directory",
        epilog="Same as: openrecognition models download",
    )
    parser.add_argument(
        "--dir",
        default=str(settings.models_dir),
        help="Where to save the files (default: OPENRECOGNITION_MODELS_DIR or ./models)",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Model keys (default: the whole catalog)",
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
        rows = list_catalog()
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            print("Models (not stored in git):\n")
            for row in rows:
                print(f"  {row['key']}")
                print(f"    file:   {row['filename']}")
                print(f"    source: {row['source']} — {row['url']}")
                print(f"    note:   {row['description']} ({row['license']})")
                print()
        return

    model_dir = Path(args.dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    if args.only:
        unknown = set(args.only) - {m.key for m in MODEL_CATALOG}
        if unknown:
            raise SystemExit(f"Unknown keys: {', '.join(sorted(unknown))}")

    keys = args.only or None
    try:
        results = download_models(model_dir, keys=keys, force=args.force)
    except ValueError as e:
        raise SystemExit(str(e)) from e

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{r['key']}: {r['status']} — {r['message']}")
            if r["status"] == "downloaded":
                print(f"         {r.get('url', '')}")


if __name__ == "__main__":
    main()
