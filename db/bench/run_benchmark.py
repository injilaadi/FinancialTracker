"""Before/after timings for the dashboard queries on synthetic data.

Creates a THROWAWAY database (default: financetracker_bench), loads the schema, generates
synthetic transactions, then times each query in three stages:
  1. baseline          (no secondary indexes)
  2. + index           (db/indexes.sql)
  3. + materialized view (db/matview.sql), for the aggregation queries

Timing = server-side "Execution Time" from EXPLAIN (ANALYZE), median of N runs after one
warm-up run. Results depend on your hardware and Postgres settings, so run it on YOUR
machine (e.g. against the Compose database) before quoting any number.

Usage:
  python run_benchmark.py --admin-url postgres://postgres:postgres@localhost:5432/postgres \
      --rows 1000000 --runs 7 --out results.json
"""
import argparse
import asyncio
import json
import os
import re
import statistics
import time
from urllib.parse import urlsplit, urlunsplit

import asyncpg

HERE = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.dirname(HERE)
AS_OF = "2026-09-30"


def read(*parts: str) -> str:
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


def load_queries() -> dict[str, str]:
    queries, name, lines = {}, None, []
    for line in read(HERE, "queries.sql").splitlines():
        match = re.match(r"--\s*name:\s*(\w+)", line)
        if match:
            if name:
                queries[name] = "\n".join(lines).strip().rstrip(";")
            name, lines = match.group(1), []
        elif name and not line.startswith("--"):
            lines.append(line)
    if name:
        queries[name] = "\n".join(lines).strip().rstrip(";")
    return queries


def walk(plan: dict, found: list[str]) -> None:
    node = plan["Node Type"] + (f" on {plan['Index Name']}" if "Index Name" in plan else "")
    found.append(node)
    for child in plan.get("Plans", []):
        walk(child, found)


