#!/usr/bin/env python3
"""Simple latency benchmark (run against a live server)."""

import argparse
import statistics
import time

import httpx

from tests.helpers import wav_bytes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--key", required=True)
    parser.add_argument("--n", type=int, default=20)
    args = parser.parse_args()
    headers = {"Authorization": f"Bearer {args.key}"}
    data = wav_bytes()
    times = []
    for _ in range(args.n):
        t0 = time.perf_counter()
        r = httpx.post(
            f"{args.url}/v1/audio/gate",
            headers=headers,
            files={"file": ("t.wav", data, "audio/wav")},
            timeout=30,
        )
        r.raise_for_status()
        times.append((time.perf_counter() - t0) * 1000)
    print(f"gate p50={statistics.median(times):.1f}ms p95={sorted(times)[int(len(times)*0.95)]:.1f}ms")


if __name__ == "__main__":
    main()
