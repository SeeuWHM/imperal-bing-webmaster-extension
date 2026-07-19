"""Bing Webmaster center workspace — one site's queries, pages, traffic trend.

Reuses the handlers_data functions server-side (plain Python, zero LLM
tokens) — same shape as GSC/SE Ranking's workspace panels.
"""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from app import ext
from bing_accounts import _active_api_key, bing_ready
from bing_api import bing_get
from cache_helpers import ANALYTICS_CACHE_TTL, cached_call
from response_models import build_page_list, build_query_list, build_traffic_stats

_SHOWN = 50   # unique queries/pages shown before "Load more"


async def _queries_section(ctx, key: str, site_url: str, show_all: bool = False) -> ui.UINode:
    async def _fetch() -> list[dict]:
        data = await bing_get(ctx, key, "GetQueryStats", {"siteUrl": site_url})
        return data.get("d") or []

    try:
        raw = await cached_call(ctx, "queries", key, {"site_url": site_url}, ANALYTICS_CACHE_TTL, _fetch)
        rows = build_query_list(site_url, raw).rows   # aggregated, dupes gone
    except Exception as e:
        return ui.Alert(message=str(e), type="error")
    shown = rows if show_all else rows[:_SHOWN]
    body = ui.DataTable(
        columns=[
            ui.DataColumn(key="query", label="Query", width="40%"),
            ui.DataColumn(key="clicks", label="Clicks", width="15%"),
            ui.DataColumn(key="impressions", label="Impressions", width="20%"),
            ui.DataColumn(key="avg_impression_position", label="Avg position", width="25%"),
        ],
        rows=[{"query": r.query, "clicks": r.clicks, "impressions": r.impressions,
               "avg_impression_position": r.avg_impression_position} for r in shown],
    ) if rows else ui.Text(content="No query data yet for this site.", variant="caption")
    children = [ui.Header(text=f"Top queries ({len(rows)})", level=5), body]
    if not show_all and len(rows) > _SHOWN:
        children.append(ui.Button(label=f"Load all {len(rows)} rows", variant="ghost", size="sm",
                                  on_click=ui.Call("__panel__bing_workspace", site_url=site_url, show_all=True)))
    return ui.Stack(gap=1, children=children)


async def _pages_section(ctx, key: str, site_url: str, show_all: bool = False) -> ui.UINode:
    async def _fetch() -> list[dict]:
        data = await bing_get(ctx, key, "GetPageStats", {"siteUrl": site_url})
        return data.get("d") or []

    try:
        raw = await cached_call(ctx, "pages", key, {"site_url": site_url}, ANALYTICS_CACHE_TTL, _fetch)
        rows = build_page_list(site_url, raw).rows   # aggregated, dupes gone
    except Exception as e:
        return ui.Alert(message=str(e), type="error")
    shown = rows if show_all else rows[:_SHOWN]
    body = ui.DataTable(
        columns=[
            ui.DataColumn(key="page", label="Page", width="45%"),
            ui.DataColumn(key="clicks", label="Clicks", width="15%"),
            ui.DataColumn(key="impressions", label="Impressions", width="20%"),
            ui.DataColumn(key="avg_impression_position", label="Avg position", width="20%"),
        ],
        rows=[{"page": r.page, "clicks": r.clicks, "impressions": r.impressions,
               "avg_impression_position": r.avg_impression_position} for r in shown],
    ) if rows else ui.Text(content="No page data yet for this site.", variant="caption")
    children = [ui.Header(text=f"Top pages ({len(rows)})", level=5), body]
    if not show_all and len(rows) > _SHOWN:
        children.append(ui.Button(label=f"Load all {len(rows)} rows", variant="ghost", size="sm",
                                  on_click=ui.Call("__panel__bing_workspace", site_url=site_url, show_all=True)))
    return ui.Stack(gap=1, children=children)


async def _traffic_section(ctx, key: str, site_url: str) -> ui.UINode:
    async def _fetch() -> list[dict]:
        data = await bing_get(ctx, key, "GetRankAndTrafficStats", {"siteUrl": site_url})
        return data.get("d") or []

    try:
        raw = await cached_call(ctx, "traffic", key, {"site_url": site_url}, ANALYTICS_CACHE_TTL, _fetch)
        rows = build_traffic_stats(site_url, raw).rows
    except Exception as e:
        return ui.Alert(message=str(e), type="error")
    total_clicks = sum(r.clicks for r in rows)
    total_impr = sum(r.impressions for r in rows)
    return ui.Stack(gap=1, children=[
        ui.Header(text=f"Traffic trend ({len(rows)} day(s))", level=5),
        ui.Stats(children=[
            ui.Stat(label="Total clicks", value=str(total_clicks), icon="MousePointerClick"),
            ui.Stat(label="Total impressions", value=str(total_impr), icon="Eye"),
        ]),
    ])


@ext.panel("bing_workspace", slot="center", title="Bing Webmaster", icon="Search",
           refresh="on_event:bing.account.switched,bing.account.disconnected")
async def workspace_panel(ctx, site_url: str = "", show_all: bool = False):
    if not await bing_ready(ctx):
        return ui.Empty(message="Connect your Bing Webmaster account first — run save_bing_key in chat.")
    if not site_url:
        return ui.Empty(message="Pick a site on the left to see its queries, pages and traffic trend.")

    key = await _active_api_key(ctx)
    queries, pages, traffic = await asyncio.gather(
        _queries_section(ctx, key, site_url, show_all),
        _pages_section(ctx, key, site_url, show_all),
        _traffic_section(ctx, key, site_url),
    )
    return ui.Stack(children=[traffic, ui.Divider(), queries, ui.Divider(), pages])
