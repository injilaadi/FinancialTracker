"""SummaryCache unit tests against fakeredis (no real Redis needed)."""
import asyncio

import fakeredis

from app.cache import MAX_MONTHS, SummaryCache, summary_key


def make(server=None, ttl=60):
    server = server or fakeredis.FakeServer()
    return SummaryCache(fakeredis.FakeAsyncRedis(server=server, decode_responses=True), ttl), server


def test_set_get_roundtrip_with_ttl():
    async def go():
        cache, _ = make(ttl=60)
        assert await cache.get(12) is None
        await cache.set(12, [{"month": "2026-10", "category": None, "spent_cents": 5, "transaction_count": 1}])
        assert (await cache.get(12))[0]["spent_cents"] == 5
        assert 0 < await cache.client.ttl(summary_key(12)) <= 60
        assert await cache.get(6) is None  # different window, different key

    asyncio.run(go())


def test_invalidate_removes_every_window():
    async def go():
        cache, _ = make()
        for months in (1, 12, MAX_MONTHS):
            await cache.set(months, [])
        await cache.invalidate()
        assert [await cache.get(m) for m in (1, 12, MAX_MONTHS)] == [None, None, None]

    asyncio.run(go())


def test_redis_down_is_a_miss_and_backs_off():
    async def go():
        server = fakeredis.FakeServer()
        cache, _ = make(server)
        await cache.set(12, [])
        server.connected = False
        assert await cache.get(12) is None  # error treated as a miss, not raised
        assert not cache._available()  # circuit open: further calls skip Redis
        await cache.set(12, [])  # skipped silently
        await cache.invalidate()  # still attempted, still must not raise

    asyncio.run(go())
