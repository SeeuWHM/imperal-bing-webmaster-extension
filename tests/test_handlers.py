"""Unit tests for handlers_accounts.py + handlers_data.py — no network.

Follows the platform convention: monkeypatch bing_get on the HANDLER module
(where it's imported and called), never on bing_api (where it's merely
defined) — patching the wrong one lets the real function run and hit the
network during tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from imperal_sdk.testing import MockContext
from imperal_sdk.testing.mock_secrets import MockSecretStore

import handlers_accounts
import handlers_data
from params import AccountLabelParams, EmptyParams, SaveKeyParams, SiteUrlParams


def _ctx(initial: dict | None = None) -> MockContext:
    ctx = MockContext(user_id="tenant-abc-123")
    ctx.secrets = MockSecretStore(initial or {})
    return ctx


# ─── connection_status ──────────────────────────────────────────────────── #

@pytest.mark.asyncio
async def test_connection_status_not_connected():
    ctx = _ctx()
    result = await handlers_accounts.fn_connection_status(ctx, EmptyParams())
    assert result.status == "success"
    assert result.data.connected is False


@pytest.mark.asyncio
async def test_connection_status_connected(monkeypatch):
    ctx = _ctx()

    async def fake_bing_get(ctx, key, method, params=None):
        return {"d": [{"Url": "http://example.com/", "IsVerified": True}]}

    monkeypatch.setattr(handlers_accounts, "bing_get", fake_bing_get)
    await handlers_accounts.fn_save_bing_key(ctx, SaveKeyParams(bing_api_key="key-1", label=""))

    result = await handlers_accounts.fn_connection_status(ctx, EmptyParams())
    assert result.status == "success"
    assert result.data.connected is True
    assert result.data.masked_key == "••••ey-1"


# ─── save_bing_key ───────────────────────────────────────────────────────── #

@pytest.mark.asyncio
async def test_save_bing_key_rejects_empty():
    ctx = _ctx()
    result = await handlers_accounts.fn_save_bing_key(ctx, SaveKeyParams(bing_api_key="   ", label=""))
    assert result.status == "error"


@pytest.mark.asyncio
async def test_save_bing_key_rejects_invalid_key(monkeypatch):
    ctx = _ctx()

    async def fake_bing_get(ctx, key, method, params=None):
        raise RuntimeError("Bing Webmaster API error (HTTP 400): InvalidApiKey [code 3]")

    monkeypatch.setattr(handlers_accounts, "bing_get", fake_bing_get)
    result = await handlers_accounts.fn_save_bing_key(ctx, SaveKeyParams(bing_api_key="bad-key", label=""))
    assert result.status == "error"
    assert "InvalidApiKey" in result.error


@pytest.mark.asyncio
async def test_save_bing_key_success_adds_account(monkeypatch):
    ctx = _ctx()

    async def fake_bing_get(ctx, key, method, params=None):
        return {"d": []}

    monkeypatch.setattr(handlers_accounts, "bing_get", fake_bing_get)
    result = await handlers_accounts.fn_save_bing_key(ctx, SaveKeyParams(bing_api_key="key-1", label="Agency"))
    assert result.status == "success"
    assert result.data.label == "Agency"
    assert result.data.is_active is True


# ─── list / switch / disconnect ─────────────────────────────────────────── #

@pytest.mark.asyncio
async def test_list_bing_accounts_empty():
    ctx = _ctx()
    result = await handlers_accounts.fn_list_bing_accounts(ctx, EmptyParams())
    assert result.status == "success"
    assert result.data.count == 0


@pytest.mark.asyncio
async def test_switch_and_disconnect_account(monkeypatch):
    ctx = _ctx()

    async def fake_bing_get(ctx, key, method, params=None):
        return {"d": []}

    monkeypatch.setattr(handlers_accounts, "bing_get", fake_bing_get)
    await handlers_accounts.fn_save_bing_key(ctx, SaveKeyParams(bing_api_key="key-1", label="First"))
    await handlers_accounts.fn_save_bing_key(ctx, SaveKeyParams(bing_api_key="key-2", label="Second"))

    switched = await handlers_accounts.fn_switch_bing_account(ctx, AccountLabelParams(label="Second"))
    assert switched.status == "success"
    assert switched.data.active == "Second"

    disconnected = await handlers_accounts.fn_disconnect_bing_account(ctx, AccountLabelParams(label="Second"))
    assert disconnected.status == "success"
    assert disconnected.data.remaining == 1


@pytest.mark.asyncio
async def test_switch_unknown_account_returns_error():
    ctx = _ctx()
    result = await handlers_accounts.fn_switch_bing_account(ctx, AccountLabelParams(label="Ghost"))
    assert result.status == "error"


# ─── handlers_data: list_bing_sites / top_queries / top_pages / traffic ──── #

@pytest.mark.asyncio
async def test_list_bing_sites_requires_connection():
    ctx = _ctx()
    result = await handlers_data.fn_list_bing_sites(ctx, EmptyParams())
    assert result.status == "error"


@pytest.mark.asyncio
async def test_list_bing_sites_success(monkeypatch):
    ctx = _ctx()

    async def fake_bing_get(ctx, key, method, params=None):
        assert method == "GetUserSites"
        return {"d": [{"Url": "http://example.com/", "IsVerified": True}]}

    monkeypatch.setattr(handlers_accounts, "bing_get", fake_bing_get)
    await handlers_accounts.fn_save_bing_key(ctx, SaveKeyParams(bing_api_key="key-1", label=""))

    monkeypatch.setattr(handlers_data, "bing_get", fake_bing_get)
    result = await handlers_data.fn_list_bing_sites(ctx, EmptyParams())
    assert result.status == "success"
    assert result.data.count == 1
    assert result.data.sites[0].site_url == "http://example.com/"


@pytest.mark.asyncio
async def test_top_queries_success(monkeypatch):
    ctx = _ctx()

    async def fake_connect(ctx, key, method, params=None):
        return {"d": []}

    monkeypatch.setattr(handlers_accounts, "bing_get", fake_connect)
    await handlers_accounts.fn_save_bing_key(ctx, SaveKeyParams(bing_api_key="key-1", label=""))

    async def fake_query_stats(ctx, key, method, params=None):
        assert method == "GetQueryStats"
        assert params == {"siteUrl": "http://example.com/"}
        return {"d": [{"Query": "webhostmost", "Clicks": 5, "Impressions": 100,
                        "AvgClickPosition": 2, "AvgImpressionPosition": 3,
                        "Date": "/Date(1699920000000)/"}]}

    monkeypatch.setattr(handlers_data, "bing_get", fake_query_stats)
    result = await handlers_data.fn_top_queries(ctx, SiteUrlParams(site_url="http://example.com/"))
    assert result.status == "success"
    assert result.data.count == 1
    assert result.data.rows[0].query == "webhostmost"
    assert result.data.rows[0].clicks == 5


@pytest.mark.asyncio
async def test_top_pages_and_traffic_stats_require_connection():
    ctx = _ctx()
    pages = await handlers_data.fn_top_pages(ctx, SiteUrlParams(site_url="http://example.com/"))
    assert pages.status == "error"
    traffic = await handlers_data.fn_traffic_stats(ctx, SiteUrlParams(site_url="http://example.com/"))
    assert traffic.status == "error"
