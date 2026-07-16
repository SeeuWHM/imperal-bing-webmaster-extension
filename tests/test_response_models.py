"""Unit tests for response_models.py — parsing REAL Bing Webmaster API shapes
(taken verbatim from Microsoft's own docs / community API reference) into
our normalized pydantic models. No network.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from response_models import (
    _bing_date, build_accounts_list, build_page_list, build_query_list,
    build_site_list, build_traffic_stats,
)


# ─── date parsing ────────────────────────────────────────────────────────── #

def test_bing_date_parses_dotnet_epoch_ms():
    # /Date(1699920000000)/ == 2023-11-14T00:00:00Z
    assert _bing_date("/Date(1699920000000)/") == "2023-11-14"


def test_bing_date_passes_through_non_date_strings():
    assert _bing_date("") == ""
    assert _bing_date("already-iso") == "already-iso"


# ─── GetQueryStats -> QueryList ──────────────────────────────────────────── #

def test_build_query_list_maps_real_bing_shape():
    # Verbatim shape from Bing Webmaster API docs (GetQueryStats).
    raw = [
        {
            "__type": "QueryStats:#Microsoft.Bing.Webmaster.Api",
            "AvgClickPosition": 0,
            "AvgImpressionPosition": 27,
            "Clicks": 0,
            "Date": "/Date(1699920000000)/",
            "Impressions": 1,
            "Query": "www.getevents.co",
        },
    ]
    result = build_query_list("https://example.com/", raw)
    assert result.site_url == "https://example.com/"
    assert result.count == 1
    row = result.rows[0]
    assert row.query == "www.getevents.co"
    assert row.impressions == 1
    assert row.clicks == 0
    assert row.avg_impression_position == 27
    assert row.date == ""  # aggregated across weeks — no single bucket date


def test_build_query_list_aggregates_weekly_buckets():
    # Same query across weekly buckets must collapse to ONE row with summed
    # clicks/impressions and an impression-weighted avg position — never the
    # -1 that AvgClickPosition carries for zero-click weeks.
    raw = [
        {"Query": "free hosting", "Clicks": 0, "Impressions": 33,
         "AvgClickPosition": -1, "AvgImpressionPosition": 10, "Date": "/Date(1699920000000)/"},
        {"Query": "free hosting", "Clicks": 2, "Impressions": 39,
         "AvgClickPosition": 3, "AvgImpressionPosition": 8, "Date": "/Date(1700524800000)/"},
        {"Query": "cheap hosting", "Clicks": 5, "Impressions": 10,
         "AvgClickPosition": 2, "AvgImpressionPosition": 4, "Date": "/Date(1700524800000)/"},
    ]
    result = build_query_list("https://example.com/", raw)
    assert result.count == 2  # two unique queries, not three weekly rows
    by_q = {r.query: r for r in result.rows}
    fh = by_q["free hosting"]
    assert fh.clicks == 2
    assert fh.impressions == 72                    # 33 + 39
    assert fh.avg_impression_position == 8.9       # (10*33 + 8*39) / 72, never -1
    assert result.rows[0].query == "cheap hosting"  # sorted by clicks desc


def test_build_query_list_empty():
    result = build_query_list("https://example.com/", [])
    assert result.count == 0
    assert result.rows == []


# ─── GetPageStats -> PageList (reuses QueryStats shape; Query = page URL) ── #

def test_build_page_list_maps_query_field_to_page():
    raw = [
        {
            "__type": "QueryStats:#Microsoft.Bing.Webmaster.Api",
            "AvgClickPosition": 0,
            "AvgImpressionPosition": 16,
            "Clicks": 0,
            "Date": "/Date(1699920000000)/",
            "Impressions": 1,
            "Query": "http://help.analyticsedge.com/category/googleanalytics/",
        },
    ]
    result = build_page_list("https://example.com/", raw)
    assert result.count == 1
    assert result.rows[0].page == "http://help.analyticsedge.com/category/googleanalytics/"
    assert result.rows[0].impressions == 1


# ─── GetRankAndTrafficStats -> TrafficStats ──────────────────────────────── #

def test_build_traffic_stats_maps_real_bing_shape():
    raw = [
        {"__type": "RankAndTrafficStats:#Microsoft.Bing.Webmaster.Api",
         "Clicks": 1, "Date": "/Date(1699920000000)/", "Impressions": 30},
        {"__type": "RankAndTrafficStats:#Microsoft.Bing.Webmaster.Api",
         "Clicks": 2, "Date": "/Date(1700006400000)/", "Impressions": 100},
    ]
    result = build_traffic_stats("https://example.com/", raw)
    assert result.count == 2
    assert result.rows[0].clicks == 1
    assert result.rows[0].impressions == 30
    assert result.rows[1].clicks == 2


# ─── GetUserSites -> SiteList ─────────────────────────────────────────────── #

def test_build_site_list_maps_real_bing_shape():
    raw = [
        {"__type": "Site:#Microsoft.Bing.Webmaster.Api",
         "AuthenticationCode": "abc", "DnsVerificationCode": "xyz",
         "IsVerified": True, "Url": "http://example.com/"},
        {"__type": "Site:#Microsoft.Bing.Webmaster.Api",
         "AuthenticationCode": "abc", "DnsVerificationCode": "xyz",
         "IsVerified": False, "Url": "http://pending.example.com/"},
    ]
    result = build_site_list(raw)
    assert result.count == 2
    assert result.sites[0].site_url == "http://example.com/"
    assert result.sites[0].is_verified is True
    assert result.sites[1].is_verified is False


def test_build_site_list_empty():
    result = build_site_list([])
    assert result.count == 0


# ─── accounts -> AccountsList (masking) ──────────────────────────────────── #

def test_build_accounts_list_masks_keys():
    raw = [{"label": "Default", "api_key": "abcd1234", "is_active": True}]
    result = build_accounts_list(raw)
    assert result.count == 1
    assert result.accounts[0].label == "Default"
    assert result.accounts[0].masked_key == "••••1234"
    assert result.accounts[0].is_active is True
