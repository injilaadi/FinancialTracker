"""Client for the ML service, with bounded concurrency."""
import asyncio

import httpx


async def call_ml(client: httpx.AsyncClient, ml_url: str, descriptions: list[str]) -> list[dict]:
    response = await client.post(f"{ml_url}/categorize", json={"descriptions": descriptions})
    response.raise_for_status()
    predictions = response.json()["predictions"]
    if len(predictions) != len(descriptions):
        raise ValueError(
            f"ml service returned {len(predictions)} predictions for {len(descriptions)} descriptions"
        )
    return predictions


async def categorize_all(
    client: httpx.AsyncClient,
    ml_url: str,
    descriptions: list[str],
    workers: int,
    batch_size: int,
) -> tuple[list[dict | None], Exception | None]:
    """Send descriptions to the ML service in batches, at most `workers` at a time.

    Results keep the input order. If a batch fails, its entries stay None (the rows are
    saved uncategorized) and the first error is returned alongside the results.

    workers=1 is the sequential baseline; raise IMPORT_WORKERS to measure the speedup.
    """
    workers = max(1, workers)
    batch_size = max(1, batch_size)

    results: list[dict | None] = [None] * len(descriptions)
    first_error: Exception | None = None
    semaphore = asyncio.Semaphore(workers)  # the "bounded pool": only N calls in flight

    async def run_batch(start: int, end: int) -> None:
        nonlocal first_error
        async with semaphore:
            try:
                predictions = await call_ml(client, ml_url, descriptions[start:end])
            except Exception as exc:  # noqa: BLE001 - one bad batch must not abort the import
                if first_error is None:
                    first_error = exc
                return
        results[start:end] = predictions  # each batch owns a distinct slice

    batches = [
        run_batch(start, min(start + batch_size, len(descriptions)))
        for start in range(0, len(descriptions), batch_size)
    ]
    await asyncio.gather(*batches)
    return results, first_error
