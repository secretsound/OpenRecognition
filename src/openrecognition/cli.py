"""CLI for OpenRecognition."""

import argparse
import json
import sys
from pathlib import Path

import httpx

from openrecognition.config import settings


def _base_url(host: str | None, port: int | None) -> str:
    h = host or settings.host
    p = port or settings.port
    return f"http://{h}:{p}"


def _headers(key: str | None) -> dict:
    h = {}
    if key:
        h["Authorization"] = f"Bearer {key}"
    elif settings.bootstrap_key_path.exists():
        h["Authorization"] = f"Bearer {settings.bootstrap_key_path.read_text().strip()}"
    return h


def cmd_serve(_args):
    from openrecognition.main import run

    run()


def cmd_mcp(_args):
    from openrecognition.integrator.mcp.server import run_stdio

    run_stdio()


def cmd_bootstrap(_args):
    from openrecognition.bootstrap import main as bootstrap_main

    bootstrap_main()


def cmd_keys_create(args):
    url = _base_url(args.host, args.port)
    scopes = args.scopes.split(",") if args.scopes else ["recognize"]
    r = httpx.post(
        f"{url}/v1/auth/keys",
        headers=_headers(args.api_key),
        json={"name": args.name, "scopes": scopes},
        timeout=30,
    )
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2))


def cmd_enroll(args):
    url = _base_url(args.host, args.port)
    files = []
    for p in args.media:
        path = Path(p)
        files.append(
            ("files", (path.name, path.read_bytes(), "application/octet-stream"))
        )
    data = {"type": args.type, "label": args.label}
    if args.species:
        data["species_hint"] = args.species
    r = httpx.post(
        f"{url}/v1/enrollments",
        headers=_headers(args.api_key),
        data=data,
        files=files,
        timeout=120,
    )
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2))


def cmd_models_list(args):
    from openrecognition.config import settings
    from openrecognition.models_download import list_catalog

    pack = args.pack or settings.pack
    rows = list_catalog(pack=pack)
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    print(f"ONNX catalog for pack '{pack}' (weights are downloaded, not in git):\n")
    from openrecognition.models_download import list_categories, list_presets

    for preset in list_presets(pack=pack):
        print(f"  [{preset['tier']}] {preset['label']}: {', '.join(preset['keys'])}")
        print(f"    {preset['description']}\n")
    print("Models by category:\n")
    cat_labels = {c["id"]: c["label"] for c in list_categories()}
    for row in rows:
        label = cat_labels.get(row["category"], row["category"])
        print(f"  {row['key']}  ({label}, {row['tier']})  [{row['source']}]")
        print(f"    {row['use_for']}")
        print(f"    {row['description']}")
        print(f"    {row['url']}\n")


def cmd_models_download(args):
    from openrecognition.config import settings
    from openrecognition.models_download import download_models

    pack = args.pack or settings.pack
    pack_dir = settings.model_packs_dir / pack
    if not pack_dir.is_dir():
        print(f"Pack directory not found: {pack_dir}", file=sys.stderr)
        sys.exit(1)
    keys = args.only if args.only else None
    try:
        results = download_models(pack_dir, keys=keys, force=args.force)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(results, indent=2))
        return
    for r in results:
        print(f"{r['key']}: {r['status']} — {r['message']}")
    print("\nRestart the API or POST /v1/admin/reload if it is already running.")


def cmd_models_status(args):
    from openrecognition.config import settings
    from openrecognition.inference.session_pool import ModelSessionPool
    from openrecognition.models_download import list_catalog

    pack = args.pack or settings.pack
    pack_dir = settings.model_packs_dir / pack
    pool = ModelSessionPool(pack_dir)
    catalog = {r["key"]: r for r in list_catalog(pack=pack)}
    if args.json:
        out = {
            "pack": pack,
            "pack_dir": str(pack_dir),
            "on_disk": pool.list_models(),
            "catalog": catalog,
        }
        print(json.dumps(out, indent=2))
        return
    print(f"Pack: {pack} ({pack_dir})\n")
    for key, row in catalog.items():
        path = pack_dir / row["filename"]
        on_disk = path.exists()
        mark = "yes" if on_disk else "no"
        print(f"  {key}: on disk={mark}  source={row['source']}")
        if not on_disk:
            print(f"    download: openrecognition models download --only {key}")


