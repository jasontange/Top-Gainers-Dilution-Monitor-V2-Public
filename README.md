# Ask Edgar Dilution Monitor

A real-time desktop overlay that monitors your trading platform for ticker changes and instantly displays dilution risk data from [Ask Edgar](https://askedgar.io).

When you switch tickers in DAS Trader Pro or thinkorswim, the overlay automatically fetches and shows:

- **Top Gainers panel** – Real-time pre-market/intraday gainers with Ask Edgar dilution data
- **Dilution risk ratings** – Overall risk, offering ability, dilution level, frequency, cash need, warrants
- **Float & outstanding shares** – With market cap, sector, and country
- **Recent news & SEC filings** – 8-K, 6-K, and news headlines with clickable links
- **Grok AI summary** – Latest AI-generated analysis
- **Offering ability breakdown** – Shelf capacity, ATM capacity, pending S-1/F-1 registrations
- **In-play dilution** – Active warrants and convertibles near current price, color-coded by risk
- **Recent offerings** – Historical offering data with ATM detection
- **Gap statistics** – Gap-up performance metrics with color-coded thresholds
- **JMT415 analyst notes** – Recent analyst commentary
- **Management commentary** – From Ask Edgar's dilution analysis
- **Ownership data** – Latest reported insider/institutional holdings

## What It Looks Like

The app runs as a dark-themed, always-on-top overlay with two panels. The left panel shows top gainers, and the right panel shows detailed dilution data for the selected ticker. It sits alongside your trading platform and updates automatically as you click through tickers.

- Risk badges are color-coded: **red** (high), **orange** (medium), **green** (low)
- News items have colored stripes: **cyan** (news), **orange** (8-K/6-K), **purple** (grok)
- Warrants/convertibles highlight **green** if strike/conversion price is at or below current price (in the money), **orange** otherwise
- Pending S-1/F-1 registrations are bolded in red as a warning
- Everything is clickable – badges link to Ask Edgar, news links to source documents

## Compatibility

| Requirement | Details |
|---|---|
| **OS** | Windows only (uses `win32gui` for window detection) |
| **Python** | 3.10+ |
| **Trading Platforms** | DAS Trader Pro, thinkorswim (TD Ameritrade / Charles Schwab) |
| **API Access** | [Ask Edgar](https://www.askedgar.io/api-trial) API key (required) + [TradingView](https://www.tradingview.com) account (free, for real-time prices) |

## Getting Started (Recommended: Use an AI Coding Assistant)

If you're new to coding or "vibe coding," the easiest way to get this running is to let an AI assistant handle the setup for you. This avoids common pitfalls like installing Python wrong, messing up API keys in the `.env` file, or missing dependencies.

### Step 1: Install VS Code + Claude Code

1. Download and install [VS Code](https://code.visualstudio.com/)
2. Install the **Claude Code** extension from the VS Code marketplace

### Step 2: Ask Claude to clone and set up the project

Open Claude Code in VS Code and tell it:

> "I want to clone this GitHub repo and set it up: https://github.com/jasontange/Top-Gainers-Dilution-Monitor-V2-Public"

Claude will:
- Install **git** if you don't have it
- Clone the repo to your machine
- Install **Python** if needed
- Install all required packages (`pip install -r requirements.txt`)
- Create your `.env` file and walk you through adding your API key and TradingView session cookie
- Launch the app for you

### Step 3: Get your Ask Edgar API key

Request a free trial key at [askedgar.io/api-trial](https://www.askedgar.io/api-trial) — one key works for all endpoints.

Claude will prompt you to paste it into your `.env` file during setup.

### Step 4: Set up real-time prices (optional but recommended)

The top gainers panel uses TradingView for price data. Without a session cookie, prices are 15 minutes delayed. To get **real-time prices**:

1. Log into [tradingview.com](https://www.tradingview.com) in Chrome (a free account works)
2. Press **F12** to open Developer Tools
3. Click the **Application** tab at the top
4. In the left sidebar, click **Cookies** → `https://www.tradingview.com`
5. Find the row named **`sessionid`** and copy the **Value**
6. Paste it into your `.env` file as: `TRADINGVIEW_SESSION_ID=paste_your_value_here`

This only needs to be done once — the cookie lasts for months.

### Step 5: Customize it

Once it's running, you can ask Claude to make changes:

> "Make the overlay window wider"
> "Add support for Interactive Brokers"
> "Change the background color to navy blue"

This is a single Python file — no frameworks, no build tools. AI assistants can easily read and modify it.

---

<details>
<summary><b>Manual Setup (if you prefer doing it yourself)</b></summary>

### 1. Install Python

Download Python from [python.org/downloads](https://www.python.org/downloads/) and install it.

**IMPORTANT:** During installation, check the box that says **"Add Python to PATH"** — this is required.

### 2. Download this app

Click the green **"Code"** button at the top of this page, then click **"Download ZIP"**.

Extract the ZIP file to a folder on your computer (e.g. your Desktop).

### 3. Install dependencies

Open a command prompt in the extracted folder and run:

```
pip install -r requirements.txt
```

### 4. Add your API key

Copy `.env.example` to `.env` and fill in your keys:

```
ASKEDGAR_API_KEY=paste_your_askedgar_key_here
TRADINGVIEW_SESSION_ID=paste_your_session_id_here
```

**Don't have a key?**
- Ask Edgar: Request a free trial at [askedgar.io/api-trial](https://www.askedgar.io/api-trial)

**TradingView session cookie** (for real-time prices):
1. Log into tradingview.com in Chrome
2. Press F12 → Application → Cookies → `https://www.tradingview.com`
3. Copy the `sessionid` value

### 5. Launch the app

```
python das_monitor.py
```

Or double-click `run.bat`.

Open DAS Trader Pro or thinkorswim alongside it. Click on a ticker and the data loads automatically.

</details>

<details>
<summary><b>Alternative: Setup via command line</b></summary>

```bash
git clone https://github.com/jasontange/Top-Gainers-Dilution-Monitor-V2-Public.git
cd Top-Gainers-Dilution-Monitor-V2-Public
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API key and TradingView session cookie
python das_monitor.py
```

</details>

## Customization Ideas

| What | Where to look | Example prompt for your AI assistant |
|---|---|---|
| **Window size/position** | `geometry("480x620+50+50")` | "Make the overlay 600px wide" |
| **Colors** | Color constants at the top | "Change the background to navy blue" |
| **Poll speed** | `POLL_INTERVAL = 1.0` | "Check for ticker changes every 0.5 seconds" |
| **News count** | `fetch_news_and_grok` | "Show 5 news headlines instead of 2" |
| **Platform support** | `find_montage_windows` | "Add support for Interactive Brokers TWS" |

### Adding support for other trading platforms

Ask your AI assistant something like:

> "Add support for [platform name] — it needs to detect the active ticker from the window title"

The AI will need to know how your platform formats its window titles. You can find out by asking:

> "Print all visible window titles on my screen so I can find my trading platform"

## Tech Stack

- **Python 3.10+** with tkinter (built-in GUI)
- **win32gui** (pywin32) for Windows window enumeration
- **tradingview-screener** for real-time market data
- **requests** for API calls
- **python-dotenv** for loading `.env` files

No frameworks, no build tools, no npm. Just one Python file.

## License

MIT – do whatever you want with it.
