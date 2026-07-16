"""Bing Webmaster Connector — core init + shared helpers.

Architecture: unlike Google Search Console (which needs OAuth because
Google's data is only reachable via a signed-in Google account), Bing
Webmaster Tools issues a plain per-user API key (Settings -> API Access ->
Generate API Key) — no OAuth dance, no shared backend microservice needed.
This extension calls https://ssl.bing.com/webmaster/api.svc/json/ directly
with ctx.http, forwarding the caller's OWN key as a query parameter, exactly
as Bing's API expects. Same shape as the SE Ranking connector's multi-account
model (several keys connected + switchable), minus the shared backend hop
(Bing's API is public and free — no credit-metering proxy required).

Multi-account: several Bing Webmaster accounts (each with its own API key)
can be connected simultaneously and switched between — see accounts.py.
"""
from __future__ import annotations

from imperal_sdk import Extension, ChatExtension

BING_API_BASE = "https://ssl.bing.com/webmaster/api.svc/json"

ext = Extension(
    "bing-webmaster-connector",
    version="1.1.1",
    display_name="Bing Webmaster Connector",
    description=(
        "Bing Webmaster Tools search performance: which queries bring clicks "
        "and impressions on Bing, page-level and site-level traffic trends, "
        "your verified Bing sites. Connect your own Bing Webmaster API key "
        "(no OAuth needed) to see your own data here."
    ),
    icon="icon.svg",
    actions_explicit=True,
    capabilities=[
        "Search Query Performance",
        "Page Traffic Stats",
        "Site Traffic Trends",
        "Verified Sites",
    ],
)

chat = ChatExtension(
    ext,
    tool_name="bing_webmaster",
    description=(
        "Bing Webmaster Tools — search performance data from Bing (not "
        "Google). Use for: bing запросы, top queries on Bing, какие запросы "
        "приводят трафик из Bing, page traffic stats on Bing, Bing search "
        "console, verified Bing sites."
    ),
    max_rounds=10,
)

# ── User-scope secret: every connected Bing Webmaster API key ────────────────
# A real per-user credential, interpreted literally as the key value: no URL
# or account identifier is ever assembled or guessed from it. JSON list of
# {label, api_key, is_active} — same multi-account shape as the SE Ranking
# connector's `seranking_accounts` (mail-client's `imap_credentials` is the
# original pattern this follows). write_mode="extension": only this
# extension's own connect/switch/disconnect handlers write it, never the
# platform's generic Secrets panel, since its shape is a JSON blob, not one
# opaque value.
ext.secret(
    name="bing_accounts",
    description=(
        "Every Bing Webmaster account you've connected (JSON list of "
        "{label, api_key, is_active}) — lets you track multiple Bing "
        "Webmaster accounts and switch between them. Managed only through "
        "this extension's own connect/switch/disconnect actions."
    ),
    required=False,
    write_mode="extension",
    scope="user",
    max_bytes=8192,
)(lambda: None)


@ext.health_check
async def health(ctx) -> dict:
    """Report whether the user has at least one Bing Webmaster account connected."""
    from bing_accounts import bing_ready
    return {"status": "ok", "version": ext.version, "bing_connected": await bing_ready(ctx)}