def cmd_recognize(args):
    url = _base_url(args.host, args.port)
    path = Path(args.file)
    modality = args.modality
    endpoint = f"{url}/v1/recognize/{modality}"
    if modality == "audio" and args.gate_only:
        endpoint = f"{url}/v1/audio/gate"
    params = {}
    if modality == "audio" and not args.gate_only:
        params["mode"] = "full"
    with path.open("rb") as f:
        r = httpx.post(
            endpoint,
            headers=_headers(args.api_key),
            files={"file": (path.name, f, "application/octet-stream")},
            params=params,
            timeout=120,
        )
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2))


def main():
    parser = argparse.ArgumentParser(prog="openrecognition")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--api-key", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="Run API server")
    p_serve.set_defaults(func=cmd_serve)

    p_mcp = sub.add_parser(
        "mcp",
        help="Run MCP stdio server (requires openrecognition serve and [mcp] extra)",
    )
    p_mcp.set_defaults(func=cmd_mcp)

    p_boot = sub.add_parser(
        "bootstrap",
        help="Create the data directory and database (no server)",
    )
    p_boot.set_defaults(func=cmd_bootstrap)

    p_key = sub.add_parser("keys", help="API key management")
    key_sub = p_key.add_subparsers(dest="key_cmd", required=True)
    p_kc = key_sub.add_parser("create")
    p_kc.add_argument("--name", required=True)
    p_kc.add_argument("--scopes", default="recognize")
    p_kc.set_defaults(func=cmd_keys_create)

    p_en = sub.add_parser("enroll", help="Create enrollment")
    p_en.add_argument("--type", required=True, choices=["person", "pet", "object", "sound"])
    p_en.add_argument("--label", required=True)
    p_en.add_argument("--species", default=None)
    p_en.add_argument("--media", nargs="+", required=True)
    p_en.set_defaults(func=cmd_enroll)

    p_rec = sub.add_parser("recognize", help="Run recognition")
    p_rec.add_argument("modality", choices=["audio", "image", "video"])
    p_rec.add_argument("--file", required=True)
    p_rec.add_argument("--gate-only", action="store_true")
    p_rec.set_defaults(func=cmd_recognize)

    p_models = sub.add_parser(
        "models",
        help="List, download, and inspect ONNX weights",
    )
    models_sub = p_models.add_subparsers(dest="models_cmd", required=True)

    p_ml = models_sub.add_parser("list", help="Show download URLs and sources")
    p_ml.add_argument("--pack", default=None, choices=["edge", "standard", "home"])
    p_ml.add_argument("--json", action="store_true")
    p_ml.set_defaults(func=cmd_models_list)

    p_md = models_sub.add_parser("download", help="Download ONNX files into model-packs/")
    p_md.add_argument("--pack", default=None, choices=["edge", "standard", "home"])
    p_md.add_argument(
        "--only",
        action="append",
        default=[],
        help="Model key(s), e.g. silero_vad speaker_embedding",
    )
    p_md.add_argument("--force", action="store_true", help="Re-download existing files")
    p_md.add_argument("--json", action="store_true")
    p_md.set_defaults(func=cmd_models_download)

    p_ms = models_sub.add_parser("status", help="Which catalog models exist on disk")
    p_ms.add_argument("--pack", default=None, choices=["edge", "standard", "home"])
    p_ms.add_argument("--json", action="store_true")
    p_ms.set_defaults(func=cmd_models_status)

    args = parser.parse_args()
    try:
        args.func(args)
    except httpx.HTTPStatusError as e:
        print(e.response.text, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
