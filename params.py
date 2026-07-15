"""Pydantic param models for Bing Webmaster Connector chat functions."""
from __future__ import annotations

from pydantic import BaseModel, Field


class EmptyParams(BaseModel):
    """No input required."""


class SaveKeyParams(BaseModel):
    bing_api_key: str = Field(
        ..., min_length=1, max_length=200,
        description="Your Bing Webmaster API key, from bing.com/webmasters -> Settings -> API Access -> Generate API Key",
    )
    label: str = Field(
        default="", max_length=60,
        description="Optional display name for this account (e.g. 'Agency', 'Client X'). Auto-generated if omitted.",
    )


class AccountLabelParams(BaseModel):
    label: str = Field(..., description="Account label (from list_bing_accounts)")


class SiteUrlParams(BaseModel):
    site_url: str = Field(
        ..., description=(
            "One of your verified Bing Webmaster site URLs (from list_bing_sites), "
            "e.g. https://example.com/ — interpreted literally, never guessed or normalized."
        ),
    )
