"""ctx.cache wrapper for Bing Webmaster's panel reads.

The sidebar (site list) and workspace (queries/pages/traffic) panels used to
call ssl.bing.com live on every single render/pagination click. Bing's own
Search Performance data is aggregated in weekly buckets (see bing_api.py's
GetQueryStats/GetPageStats), so it changes at most once a day — caching it
for a couple of minutes costs zero real freshness while making repeat panel
opens near-instant instead of 1-3 sequential live HTTP round-trips.

ctx.cache TTL is platform-capped to [5, 300]s (I-CACHE-TTL-CAP-300S).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field


class CachedBingPayload(BaseModel):
    """Generic ctx.cache envelope — one JSON-serialisable payload per call."""
    data: Any = Field(default_factory=list)


SITES_CACHE_TTL = 120       # verified-sites list rarely changes
ANALYTICS_CACHE_TTL = 240   # queries/pages/traffic — Bing buckets weekly anyway


def _cache_key(scope: str, api_key: str, extra: dict | None = None) -> str:
    # Hash the api_key itself rather than storing it in the clear key — it's
    # a live credential, keep it out of any cache-key logs/telemetry.
    parts = {"scope": scope, "key": hashlib.sha256(api_key.encode()).hexdigest()[:16], "extra": extra or {}}
    digest = hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:32]
    return f"bing:{digest}"


async def cached_call(ctx, scope: str, api_key: str, extra: dict | None,
                       ttl_seconds: int, fetcher: Callable[[], Awaitable[Any]]) -> Any:
    """Cache one JSON-serialisable payload behind ctx.cache.get_or_fetch().

    Falls back to calling the fetcher directly if ctx.cache is unavailable
    (e.g. a minimal test/mock Context) so callers never have to special-case it.
    """
    key = _cache_key(scope, api_key, extra)

    async def _fetch() -> CachedBingPayload:
        return CachedBingPayload(data=await fetcher())

    try:
        cache = ctx.cache
    except Exception:
        return await fetcher()

    result = await cache.get_or_fetch(key, CachedBingPayload, _fetch, ttl_seconds=ttl_seconds)
    return result.data