async def time_query(conn, sql: str, args: list, runs: int) -> dict:
    explain = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql
    await conn.fetch(explain, *args)  # warm-up (fills caches), discarded
    times, nodes = [], []
    for _ in range(runs):
        raw = await conn.fetchval(explain, *args)
        doc = json.loads(raw) if isinstance(raw, str) else raw
        times.append(doc[0]["Execution Time"])
        nodes = []
        walk(doc[0]["Plan"], nodes)
    return {"median_ms": round(statistics.median(times), 3), "min_ms": round(min(times), 3),
            "max_ms": round(max(times), 3), "plan": nodes}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--admin-url", required=True, help="URL of any existing database (used to create the benchmark DB)")
    parser.add_argument("--db-name", default="financetracker_bench")
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--runs", type=int, default=7)
    parser.add_argument("--out")
    args = parser.parse_args()

    parts = urlsplit(args.admin_url)
    bench_url = urlunsplit(parts._replace(path="/" + args.db_name))
    admin = await asyncpg.connect(args.admin_url)
    await admin.execute(f'DROP DATABASE IF EXISTS "{args.db_name}"')
    await admin.execute(f'CREATE DATABASE "{args.db_name}"')
    await admin.close()

    conn = await asyncpg.connect(bench_url, command_timeout=3600)
    version = await conn.fetchval("SHOW server_version")
    await conn.execute(read(DB_DIR, "init.sql"))

    started = time.perf_counter()
    await conn.execute(read(HERE, "generate_synthetic.sql").replace("__ROWS__", str(args.rows)))
    generate_s = time.perf_counter() - started
    await conn.execute("ANALYZE")
    rows = await conn.fetchval("SELECT count(*) FROM transactions")
    account = await conn.fetchval("SELECT min(id) FROM accounts WHERE institution = 'synthetic'")
    account_rows = await conn.fetchval("SELECT count(*) FROM transactions WHERE account_id = $1", account)
    print(f"Postgres {version}; {rows:,} synthetic rows (generated in {generate_s:.1f}s); "
          f"benchmark account {account} has {account_rows:,} rows")

    queries = load_queries()
    params = {
        "q1_monthly_by_category": [account, "2025-10-01"],
        "q2_recent_transactions": [account],
        "q3_top_categories_one_month": [account, "2026-06-01", "2026-07-01"],
    }
    mv_params = {
        "q1_monthly_by_category": ("q1_monthly_by_category_mv", [account, "2025-10-01"]),
        "q3_top_categories_one_month": ("q3_top_categories_one_month_mv", [account, "2026-06-01"]),
    }
    from datetime import date
    def typed(values):  # asyncpg wants real date objects for $n::date parameters
        return [date.fromisoformat(v) if isinstance(v, str) else v for v in values]

    def canon(records):  # comparable form of a result set (NULL category sorts as '')
        return sorted((tuple(r) for r in records), key=lambda r: tuple("" if v is None else str(v) for v in r))

    results: dict[str, dict] = {name: {} for name in params}
    reference = {}

    async def run_stage(stage: str, include_mv: bool) -> None:
        for name, values in params.items():
            results[name][stage] = await time_query(conn, queries[name], typed(values), args.runs)
            if stage == "baseline" and name in mv_params:
                reference[name] = canon(await conn.fetch(queries[name], *typed(values)))
        if include_mv:
            for name, (mv_name, values) in mv_params.items():
                results[name]["matview"] = await time_query(conn, queries[mv_name], typed(values), args.runs)
                got = canon(await conn.fetch(queries[mv_name], *typed(values)))
                if name == "q1_monthly_by_category":
                    assert got == reference[name], "materialized view result differs from base query (q1)"
                else:
                    assert dict(got) == dict(reference[name]), "materialized view result differs from base query (q3)"

    await run_stage("baseline", include_mv=False)

    started = time.perf_counter()
    await conn.execute(read(DB_DIR, "indexes.sql"))
    index_build_s = time.perf_counter() - started
    await conn.execute("VACUUM ANALYZE transactions")  # visibility map, needed for index-only scans
    await run_stage("indexed", include_mv=False)

    started = time.perf_counter()
    await conn.execute(read(DB_DIR, "matview.sql"))
    matview_build_s = time.perf_counter() - started
    await conn.execute("ANALYZE monthly_category_spend")
    await run_stage("indexed", include_mv=True)  # re-times indexed too; keeps the later of the two
    started = time.perf_counter()
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_category_spend")
    refresh_s = time.perf_counter() - started

    sizes = {
        "table_mb": await conn.fetchval("SELECT pg_relation_size('transactions') / 1048576"),
        "index_mb": await conn.fetchval("SELECT pg_relation_size('idx_transactions_account_posted') / 1048576"),
        "matview_rows": await conn.fetchval("SELECT count(*) FROM monthly_category_spend"),
        "matview_kb": await conn.fetchval("SELECT pg_total_relation_size('monthly_category_spend') / 1024"),
    }
    await conn.close()

    cpus = os.cpu_count()
    print(f"\nMedian of {args.runs} runs (ms, server-side EXPLAIN ANALYZE); lower is better\n")
    print(f"| query | baseline | + index | + materialized view |")
    print("|---|---:|---:|---:|")
    for name, stages in results.items():
        base = stages["baseline"]["median_ms"]
        idx = stages["indexed"]["median_ms"]
        mv = stages.get("matview", {}).get("median_ms")
        mv_text = f"{mv:.2f} ({base / mv:.0f}x)" if mv else "n/a"
        print(f"| {name} | {base:.2f} | {idx:.2f} ({base / idx:.1f}x) | {mv_text} |")
    print("\nPlans:")
    for name, stages in results.items():
        for stage, data in stages.items():
            print(f"  {name:<30} {stage:<9} {' > '.join(data['plan'])}")
    print(f"\nCosts: index build {index_build_s:.1f}s, matview build {matview_build_s:.1f}s, "
          f"matview refresh {refresh_s:.2f}s; {sizes}")
    print(f"Environment: Postgres {version}, {cpus} CPUs, {rows:,} rows")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump({"postgres": version, "cpus": cpus, "rows": rows, "runs": args.runs, "results": results,
                       "index_build_s": index_build_s, "matview_build_s": matview_build_s,
                       "matview_refresh_s": refresh_s, "sizes": sizes}, handle, indent=2, default=str)


if __name__ == "__main__":
    asyncio.run(main())
