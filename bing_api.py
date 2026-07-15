"""Thin wrappers over the Bing Webmaster Tools JSON API — one primitive per
operation, no orchestration baked in here. Calls go directly to
ssl.bing.com via ctx.http with the caller's own API key as a query
parameter (Bing's own auth model — no OAuth, no shared backend proxy).

Reference: https://learn.microsoft.com/en-us/bingwebmaster/getting-access
(API key from Bing Webmaster Tools -> Settings -> API Access) and
https://learn.microsoft.com/en-us/bingwebmaster/api-protocols (JSON
endpoints, GET https://ssl.bing.com/webmaster/api.svc/json/METHOD?apikey=...).

Error shape (confirmed via Microsoft Learn + community docs): HTTP 400 with
a JSON body like {"ErrorCode": 3, "Message": "InvalidApiKey"}.
"""
from __future__ import annotations

from app import BING_API_BASE


def _bing_error(status_code: int, body: dict | None) -> str:
    body = body or {}
    msg = body.get("Message") or body.get("message") or ""
    code = body.get("ErrorCode")
    if msg:
        return f"Bing Webmaster API error (HTTP {status_code}): {msg}" + (f" [code {code}]" if code is not None else "")
    return f"Bing Webmaster API error: HTTP {status_code}"


async def bing_get(ctx, api_key: str, method: str, params: dict | None = None) -> dict:
    """Call one Bing Webmaster JSON API method. Returns the raw {\"d\": ...}
    envelope on success, or raises RuntimeError with a clean message on
    failure (invalid key, site not verified, throttling, etc.)."""
    if not api_key:
        raise RuntimeError("No Bing Webmaster account connected. Call connect_bing/save_bing_key first.")

    query = {"apikey": api_key, **(params or {})}
    url = f"{BING_API_BASE}/{method}"
    resp = await ctx.http.get(url, params=query, timeout=30)

    if resp.status_code != 200:
        body = None
        try:
            body = resp.json()
        except Exception:
            pass
        raise RuntimeError(_bing_error(resp.status_code, body))

    try:
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"Bing Webmaster API returned a non-JSON response: {e}")

    return data or {}


async def bing_get_user_sites(ctx, api_key: str) -> list[dict]:
    """Every website registered with this Bing Webmaster account.

    Returns [{"url", "is_verified"}]."""
    data = await bing_get(ctx, api_key, "GetUserSites")
    rows = data.get("d") or []
    return [
        {"url": r.get("Url", ""), "is_verified": bool(r.get("IsVerified"))}
        for r in rows
    ]


def _bing_date_to_epoch_ms(value: str) -> int:
    """Bing serializes dates as ASP.NET JSON date strings: '/Date(1700000000000)/'."""
    if not value:
        return 0
    try:
        inner = value.split("(", 1)[1].split(")", 1)[0]
        # Strip a trailing timezone offset like "+0000" if present.
        digits = "".join(ch for ch in inner if ch.isdigit() or ch == "-")
        return int(digits[:13]) if digits else 0
    except Exception:
        return 0


async def bing_get_query_stats(ctx, api_key: str, site_url: str) -> list[dict]:
    """Per-query search performance for one verified site — all history Bing
    has, in weekly buckets (no date-range/limit params on this endpoint).

    Returns [{"query", "clicks", "impressions", "avg_click_position",
    "avg_impression_position", "date_ms"}]."""
    data = await bing_get(ctx, api_key, "GetQueryStats", {"siteUrl": site_url})
    rows = data.get("d") or []
    return [
        {
            "query": r.get("Query", ""),
            "clicks": r.get("Clicks", 0),
            "impressions": r.get("Impressions", 0),
            "avg_click_position": r.get("AvgClickPosition", 0),
            "avg_impression_position": r.get("AvgImpressionPosition", 0),
            "date_ms": _bing_date_to_epoch_ms(r.get("Date", "")),
        }
        for r in rows
    ]


async def bing_get_page_stats(ctx, api_key: str, site_url: str) -> list[dict]:
    """Per-page search performance for one verified site (Bing's Search
    Performance report, page dimension instead of query).

    Returns [{"page", "clicks", "impressions", "avg_click_position",
    "avg_impression_position", "date_ms"}]."""
    data = await bing_get(ctx, api_key, "GetPageStats", {"siteUrl": site_url})
    rows = data.get("d") or []
    return [
        {
            "page": r.get("Query", ""),  # Bing's PageStats reuses the QueryStats shape; the "Query" field holds the page URL
            "clicks": r.get("Clicks", 0),
            "impressions": r.get("Impressions", 0),
            "avg_click_position": r.get("AvgClickPosition", 0),
            "avg_impression_position": r.get("AvgImpressionPosition", 0),
            "date_ms": _bing_date_to_epoch_ms(r.get("Date", "")),
        }
        for r in rows
    ]


async def bing_get_rank_and_traffic_stats(ctx, api_key: str, site_url: str) -> list[dict]:
    """Daily clicks/impressions trend for one verified site (site-wide, no
    query/page breakdown) — good for a small trend chart.

    Returns [{"clicks", "impressions", "date_ms"}]."""
    data = await bing_get(ctx, api_key, "GetRankAndTrafficStats", {"siteUrl": site_url})
    rows = data.get("d") or []
    return [
        {
            "clicks": r.get("Clicks", 0),
            "impressions": r.get("Impressions", 0),
            "date_ms": _bing_date_to_epoch_ms(r.get("Date", "")),
        }
        for r in rows
    ]
