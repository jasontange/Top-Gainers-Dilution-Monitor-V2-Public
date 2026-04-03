# Ask Edgar Dilution Monitor

## Project Overview

This is a single-file Python tkinter desktop app (`das_monitor.py`) that runs as an always-on-top overlay for day traders. It has two panels:

- **Left panel**: Top pre-market/intraday gainers from TradingView (real-time with session cookie), filtered to 2-4 letter uppercase common stock tickers, enriched with Ask Edgar dilution ratings
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

Everything is in `das_monitor.py` (~1500 lines). No separate modules, no frameworks.

### Key sections:

1. **Config & constants** (top) — API URLs, keys, colors, fonts
2. **API cache** — `_cached_fetch()` caches Ask Edgar responses for 30 minutes (except news)
3. **API fetch functions** — `fetch_dilution_data()`, `fetch_float_data()`, `fetch_news_and_grok()`, `fetch_in_play_dilution()`, `fetch_gap_stats()`, `fetch_offerings()`, `fetch_ownership()`, `fetch_chart_analysis()`, `fetch_top_gainers()`
4. **Window detection** — `find_montage_windows()` for DAS, `find_tos_chart_windows()` for thinkorswim
5. **`DilutionOverlay` class** — The main tkinter app with all UI rendering methods
6. **Card rendering methods** — `_add_offering_ability_card()`, `_add_gap_stats_card()`, `_add_offerings_card()`, `_add_in_play_section()`, `_add_ownership_card()`, etc.

### Data flow:

1. `_poll_windows()` runs every 1 second, checks for ticker changes
2. On change, `_on_ticker_change()` spawns a background thread
3. Thread makes parallel API calls via `ThreadPoolExecutor` (10 workers)
4. Results are passed back to the UI thread via `root.after(0, callback)`
5. UI clears and rebuilds the right panel with fresh data

### Top gainers data flow:

1. `fetch_top_gainers()` uses `tradingview-screener` package to query TradingView scanner API
2. If `TRADINGVIEW_SESSION_ID` is set, passes cookies for real-time data; otherwise falls back to 15-min delayed
3. Filters to 2-4 letter tickers with `premarket_change > MIN_GAINER_PCT` (15%)
4. Enriches each ticker in parallel with Ask Edgar float, dilution, chart analysis, and news data

### Right panel card order:

1. Feed (news + grok)
2. Risk badges (grid)
3. Offering Ability
4. In Play Dilution
5. Recent Offerings
6. Gap Stats
7. JMT415 Notes
8. Mgmt Commentary
9. Ownership

### Ask Edgar API endpoints used:

| Endpoint | Function |
|---|---|
| `/v1/dilution-rating` | `fetch_dilution_data()` |
| `/v1/float` | `fetch_float_data()` |
| `/v1/news` | `fetch_news_and_grok()` |
| `/v1/screener` | `fetch_last_price()` |
| `/v1/dilution-data` | `fetch_in_play_dilution()` |
| `/v1/ai-chart-analysis` | `fetch_chart_analysis()` |
| `/v1/gap-stats` | `fetch_gap_stats()` |
| `/v1/offerings` | `fetch_offerings()` |
| `/v1/ownership` | `fetch_ownership()` |

All Ask Edgar endpoints use the same API key via `API-KEY` header.

### API Caching:

All Ask Edgar endpoints (except news) are cached for 30 minutes per ticker using `_cached_fetch()`. News (`fetch_news_and_grok`) is always live. Cache is in-memory only — cleared on app restart. Failed requests (returning `None`) are not cached so they retry on next request.

## Common Issues

- **"ASKEDGAR_API_KEY not set"** — The `.env` file is missing or the key is blank. Create `.env` from `.env.example` and paste the API key.
- **`ModuleNotFoundError: win32gui`** — Run `pip install pywin32`. This only works on Windows.
- **`ModuleNotFoundError: tradingview_screener`** — Run `pip install tradingview-screener`.
- **Top gainers show delayed data** — Add `TRADINGVIEW_SESSION_ID` to `.env` for real-time data. See setup instructions above.
- **App doesn't detect my platform** — Only DAS Trader Pro and thinkorswim (detached charts) are supported. The user can ask you to add support for other platforms by detecting their window title format.
- **"No data" for a ticker** — The ticker may not be in Ask Edgar's database. This is normal for non-dilution stocks. Other cards (news, gap stats, offerings) will still show if data exists.

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
