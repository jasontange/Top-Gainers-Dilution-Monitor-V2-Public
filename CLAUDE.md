# Ask Edgar Dilution Monitor

These rules apply to every task in this project unless explicitly overridden.
Bias: caution over speed on non-trivial work. Use judgment on trivial tasks.

## Rules

### 1. Think Before Coding
State assumptions explicitly. If uncertain, ask rather than guess.
Present multiple interpretations when ambiguity exists.
Push back when a simpler approach exists. Stop when confused — name what's unclear.

### 2. Simplicity First
Minimum code that solves the problem. Nothing speculative.
No features beyond what was asked. No abstractions for single-use code.
Test: would a senior engineer say this is overcomplicated? If yes, simplify.

### 3. Surgical Changes
Touch only what you must. Clean up only your own mess.
Don't "improve" adjacent code, comments, or formatting.
Don't refactor what isn't broken. Match existing style.

### 4. Goal-Driven Execution
Define success criteria. Loop until verified.
Don't follow steps blindly — define success and iterate.
Strong success criteria let you loop independently.

### 5. Use the model only for judgment calls
Use me for: classification, drafting, summarization, extraction.
Do NOT use me for: routing, retries, deterministic transforms.
If code can answer, code answers.

### 6. Token budgets are not advisory
Per-task: 4,000 tokens. Per-session: 30,000 tokens.
If approaching budget, summarize and start fresh.
Surface the breach. Do not silently overrun.

### 7. Surface conflicts, don't average them
If two patterns contradict, pick one (more recent / more tested).
Explain why. Flag the other for cleanup. Don't blend conflicting patterns.

### 8. Read before you write
Before adding code, read exports, immediate callers, shared utilities.
"Looks orthogonal" is dangerous. If unsure why code is structured a way, ask.

### 9. Tests verify intent, not just behavior
Tests must encode WHY behavior matters, not just WHAT it does.
A test that can't fail when business logic changes is wrong.

### 10. Checkpoint after every significant step
Summarize what was done, what's verified, what's left.
Don't continue from a state you can't describe back.
If you lose track, stop and restate.

### 11. Match the codebase's conventions, even if you disagree
Conformance > taste inside the codebase.
If you genuinely think a convention is harmful, surface it. Don't fork silently.

### 12. Fail loud
"Completed" is wrong if anything was skipped silently.
"Tests pass" is wrong if any were skipped.
Default to surfacing uncertainty, not hiding it.

---

## Project Overview

This is a single-file Python tkinter desktop app (`das_monitor.py`) that runs as an always-on-top overlay for day traders. It has two panels:

- **Left panel**: Top pre-market/intraday gainers filtered to 2-4 letter uppercase common stock tickers, enriched with Ask Edgar dilution ratings (top 10 only)
- **Right panel**: Detailed dilution data for the selected ticker from Ask Edgar APIs
- **Search box**: Manual ticker entry at the top

The app monitors DAS Trader Pro and thinkorswim window titles to auto-detect ticker changes.

## Audience

Users are primarily **day traders who are new to coding** ("vibe coders"). They may not know how to:

- Install Python or git
- Use the command line
- Edit `.env` files correctly
- Install pip packages
- Debug import errors or missing dependencies

When helping users, provide clear step-by-step guidance. Offer to execute commands on their behalf when possible. If something fails, explain what went wrong in plain language.

## Setup Requirements

### API Keys & Cookies (stored in `.env`)

