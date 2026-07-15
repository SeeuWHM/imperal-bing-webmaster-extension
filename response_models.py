"""Pydantic response models for Bing Webmaster Connector chat functions.

Every @chat.function(action_type="read") declares a data_model so the
platform validates return shapes and prevents naming drift (federal V23).
Return raw facts (ICNLI) — the narrator owns phrasing. Field names are
normalized to the same shape GSC/SE Ranking use (query/clicks/impressions/
position) so Webbee and article-writer see one consistent schema regardless
of source engine.
"""
from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field


class SiteRecord(BaseModel):
    site_url: str = ""
    is_verified: bool = False


class SiteList(BaseModel):
    sites: List[SiteRecord] = Field(default_factory=list)
    count: int = 0


class ConnectionStatus(BaseModel):
    connected: bool = False
    masked_key: str = ""


class AccountRecord(BaseModel):
    label: str = ""
    masked_key: str = ""
    is_active: bool = False


class AccountsList(BaseModel):
    accounts: List[AccountRecord] = Field(default_factory=list)
    count: int = 0


class AccountSwitched(BaseModel):
    active: str = ""


class AccountDisconnected(BaseModel):
    label: str = ""
    remaining: int = 0


class QueryRow(BaseModel):
    """One row from GetQueryStats — Bing's weekly query-level performance."""
    query: str = ""
    clicks: int = 0
    impressions: int = 0
    avg_click_position: float = 0.0
    avg_impression_position: float = 0.0
    date: str = ""


class QueryList(BaseModel):
    site_url: str = ""
    rows: List[QueryRow] = Field(default_factory=list)
    count: int = 0


class PageRow(BaseModel):
    """One row from GetPageStats — Bing's weekly page-level performance."""
    page: str = ""
    clicks: int = 0
    impressions: int = 0
    avg_click_position: float = 0.0
    avg_impression_position: float = 0.0
    date: str = ""


class PageList(BaseModel):
    site_url: str = ""
    rows: List[PageRow] = Field(default_factory=list)
    count: int = 0


class TrafficRow(BaseModel):
    """One row from GetRankAndTrafficStats — Bing's daily site-wide traffic."""
    date: str = ""
    clicks: int = 0
    impressions: int = 0


class TrafficStats(BaseModel):
    site_url: str = ""
    rows: List[TrafficRow] = Field(default_factory=list)
    count: int = 0


def _bing_date(raw: str) -> str:
    """Bing's JSON API returns .NET-style dates: '/Date(1699920000000)/'.
    Convert to an ISO date string (UTC) — never guess/fabricate a value."""
    if not raw or "Date(" not in raw:
        return raw or ""
    try:
        ms = int(raw.split("Date(")[1].split(")")[0].split("+")[0].split("-")[0])
        import datetime
        return datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc).date().isoformat()
    except Exception:
        return raw


def build_query_list(site_url: str, rows: list[dict]) -> QueryList:
    qrows = [
        QueryRow(
            query=r.get("Query", ""), clicks=r.get("Clicks", 0),
            impressions=r.get("Impressions", 0),
            avg_click_position=r.get("AvgClickPosition", 0.0),
            avg_impression_position=r.get("AvgImpressionPosition", 0.0),
            date=_bing_date(r.get("Date", "")),
        )
        for r in rows
    ]
    return QueryList(site_url=site_url, rows=qrows, count=len(qrows))


def build_page_list(site_url: str, rows: list[dict]) -> PageList:
    prows = [
        PageRow(
            page=r.get("Query", ""),  # Bing's GetPageStats reuses the QueryStats shape; "Query" holds the page URL here
            clicks=r.get("Clicks", 0),
            impressions=r.get("Impressions", 0),
            avg_click_position=r.get("AvgClickPosition", 0.0),
            avg_impression_position=r.get("AvgImpressionPosition", 0.0),
            date=_bing_date(r.get("Date", "")),
        )
        for r in rows
    ]
    return PageList(site_url=site_url, rows=prows, count=len(prows))


def build_traffic_stats(site_url: str, rows: list[dict]) -> TrafficStats:
    trows = [
        TrafficRow(
            date=_bing_date(r.get("Date", "")),
            clicks=r.get("Clicks", 0),
            impressions=r.get("Impressions", 0),
        )
        for r in rows
    ]
    return TrafficStats(site_url=site_url, rows=trows, count=len(trows))


def build_site_list(rows: list[dict]) -> SiteList:
    return SiteList(
        sites=[SiteRecord(site_url=r.get("Url", ""), is_verified=bool(r.get("IsVerified", False))) for r in rows],
        count=len(rows),
    )


def build_accounts_list(accounts: list[dict]) -> AccountsList:
    from accounts import _mask
    return AccountsList(
        accounts=[
            AccountRecord(label=a.get("label", ""), masked_key=_mask(a.get("api_key", "")),
                          is_active=bool(a.get("is_active")))
            for a in accounts
        ],
        count=len(accounts),
    )
