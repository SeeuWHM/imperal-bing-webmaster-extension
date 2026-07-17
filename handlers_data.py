"""Chat-function handlers for reading Bing Webmaster search performance data —
the analogues of GSC's list_sites/top_queries but sourced from Bing.

Every read call uses the currently ACTIVE account's key (accounts.py). Bing's
JSON API has no date-range or limit parameters (unlike GSC) — it always
returns everything it has, bucketed weekly (queries/pages) or daily (site
traffic); we don't fabricate filtering it doesn't support.
"""
from __future__ import annotations

from imperal_sdk.types import ActionResult

from app import chat
from bing_accounts import _active_api_key
from bing_api import bing_get
from params import EmptyParams, SiteUrlParams
from response_models import (
    PageList, QueryList, SiteList, TrafficStats,
    build_page_list, build_query_list, build_site_list, build_traffic_stats,
)


async def _require_key(ctx) -> str:
    key = await _active_api_key(ctx)
    if not key:
        raise RuntimeError("No Bing Webmaster account connected. Call save_bing_key first.")
    return key


@chat.function(
    "list_bing_sites", action_type="read", chain_callable=True, data_model=SiteList,
    description=(
        "List the Bing Webmaster properties (verified sites) the active Bing account can "
        "see. Use for: list my Bing Webmaster sites, show verified Bing properties."
    ),
)
async def fn_list_bing_sites(ctx, params: EmptyParams) -> ActionResult:
    """The active account's verified (and pending) Bing Webmaster sites."""
    try:
        key = await _require_key(ctx)
        data = await bing_get(ctx, key, "GetUserSites")
    except Exception as e:
        return ActionResult.error(str(e), retryable=False)
    rows = data.get("d") or []
    result = build_site_list(rows)
    return ActionResult.success(data=result, summary=f"{result.count} Bing Webmaster site(s).")


@chat.function(
    "top_queries", action_type="read", chain_callable=True, data_model=QueryList,
    description=(
        "The connected site's best-performing Bing search queries — clicks, impressions, "
        "average position. Weekly buckets, Bing gives all history it has (no date-range "
        "filter on this endpoint). Use for: top queries on Bing."
    ),
)
async def fn_top_queries(ctx, params: SiteUrlParams) -> ActionResult:
    """Query-level Bing Search performance for one site (GetQueryStats)."""
    try:
        key = await _require_key(ctx)
        data = await bing_get(ctx, key, "GetQueryStats", {"siteUrl": params.site_url})
    except Exception as e:
        return ActionResult.error(str(e), retryable=False)
    rows = data.get("d") or []
    result = build_query_list(params.site_url, rows)
    return ActionResult.success(data=result, summary=f"{result.count} query row(s) for {params.site_url}.")


@chat.function(
    "top_pages", action_type="read", chain_callable=True, data_model=PageList,
    description=(
        "The connected site's best-performing pages on Bing — clicks, impressions, average "
        "position per page. Weekly buckets, all history Bing has. Use for: top pages on "
        "Bing, which pages get Bing traffic."
    ),
)
async def fn_top_pages(ctx, params: SiteUrlParams) -> ActionResult:
    """Page-level Bing Search performance for one site (GetPageStats)."""
    try:
        key = await _require_key(ctx)
        data = await bing_get(ctx, key, "GetPageStats", {"siteUrl": params.site_url})
    except Exception as e:
        return ActionResult.error(str(e), retryable=False)
    rows = data.get("d") or []
    result = build_page_list(params.site_url, rows)
    return ActionResult.success(data=result, summary=f"{result.count} page row(s) for {params.site_url}.")


@chat.function(
    "traffic_stats", action_type="read", chain_callable=True, data_model=TrafficStats,
    description=(
        "Daily site-wide clicks + impressions trend for one site on Bing — a small trend "
        "chart, like the top of Bing's Search Performance report. Use for: bing traffic "
        "trend, daily Bing clicks and impressions."
    ),
)
async def fn_traffic_stats(ctx, params: SiteUrlParams) -> ActionResult:
    """Daily Clicks/Impressions trend for one site (GetRankAndTrafficStats)."""
    try:
        key = await _require_key(ctx)
        data = await bing_get(ctx, key, "GetRankAndTrafficStats", {"siteUrl": params.site_url})
    except Exception as e:
        return ActionResult.error(str(e), retryable=False)
    rows = data.get("d") or []
    result = build_traffic_stats(params.site_url, rows)
    return ActionResult.success(data=result, summary=f"{result.count} day(s) of traffic for {params.site_url}.")