| Variable | Source | Purpose |
|---|---|---|
| `ASKEDGAR_API_KEY` | [askedgar.io/api-trial](https://www.askedgar.io/api-trial) | Dilution data, news, filings, gap stats, offerings — one key for all endpoints |
| `TRADINGVIEW_SESSION_ID` | Chrome DevTools (see below) | Real-time price data from TradingView (optional — falls back to 15-min delayed without it) |

The `.env` file should be in the project root alongside `das_monitor.py`. It is git-ignored.

#### Getting the TradingView session cookie:
1. Log into TradingView in Chrome
2. Press F12 → Application tab → Cookies → `https://www.tradingview.com`
3. Copy the `sessionid` value
4. Paste into `.env` as `TRADINGVIEW_SESSION_ID=your_value`

The cookie lasts for months — only needs to be redone if you log out of TradingView.

### Python Dependencies

Listed in `requirements.txt`. Install with `pip install -r requirements.txt`. Key packages:

- `pywin32` — Windows API for window title detection
- `requests` — HTTP client for API calls
- `python-dotenv` — Loads `.env` file
- `tradingview-screener` — TradingView scanner API for real-time top gainers

### Platform

Windows only — uses `win32gui` for enumerating desktop windows.

## Architecture

Everything is in `das_monitor.py` (~1770 lines). No separate modules, no frameworks.

### Key sections:

1. **Config & constants** (top) — API URLs, keys, colors, fonts
2. **API cache** — `_cached_fetch()` caches Ask Edgar responses for 30 minutes, including no-data responses (sentinel pattern)
3. **API fetch functions** — `fetch_dilution_data()`, `fetch_screener_data()`, `fetch_news_and_grok()`, `_cached_news_results()`, `fetch_in_play_dilution()`, `fetch_gap_stats()`, `fetch_offerings()`, `fetch_ownership()`, `fetch_split_status()`, `fetch_chart_analysis()`, `fetch_top_gainers()`
4. **Window detection** — `find_montage_windows()` for DAS, `find_tos_tickers()` for thinkorswim
5. **`DilutionOverlay` class** — The main tkinter app with all UI rendering methods
6. **Card rendering methods** — `_add_offering_ability_card()`, `_add_gap_stats_card()`, `_add_offerings_card()`, `_add_in_play_section()`, `_add_split_status_card()`, `_add_ownership_card()`, etc.

### Data flow:

1. `_start_monitor()` polls windows every 1 second, checks for ticker changes
2. On change, `_on_ticker_change()` spawns a background thread
3. Thread makes API calls to all Ask Edgar endpoints for the ticker
4. Results are passed back to the UI thread via `root.after(0, callback)`
5. UI clears and rebuilds the right panel with fresh data

### Top gainers data flow:

1. `fetch_top_gainers()` queries for top gaining tickers via TradingView scanner API
2. If `TRADINGVIEW_SESSION_ID` is set, passes cookies for real-time data; otherwise falls back to 15-min delayed
3. Filters to 2-4 letter tickers with `premarket_change > MIN_GAINER_PCT` (15%)
4. Enriches **top 10 only** in parallel (3 workers) with Ask Edgar screener, dilution rating, and news data
5. Tickers beyond top 10 are shown without enrichment to conserve API calls

### Right panel card order:

1. Feed (news + grok)
2. Risk badges (grid)
3. Offering Ability
4. In Play Dilution
5. Reverse Split Status
6. Recent Offerings
7. Gap Stats
8. JMT415 Notes
9. Mgmt Commentary
10. Ownership

### Ask Edgar API endpoints used:

| Endpoint | Function |
|---|---|
| `/v1/dilution-rating` | `fetch_dilution_data()` |
| `/v1/screener` | `fetch_screener_data()` — price, float, outstanding, market cap, sector, country |
| `/v1/news-basic` | `_cached_news_results()` / `fetch_news_and_grok()` |
| `/v1/dilution-data` | `fetch_in_play_dilution()` |
| `/v1/ai-chart-analysis` | `fetch_chart_analysis()` |
| `/v1/gap-stats` | `fetch_gap_stats()` |
| `/v1/offerings` | `fetch_offerings()` |
| `/v1/ownership` | `fetch_ownership()` |
| `/v1/split-status` | `fetch_split_status()` |

All Ask Edgar endpoints use the same API key via `API-KEY` header.

### API Caching:

All Ask Edgar endpoints are cached for 30 minutes per ticker using `_cached_fetch()`. Cache is in-memory only — cleared on app restart. Failed requests (returning `None`) **are cached** using a sentinel value (`_CACHE_SENTINEL`) to prevent retry storms against the API.

### In Play Dilution filtering:

- Warrants/convertibles filtered to exercise/conversion price <= 4x current stock price
- Items with `price_protection` containing "Variable" bypass the price filter
- "Not Registered" items are skipped, except convertibles filed >6 months ago
- Warrants with `$0.00` exercise price are still shown (not filtered as falsy)

### Reverse Split Status:

- Shows most recent 3 entries from `/v1/split-status`
- Stacked two-line layout: action type on top, date range below

## Common Issues

- **"ASKEDGAR_API_KEY not set"** — The `.env` file is missing or the key is blank. Create `.env` from `.env.example` and paste the API key.
- **`ModuleNotFoundError: win32gui`** — Run `pip install pywin32`. This only works on Windows.
- **`ModuleNotFoundError: tradingview_screener`** — Run `pip install tradingview-screener`.
- **Top gainers show delayed data** — Add `TRADINGVIEW_SESSION_ID` to `.env` for real-time data. See setup instructions above.
- **App doesn't detect my platform** — Only DAS Trader Pro and thinkorswim (detached charts) are supported. The user can ask you to add support for other platforms by detecting their window title format.
- **"No data" for a ticker** — The ticker may not be in Ask Edgar's database. This is normal for non-dilution stocks. Other cards (news, gap stats, offerings) will still show if data exists.
- **Rate limiting (429 errors)** — The API has per-minute and daily unique ticker limits. Enrichment is limited to top 10 gainers to conserve quota. Don't run multiple app instances simultaneously.
- **Stale cached data** — Restart the app to clear the in-memory cache. Cache TTL is 30 minutes.

## Running the App

```bash
python das_monitor.py
```

Or double-click `run.bat`.

## Customization

This is designed to be modified by AI coding assistants. Common requests:

- Changing window size, colors, fonts
- Adding support for other trading platforms
- Adding/removing data cards
- Changing the polling interval
- Modifying how data is displayed
