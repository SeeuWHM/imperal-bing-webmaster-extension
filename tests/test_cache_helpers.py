"""cache_helpers.cached_call — unit tests, no network."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from cache_helpers import cached_call


class _FakeCacheClient:
    def __init__(self):
        self.store: dict[str, object] = {}
        self.fetch_calls = 0

    async def get_or_fetch(self, key, model, fetcher, ttl_seconds=60):
        if key in self.store:
            return self.store[key]
        self.fetch_calls += 1
        value = await fetcher()
        self.store[key] = value
        return value


def _ctx_with_cache():
    ctx = SimpleNamespace()
    ctx.cache = _FakeCacheClient()
    return ctx


class _NoCacheContext:
    @property
    def cache(self):
        raise RuntimeError("no cache available")


@pytest.mark.asyncio
async def test_cached_call_fetches_once_then_serves_from_cache():
    ctx = _ctx_with_cache()
    calls = []

    async def fetcher():
        calls.append(1)
        return [{"query": "hello", "clicks": 5}]

    first = await cached_call(ctx, "queries", "key-abc", {"site_url": "https://a.com"}, 60, fetcher)
    second = await cached_call(ctx, "queries", "key-abc", {"site_url": "https://a.com"}, 60, fetcher)

    assert first == [{"query": "hello", "clicks": 5}]
    assert second == first
    assert len(calls) == 1
    assert ctx.cache.fetch_calls == 1


@pytest.mark.asyncio
async def test_cached_call_keys_differ_per_api_key_and_extra():
    ctx = _ctx_with_cache()

    async def fetcher_a():
        return ["A"]

    async def fetcher_b():
        return ["B"]

    r1 = await cached_call(ctx, "pages", "key-1", {"site_url": "https://a.com"}, 60, fetcher_a)
    r2 = await cached_call(ctx, "pages", "key-2", {"site_url": "https://a.com"}, 60, fetcher_b)
    r3 = await cached_call(ctx, "pages", "key-1", {"site_url": "https://b.com"}, 60, fetcher_b)

    assert r1 == ["A"]
    assert r2 == ["B"]
    assert r3 == ["B"]
    assert ctx.cache.fetch_calls == 3


@pytest.mark.asyncio
async def test_cached_call_falls_back_when_cache_unavailable():
    ctx = _NoCacheContext()
    calls = []

    async def fetcher():
        calls.append(1)
        return ["fresh"]

    result = await cached_call(ctx, "traffic", "key-x", None, 60, fetcher)
    assert result == ["fresh"]
    assert len(calls) == 1
