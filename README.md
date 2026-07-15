# Bing Webmaster Connector

Imperal Cloud extension — Bing search performance (queries, pages, traffic
trend, verified sites) straight from the real Bing Webmaster Tools API.

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
SE Ranking connector (`accounts.py`, secret `bing_accounts`, `write_mode`
`extension`). The sidebar panel lists every connected account with the
active one marked; click any other to switch, or disconnect one without
touching the rest.

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
limit parameters** — every query/page/traffic call always returns everything
Bing currently has, weekly-bucketed for queries/pages and daily for the
traffic trend. We never fabricate filtering it doesn't support.

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

Full request/response contract: [`docs/bing-webmaster-api.openapi.yaml`](docs/bing-webmaster-api.openapi.yaml).

## Account management tools

- `connection_status` — is any Bing account connected right now.
- `save_bing_key` — connect a new account (validates the key against Bing's
  `GetUserSites` before saving; rejects invalid keys with a clear message).
- `list_bing_accounts` — every connected account, active one marked.
- `switch_bing_account` — make a different connected account active.
- `disconnect_bing_account` — remove one connected account, others untouched.

## Tests

```bash
python -m venv .venv && .venv/bin/pip install imperal-sdk pytest pytest-asyncio
.venv/bin/python -m pytest tests/ -v
```

34 tests, no network calls — `accounts.py`'s multi-account logic, real Bing
response-shape parsing (`response_models.py`, verbatim example payloads from
Microsoft's own docs), and every chat-function handler (success + error
paths) via `MockContext`/`MockSecretStore`.
