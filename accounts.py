"""Multi-account Bing Webmaster key storage.

Same JSON-blob pattern as the SE Ranking connector's accounts.py: several
Bing Webmaster API keys can be connected simultaneously and switched between,
one active at a time. `bing_accounts` holds a JSON list of
[{"label": str, "api_key": str, "is_active": bool}, ...].
"""
from __future__ import annotations

import json

ACCOUNTS_SECRET = "bing_accounts"


def _mask(key: str) -> str:
    key = (key or "").strip()
    if not key:
        return ""
    tail = key[-4:] if len(key) >= 4 else key
    return f"••••{tail}"


async def _load_raw(ctx) -> list[dict]:
    raw = await ctx.secrets.get(ACCOUNTS_SECRET)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


async def _save_raw(ctx, accounts: list[dict]) -> None:
    await ctx.secrets.set(ACCOUNTS_SECRET, json.dumps(accounts))


async def _all_accounts(ctx) -> list[dict]:
    """Every connected Bing Webmaster account."""
    return await _load_raw(ctx)


async def _active_account(ctx) -> dict | None:
    accounts = await _all_accounts(ctx)
    if not accounts:
        return None
    return next((a for a in accounts if a.get("is_active")), accounts[0])


async def _active_api_key(ctx) -> str:
    account = await _active_account(ctx)
    return (account or {}).get("api_key", "").strip()


async def bing_ready(ctx) -> bool:
    """Whether the caller has at least one Bing Webmaster account connected."""
    return bool(await _active_api_key(ctx))


async def _add_account(ctx, api_key: str, label: str = "") -> dict:
    """Add a new Bing Webmaster account. First account connected becomes active
    automatically; later ones are added inactive (call switch to activate)."""
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("API key cannot be empty.")

    accounts = await _all_accounts(ctx)

    if any(a.get("api_key") == api_key for a in accounts):
        raise ValueError("This Bing Webmaster API key is already connected.")

    default_label = f"Account {len(accounts) + 1}" if accounts else "Default"
    label = label.strip() or default_label
    if any(a.get("label") == label for a in accounts):
        label = f"{label} ({_mask(api_key)})"

    new_account = {"label": label, "api_key": api_key, "is_active": not accounts}
    accounts.append(new_account)
    await _save_raw(ctx, accounts)
    return new_account


async def _switch_account(ctx, label: str) -> dict:
    """Make one already-connected account the active one."""
    accounts = await _all_accounts(ctx)
    match = next((a for a in accounts if a.get("label") == label), None)
    if not match:
        available = [a.get("label") for a in accounts]
        raise ValueError(f"Account {label!r} not found. Connected: {available}")

    for a in accounts:
        a["is_active"] = (a.get("label") == label)
    await _save_raw(ctx, accounts)
    return match


async def _disconnect_account(ctx, label: str) -> int:
    """Remove one connected account by label. If it was active, the first
    remaining account (if any) becomes active. Returns the remaining count."""
    accounts = await _all_accounts(ctx)
    match = next((a for a in accounts if a.get("label") == label), None)
    if not match:
        available = [a.get("label") for a in accounts]
        raise ValueError(f"Account {label!r} not found. Connected: {available}")

    was_active = match.get("is_active", False)
    remaining = [a for a in accounts if a.get("label") != label]
    if was_active and remaining:
        remaining[0]["is_active"] = True
    await _save_raw(ctx, remaining)
    return len(remaining)
