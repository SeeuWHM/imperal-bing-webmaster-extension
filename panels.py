"""Bing Webmaster sidebar panel — connect form when nothing's connected;
account selector + the active account's verified sites when connected.

No OAuth here (Bing issues a plain per-user API key, unlike GSC's Google
account grant) — this panel is the SE Ranking connector's shape (a real
password-masked form right here) crossed with the GSC connector's
multi-account selector (several keys connected + switchable, active one
marked, click to switch/disconnect).
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
from bing_accounts import _active_account, _all_accounts, bing_ready
from bing_api import bing_get
from cache_helpers import SITES_CACHE_TTL, cached_call

_SHOWN_COLLAPSED = 8


def _key_form(error: str = "") -> list[ui.UINode]:
    """The API-key entry form itself — reused by the not-connected prompt and by
    the inline "add another account" block, so both stay in sync."""
    children = []
    if error:
        children.append(ui.Alert(message=error, type="error"))
    children.append(ui.Form(
        action="save_bing_key",
        submit_label="Connect",
        children=[
            ui.Password(placeholder="Paste your Bing Webmaster API key…", param_name="bing_api_key"),
            ui.Input(placeholder="Label (optional, e.g. \"Agency\")", param_name="label"),
        ],
    ))
    children.append(ui.Text(
        content="Get your key at bing.com/webmasters → Settings → API Access → Generate API Key.",
        variant="caption",
    ))
    return children


def _connect_form(error: str = "") -> ui.UINode:
    return ui.Stack(children=[
        ui.Header(text="Bing Webmaster", level=4),
        ui.Badge(label="○ not connected", color="gray"),
        ui.Divider(),
        ui.Text(content=(
            "Connect your Bing Webmaster API key to see your site's Bing search "
            "performance here — queries, pages, traffic trend. You can connect "
            "more than one account and switch between them below."
        ), variant="body"),
        *_key_form(error),
    ])


def _account_items(accounts: list[dict]) -> list[ui.UINode]:
    """Every connected Bing Webmaster account, active one marked, click any
    other to switch. Without this block a second connected key had nowhere
    to render (same bug class fixed for the GSC connector)."""
    items = []
    for acc in accounts:
        label = acc.get("label", "")
        is_active = bool(acc.get("is_active"))
        items.append(ui.ListItem(
            id=label, title=label,
            subtitle="✓ Active" if is_active else "Click to switch",
            avatar=ui.Avatar(fallback=label[0].upper() if label else "?", size="sm"),
            badge=ui.Badge("✓", color="green") if is_active else None,
            on_click=None if is_active else ui.Call("switch_bing_account", label=label),
            actions=[{"label": "Disconnect", "icon": "Trash2",
                      "on_click": ui.Call("disconnect_bing_account", label=label)}],
        ))
    return items


@ext.panel("bing_sidebar", slot="left", title="Bing Webmaster", icon="Search",
           default_width=260,
           refresh="on_event:bing.account.connected,bing.account.switched,bing.account.disconnected")
async def sidebar_panel(ctx, show_all: bool = False, show_add: bool = False):
    if not await bing_ready(ctx):
        return _connect_form()

    accounts = await _all_accounts(ctx)
    active = await _active_account(ctx)
    active_label = (active or {}).get("label", "")
    active_key = (active or {}).get("api_key", "")

    async def _fetch_sites() -> list[dict]:
        data = await bing_get(ctx, active_key, "GetUserSites")
        return data.get("d") or []

    try:
        rows = await cached_call(ctx, "sites", active_key, None, SITES_CACHE_TTL, _fetch_sites)
    except Exception as e:
        # A stored key Bing now rejects (revoked/expired) drops back to the
        # connect prompt with the real reason, not a dead-end error card.
        return _connect_form(error=str(e))

    shown = rows if show_all else rows[:_SHOWN_COLLAPSED]
    remaining = len(rows) - len(shown)
    list_or_empty = (
        ui.List(items=[
            ui.ListItem(
                id=r.get("Url", ""),
                title=r.get("Url", "") or "(unknown)",
                subtitle="Verified" if r.get("IsVerified") else "Not verified",
                on_click=ui.Call("__panel__bing_workspace", site_url=r.get("Url", "")),
            )
            for r in shown
        ])
        if shown else
        ui.Text(content="No sites on this Bing Webmaster account.", variant="caption")
    )
    footer = (
        [ui.Button(label=f"+ {remaining} more site(s)", variant="ghost", size="sm",
                    on_click=ui.Call("__panel__bing_sidebar", show_all=True))]
        if remaining > 0 else
        ([ui.Button(label="Show fewer", variant="ghost", size="sm",
                     on_click=ui.Call("__panel__bing_sidebar", show_all=False))]
         if show_all and len(rows) > _SHOWN_COLLAPSED else [])
    )

    root = ui.Stack(children=[
        ui.Header(text="Bing Webmaster", level=4),
        ui.Badge(label="● connected", color="green"),
        ui.Divider(),
        ui.Text(content=f"Accounts ({len(accounts)})", variant="caption"),
        ui.List(items=_account_items(accounts)) if accounts else ui.Empty(message="No accounts"),
        # Inline add-account form (expands in place — same proven mechanism as
        # the "+N more" toggle; replaces the old overlay panel that never opened).
        ui.Stack(children=[
            ui.Divider(),
            ui.Text(content="Add another Bing account", variant="caption"),
            *_key_form(),
            ui.Button(label="Cancel", variant="ghost", size="sm",
                      on_click=ui.Call("__panel__bing_sidebar", show_add=False)),
        ]) if show_add else
        ui.Button(label="Add another Bing account", icon="Plus", variant="outline",
                  on_click=ui.Call("__panel__bing_sidebar", show_add=True)),
        ui.Divider(),
        ui.Stats(children=[
            ui.Stat(label="Sites", value=str(len(rows)), icon="Globe"),
        ]),
        ui.Divider(),
        ui.Text(content=f"{active_label}'s Bing Webmaster sites — click one to open", variant="caption"),
        list_or_empty,
        *footer,
    ])
    root.props["auto_action"] = ui.Call("__panel__bing_workspace").to_dict()
    return root
