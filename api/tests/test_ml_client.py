import asyncio
import json

import httpx

from app.ml_client import categorize_all


def _predictions(descriptions):
    return [
        {"description": d, "category": "Cat-" + d, "source": "rules", "matched": None}
        for d in descriptions
    ]


def _run(handler, descriptions, workers, batch_size):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await categorize_all(client, "http://ml.test", descriptions, workers, batch_size)

    return asyncio.run(go())


def test_order_is_preserved_across_workers():
    async def handler(request):
        await asyncio.sleep(0.01)
        return httpx.Response(200, json={"predictions": _predictions(json.loads(request.content)["descriptions"])})

    descriptions = [f"d{i:02d}" for i in range(25)]
    results, error = _run(handler, descriptions, workers=4, batch_size=3)
    assert error is None
    assert [r["category"] for r in results] == ["Cat-" + d for d in descriptions]


def test_concurrency_is_bounded_and_really_concurrent():
    state = {"inflight": 0, "peak": 0}

    async def handler(request):
        state["inflight"] += 1
        state["peak"] = max(state["peak"], state["inflight"])
        await asyncio.sleep(0.02)
        state["inflight"] -= 1
        return httpx.Response(200, json={"predictions": _predictions(json.loads(request.content)["descriptions"])})

    descriptions = [f"d{i:02d}" for i in range(30)]

    _run(handler, descriptions, workers=3, batch_size=1)
    assert 1 < state["peak"] <= 3  # concurrent, but never more than `workers`

    state.update(inflight=0, peak=0)
    _run(handler, descriptions, workers=1, batch_size=1)
    assert state["peak"] == 1  # workers=1 is the sequential baseline


def test_failed_batch_stays_uncategorized_and_others_succeed():
    async def handler(request):
        descriptions = json.loads(request.content)["descriptions"]
        if "d00" in descriptions:
            return httpx.Response(500)
        return httpx.Response(200, json={"predictions": _predictions(descriptions)})

    descriptions = [f"d{i:02d}" for i in range(9)]
    results, error = _run(handler, descriptions, workers=2, batch_size=3)
    assert error is not None
    assert results[:3] == [None, None, None]
    assert [r["category"] for r in results[3:]] == ["Cat-" + d for d in descriptions[3:]]


def test_wrong_prediction_count_is_an_error():
    async def handler(request):
        return httpx.Response(200, json={"predictions": []})

    results, error = _run(handler, ["a", "b"], workers=1, batch_size=2)
    assert error is not None
    assert results == [None, None]
