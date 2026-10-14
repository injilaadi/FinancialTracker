"""Redis cache for the monthly summary.

Design:
- Key `summary:monthly:{months}` holds the JSON response for that window. TTL is a safety net
  (and makes the "last N months" window roll over at month boundaries).
- Any write (import, new transaction) calls invalidate(), which deletes every possible key
  (months is limited to 1..60), so readers never see data older than the last write.
- Redis is an optimization, never a dependency: every error is logged and treated as a miss,
  and after a failure the cache is skipped for a few seconds so a dead Redis does not add a
  timeout to every request.
"""
import json
import logging
import time

import redis.asyncio as aioredis

logger = logging.getLogger("api.cache")

MAX_MONTHS = 60
BACKOFF_SECONDS = 10.0


def summary_key(months: int) -> str:
    return f"summary:monthly:{months}"


class SummaryCache:
    def __init__(self, client: aioredis.Redis, ttl_seconds: int):
        self.client = client
        self.ttl = ttl_seconds
        self._skip_until = 0.0

    @classmethod
    def from_url(cls, url: str, ttl_seconds: int) -> "SummaryCache":
        # Short timeouts: a slow cache is worse than no cache.
        client = aioredis.from_url(url, decode_responses=True, socket_timeout=0.25, socket_connect_timeout=0.25)
        return cls(client, ttl_seconds)

    def _available(self) -> bool:
        return time.monotonic() >= self._skip_until

    def _failed(self, action: str) -> None:
        self._skip_until = time.monotonic() + BACKOFF_SECONDS
        logger.warning("redis %s failed; skipping cache for %.0fs", action, BACKOFF_SECONDS, exc_info=True)

    async def get(self, months: int):
        if not self._available():
            return None
        try:
            raw = await self.client.get(summary_key(months))
        except Exception:  # noqa: BLE001 - any cache problem is just a miss
            self._failed("get")
            return None
        return json.loads(raw) if raw is not None else None

    async def set(self, months: int, payload) -> None:
        if not self._available():
            return
        try:
            await self.client.set(summary_key(months), json.dumps(payload), ex=self.ttl)
        except Exception:  # noqa: BLE001
            self._failed("set")

    async def invalidate(self) -> None:
        # Deliberately NOT gated by the backoff: after a write we always try to clear stale entries.
        try:
            await self.client.delete(*[summary_key(m) for m in range(1, MAX_MONTHS + 1)])
        except Exception:  # noqa: BLE001
            self._failed("invalidate")

    async def close(self) -> None:
        await self.client.aclose()
