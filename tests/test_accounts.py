"""Unit tests for accounts.py — the multi-account JSON-blob store.

No network. MockContext + MockSecretStore, following the SE Ranking /
Article Writer connectors' convention.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import json

import pytest
from imperal_sdk.testing import MockContext
from imperal_sdk.testing.mock_secrets import MockSecretStore

import accounts


def _ctx(initial: dict | None = None) -> MockContext:
    ctx = MockContext(user_id="tenant-abc-123")
    ctx.secrets = MockSecretStore(initial or {})
    return ctx


@pytest.mark.asyncio
async def test_mask_short_and_empty_keys():
    assert accounts._mask("") == ""
    assert accounts._mask("ab") == "••••ab"
    assert accounts._mask("abcdefgh") == "••••efgh"


@pytest.mark.asyncio
async def test_no_accounts_when_nothing_connected():
    ctx = _ctx()
    assert await accounts._all_accounts(ctx) == []
    assert await accounts._active_account(ctx) is None
    assert await accounts._active_api_key(ctx) == ""
    assert await accounts.bing_ready(ctx) is False


@pytest.mark.asyncio
async def test_add_first_account_becomes_active_and_labeled_default():
    ctx = _ctx()
    account = await accounts._add_account(ctx, "key-1", "")
    assert account["label"] == "Default"
    assert account["is_active"] is True

    all_accounts = await accounts._all_accounts(ctx)
    assert len(all_accounts) == 1
    assert await accounts.bing_ready(ctx) is True
    assert await accounts._active_api_key(ctx) == "key-1"


@pytest.mark.asyncio
async def test_add_second_account_stays_inactive_with_auto_label():
    ctx = _ctx()
    await accounts._add_account(ctx, "key-1", "")
    second = await accounts._add_account(ctx, "key-2", "")
    assert second["label"] == "Account 2"
    assert second["is_active"] is False

    # Active account is still the first one.
    assert await accounts._active_api_key(ctx) == "key-1"


@pytest.mark.asyncio
async def test_add_account_respects_explicit_label():
    ctx = _ctx()
    account = await accounts._add_account(ctx, "key-1", "Agency")
    assert account["label"] == "Agency"


@pytest.mark.asyncio
async def test_add_account_rejects_empty_key():
    ctx = _ctx()
    with pytest.raises(ValueError):
        await accounts._add_account(ctx, "   ", "")


@pytest.mark.asyncio
async def test_add_account_disambiguates_duplicate_label():
    ctx = _ctx()
    first = await accounts._add_account(ctx, "key-1", "Agency")
    second = await accounts._add_account(ctx, "key-2", "Agency")
    assert first["label"] == "Agency"
    # Same label reused -> disambiguated with the new key's mask, never silently
    # dropped or overwritten.
    assert second["label"] != "Agency"
    assert second["label"].startswith("Agency (")


@pytest.mark.asyncio
async def test_switch_account_changes_active():
    ctx = _ctx()
    await accounts._add_account(ctx, "key-1", "First")
    await accounts._add_account(ctx, "key-2", "Second")

    switched = await accounts._switch_account(ctx, "Second")
    assert switched["label"] == "Second"
    assert await accounts._active_api_key(ctx) == "key-2"

    all_accounts = await accounts._all_accounts(ctx)
    actives = [a["label"] for a in all_accounts if a["is_active"]]
    assert actives == ["Second"]


@pytest.mark.asyncio
async def test_switch_account_unknown_label_raises():
    ctx = _ctx()
    await accounts._add_account(ctx, "key-1", "First")
    with pytest.raises(ValueError):
        await accounts._switch_account(ctx, "Nonexistent")


@pytest.mark.asyncio
async def test_disconnect_account_removes_only_that_one():
    ctx = _ctx()
    await accounts._add_account(ctx, "key-1", "First")
    await accounts._add_account(ctx, "key-2", "Second")

    remaining = await accounts._disconnect_account(ctx, "First")
    assert remaining == 1
    all_accounts = await accounts._all_accounts(ctx)
    assert [a["label"] for a in all_accounts] == ["Second"]


@pytest.mark.asyncio
async def test_disconnect_active_account_promotes_another():
    ctx = _ctx()
    await accounts._add_account(ctx, "key-1", "First")
    await accounts._add_account(ctx, "key-2", "Second")
    # First is active by default (first-added rule).
    await accounts._disconnect_account(ctx, "First")

    all_accounts = await accounts._all_accounts(ctx)
    assert len(all_accounts) == 1
    assert all_accounts[0]["is_active"] is True
    assert await accounts._active_api_key(ctx) == "key-2"


@pytest.mark.asyncio
async def test_disconnect_unknown_label_raises():
    ctx = _ctx()
    await accounts._add_account(ctx, "key-1", "First")
    with pytest.raises(ValueError):
        await accounts._disconnect_account(ctx, "Ghost")


@pytest.mark.asyncio
async def test_accounts_persist_across_reads_via_secret_store():
    ctx = _ctx()
    await accounts._add_account(ctx, "key-1", "First")

    raw = await ctx.secrets.get(accounts.ACCOUNTS_SECRET)
    parsed = json.loads(raw)
    assert parsed[0]["label"] == "First"
    assert parsed[0]["api_key"] == "key-1"
