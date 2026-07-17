"""Chat-function handlers for connecting/disconnecting/switching the user's
own Bing Webmaster account(s) — the primary, in-extension UX for entering an
API key (a real form in the sidebar). No OAuth: Bing issues a plain API key
per Microsoft account (Settings -> API Access -> Generate API Key).

Multi-account: several Bing Webmaster keys can be connected at once and
switched between (accounts.py owns the JSON-blob storage). Same shape as the
SE Ranking connector's account handlers.
"""
from __future__ import annotations

from pydantic import BaseModel

from imperal_sdk.types import ActionResult

from app import chat
from bing_accounts import (
    _active_api_key, _add_account, _all_accounts, _disconnect_account, _mask, _switch_account,
)
from bing_api import bing_get
from params import AccountLabelParams, EmptyParams, SaveKeyParams
from response_models import (
    AccountDisconnected, AccountRecord, AccountsList, AccountSwitched, ConnectionStatus,
    build_accounts_list,
)


@chat.function(
    "connection_status", action_type="read", chain_callable=True, data_model=ConnectionStatus,
    description=(
        "Whether the user's own Bing Webmaster API key is connected. Use for: "
        "is my Bing account connected, connection status."
    ),
)
async def fn_connection_status(ctx, params: EmptyParams) -> ActionResult:
    """Report whether the caller has an active Bing Webmaster key configured."""
    key = await _active_api_key(ctx)
    masked = _mask(key)
    result = ConnectionStatus(connected=bool(key), masked_key=masked)
    summary = f"Connected ({masked})" if key else "Not connected"
    return ActionResult.success(data=result, summary=summary)


@chat.function(
    "save_bing_key", action_type="write", event="bing.account.connected",
    effects=["create:secret"], data_model=AccountRecord,
    description=(
        "Connect a Bing Webmaster account by saving its API key. Validates the key "
        "against Bing (calls GetUserSites) before saving — rejects invalid keys with a "
        "clear message. Connecting again adds ANOTHER account rather than replacing the "
        "first — you can hold several Bing Webmaster accounts and switch between them."
    ),
)
async def fn_save_bing_key(ctx, params: SaveKeyParams) -> ActionResult:
    """Validate a Bing Webmaster API key against the real API, then store it as a
    new connected account (or reject with the real reason it failed)."""
    key = params.bing_api_key.strip()
    if not key:
        return ActionResult.error("API key cannot be empty.", retryable=False)

    try:
        await bing_get(ctx, key, "GetUserSites")
    except Exception as e:
        return ActionResult.error(f"Could not validate this Bing Webmaster key: {e}", retryable=True)

    account = await _add_account(ctx, key, params.label)
    return ActionResult.success(
        data=AccountRecord(label=account["label"], masked_key=_mask(key), is_active=bool(account.get("is_active"))),
        summary=f"Bing Webmaster account '{account['label']}' connected.",
    )


@chat.function(
    "list_bing_accounts", action_type="read", chain_callable=True, data_model=AccountsList,
    description=(
        "List every Bing Webmaster account you've connected — label, masked key, which "
        "one is active. Use for: list connected Bing accounts, which Bing Webmaster "
        "account is active."
    ),
)
async def fn_list_bing_accounts(ctx, params: EmptyParams) -> ActionResult:
    """Every connected Bing Webmaster account with its label, masked key, and
    which one is currently active."""
    accounts = await _all_accounts(ctx)
    result = build_accounts_list(accounts)
    return ActionResult.success(data=result, summary=f"{result.count} Bing Webmaster account(s) connected.")


@chat.function(
    "switch_bing_account", action_type="write", event="bing.account.switched",
    effects=["update:secret"], data_model=AccountSwitched,
    description=(
        "Switch which connected Bing Webmaster account is active — all following Bing "
        "calls (sites, queries, pages, traffic) use this account's key. Use for: "
        "switch to Bing account X, use my other Bing key."
    ),
)
async def fn_switch_bing_account(ctx, params: AccountLabelParams) -> ActionResult:
    """Make one already-connected Bing Webmaster account the active one."""
    try:
        account = await _switch_account(ctx, params.label)
    except Exception as e:
        return ActionResult.error(str(e), retryable=False)
    return ActionResult.success(
        data=AccountSwitched(active=account["label"]),
        summary=f"Now using Bing Webmaster account '{account['label']}'.",
    )


@chat.function(
    "disconnect_bing_account", action_type="destructive", event="bing.account.disconnected",
    effects=["delete:secret"], data_model=AccountDisconnected,
    description=(
        "Disconnect ONE specific connected Bing Webmaster account by its label — removes "
        "only that key, other connected accounts are untouched. Use for: disconnect this "
        "Bing account, remove one Bing Webmaster key."
    ),
)
async def fn_disconnect_bing_account(ctx, params: AccountLabelParams) -> ActionResult:
    """Remove one connected Bing Webmaster account by its label, leaving the rest untouched."""
    try:
        remaining = await _disconnect_account(ctx, params.label)
    except Exception as e:
        return ActionResult.error(str(e), retryable=False)
    return ActionResult.success(
        data=AccountDisconnected(label=params.label, remaining=remaining),
        summary=f"Bing Webmaster account '{params.label}' disconnected. {remaining} remaining.",
    )
