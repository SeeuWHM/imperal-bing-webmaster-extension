"""Skeleton context providers for Bing Webmaster — LLM context cache holding
ready answers. Degrades to configured:false WITHOUT calling Bing when
nothing is connected (never leak errors, never block routing). Lists capped
at 5 per the skeleton contract.
"""
from __future__ import annotations

from app import ext
from bing_accounts import _active_api_key, bing_ready
from bing_api import bing_get


@ext.skeleton("bing_config", ttl=300,
              description="Bing Webmaster connection status — whether the user has connected an API key")
async def skeleton_bing_config(ctx) -> dict:
    configured = await bing_ready(ctx)
    return {"response": {
        "configured": configured,
        "instruction": (
            "Bing Webmaster not connected — tell the user to call save_bing_key with their "
            "Bing Webmaster API key (bing.com/webmasters -> Settings -> API Access -> "
            "Generate API Key) before asking about their sites or search performance."
            if not configured else
            "Bing Webmaster is connected. Call list_bing_sites to see the user's properties."
        ),
    }}


@ext.skeleton("bing_sites", ttl=600,
              description="The user's Bing Webmaster properties — site URL and verification status (up to 5 shown)")
async def skeleton_bing_sites(ctx) -> dict:
    if not await bing_ready(ctx):
        return {"response": {"configured": False, "sites": [], "total": 0}}
    try:
        key = await _active_api_key(ctx)
        data = await bing_get(ctx, key, "GetUserSites")
        rows = data.get("d") or []
    except Exception as e:
        return {"response": {"configured": True, "sites": [], "total": 0, "error": str(e)}}
    return {"response": {
        "configured": True,
        "sites": [
            {"site_url": r.get("Url", ""), "is_verified": bool(r.get("IsVerified", False))}
            for r in rows[:5]
        ],
        "total": len(rows),
    }}
