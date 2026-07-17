# Bing Webmaster Connector

[![Imperal SDK](https://img.shields.io/badge/imperal--sdk-5.9-blue)](https://pypi.org/project/imperal-sdk/)
[![Version](https://img.shields.io/badge/version-1.1.1-green)](https://github.com/SeeuWHM/imperal-bing-webmaster-extension/releases)
[![License](https://img.shields.io/badge/license-LGPL--2.1-orange)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Imperal%20Cloud-purple)](https://panel.imperal.io)

**Bing search performance extension for [Imperal Cloud](https://panel.imperal.io).**

Queries, pages, traffic trend, and verified sites — straight from the real Bing Webmaster Tools API, no OAuth required.

---

## What It Does

Talk to it naturally:

```
"show my top queries on webhostmost.com"
"how's my Bing traffic trending this month"
"which pages are getting impressions but no clicks"
"list my verified Bing sites"
"connect my Bing Webmaster account"
"switch to my other Bing account"
```

Or use the sidebar panel — every connected account is listed with the active
one marked; switch, disconnect, or add another account inline without leaving
the workspace.

---

## Why this is simpler than Google Search Console

GSC needs OAuth because Google's Search Console data is only reachable via a
signed-in Google account. **Bing Webmaster Tools issues a plain per-user API
key** (Settings → API Access → Generate API Key) — no OAuth dance, no client
ID/secret, no consent screen. This extension calls
`https://ssl.bing.com/webmaster/api.svc/json/` directly with `ctx.http`,
forwarding the caller's own key as a query parameter, exactly like the SE
Ranking connector's key-based model — except Bing's API is public and free,
so there's no shared backend microservice / credit-metering proxy in the
loop either.

## Multi-account

Several Bing Webmaster accounts (each with its own API key) can be connected
at once and switched between — same JSON-blob-in-`ctx.secrets` pattern as the
SE Ranking connector (`bing_accounts.py`, secret `bing_accounts`, `write_mode`
`extension`). The sidebar panel lists every connected account with the active
one marked; click any other to switch, disconnect one without touching the
rest, or expand an **inline "Add another account" form** right in the sidebar
(no separate overlay).

## Setup (for the end user)

1. Sign in at [bing.com/webmasters](https://www.bing.com/webmasters) with a
   Microsoft account.
2. Add your site — **you can import it straight from Google Search Console**
   with one click if it's already verified there; Bing reuses that
   verification instead of making you do DNS/meta-tag/file verification
   again.
3. Settings (gear icon) → **API Access** → **API Key** → generate one. That's
   the key this extension asks for.
4. Paste it into the sidebar's Connect form here (or via the platform's
   Secrets panel — same value, either way).

Data appears once Bing has crawled/indexed the site. Bing's own retention
window is roughly 6 months (vs GSC's ~16), and its API has **no date-range or
limit parameters** — every query/page/traffic call returns everything Bing
currently has, weekly-bucketed for queries/pages and daily for the traffic
trend. Because Bing returns one row **per query per week**, `top_queries` /
`top_pages` **aggregate** those weekly buckets into one row per query/page
(clicks + impressions summed, position = an impression-weighted average of
`AvgImpressionPosition`), sorted by clicks — otherwise the raw feed is
thousands of duplicated rows. We never fabricate filtering Bing doesn't support.

## Endpoints implemented

| Bing method | Our tool | Normalizes to |
|---|---|---|
| `GetUserSites` | `list_bing_sites` | `site_url`, `is_verified` |
| `GetQueryStats` | `top_queries` | `query`, `clicks`, `impressions`, `avg_click_position`, `avg_impression_position`, `date` |
| `GetPageStats` | `top_pages` | `page`, `clicks`, `impressions`, `avg_click_position`, `avg_impression_position`, `date` |
| `GetRankAndTrafficStats` | `traffic_stats` | `date`, `clicks`, `impressions` |

Field names deliberately mirror the Google Search Console connector's shape
(`query`/`clicks`/`impressions`/`position`) so Webbee and the Article Writer
extension see one consistent schema regardless of which search engine the
data came from.

> Note: Bing sets `AvgClickPosition = -1` for any bucket with zero clicks — we
> never surface that as a position; the "Avg position" shown is the
> impression-weighted `AvgImpressionPosition`. A `NotAuthorized` (code 14) from
> Bing (a site owned by a *different* connected account) is translated into a
> plain "pick a site from the active account, or switch account" message rather
> than a raw API error.

Full request/response contract: [`docs/bing-webmaster-api.openapi.yaml`](docs/bing-webmaster-api.openapi.yaml).

## Account management tools

- `connection_status` — is any Bing account connected right now.
- `save_bing_key` — connect a new account (validates the key against Bing's
  `GetUserSites` before saving; rejects invalid keys with a clear message).
- `list_bing_accounts` — every connected account, active one marked.
- `switch_bing_account` — make a different connected account active.
- `disconnect_bing_account` — remove one connected account, others untouched.

## Development / Tests

```bash
python -m venv .venv && .venv/bin/pip install imperal-sdk pytest pytest-asyncio
.venv/bin/python -m pytest tests/ -v
```

35 tests, no network calls — `bing_accounts.py`'s multi-account logic, real Bing
response-shape parsing + weekly-bucket aggregation (`response_models.py`, verbatim
example payloads from Microsoft's own docs), and every chat-function handler
(success + error paths) via `MockContext`/`MockSecretStore`.

---

## Built with

- [imperal-sdk](https://github.com/imperalcloud/imperal-sdk) 5.9
- [Imperal Cloud](https://panel.imperal.io)
