"""Latency of GET /summary/monthly, to compare the cache on vs off.

Run it twice against the same data: once with the cache on, once with CACHE_ENABLED=false
(restart the API in between). Client-side time per request, one connection, sequential.

  python bench_summary.py --url http://localhost:8080 --requests 500 --months 12
"""
import argparse
import statistics
import time
from collections import Counter

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--warmup", type=int, default=20)
    args = parser.parse_args()

    target = f"{args.url}/summary/monthly"
    times, cache_states = [], Counter()
    with httpx.Client(timeout=10) as client:
        for i in range(args.warmup + args.requests):
            started = time.perf_counter()
            response = client.get(target, params={"months": args.months})
            elapsed_ms = (time.perf_counter() - started) * 1000
            response.raise_for_status()
            if i >= args.warmup:
                times.append(elapsed_ms)
                cache_states[response.headers.get("X-Cache", "?")] += 1
    times.sort()
    p = lambda q: times[min(len(times) - 1, int(len(times) * q))]
    print(f"months={args.months} requests={len(times)} rows_in_response={len(response.json())} "
          f"X-Cache={dict(cache_states)}")
    print(f"median {statistics.median(times):.2f} ms   p95 {p(0.95):.2f} ms   p99 {p(0.99):.2f} ms")


if __name__ == "__main__":
    main()
