# Ask Edgar Dilution Monitor

A real-time desktop overlay that monitors your trading platform for ticker changes and instantly displays dilution risk data from [Ask Edgar](https://askedgar.io).

When you switch tickers in DAS Trader Pro or thinkorswim, the overlay automatically fetches and shows:

- **Top Gainers panel** – Pre-market/intraday gainers filtered to common stock tickers, with Ask Edgar dilution data
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
| **API Access** | [Ask Edgar](https://www.askedgar.io/api-trial) API key + [Massive](https://massive.com) API key |

### How Platform Detection Works

- **DAS Trader Pro**: Monitors montage windows (`TICKER     0 -- 0     Company Name...`) and chart windows (`TICKER--5 Minute--`). Any ticker change in any montage or chart window triggers the overlay.
- **thinkorswim**: Monitors detached chart windows (`PRSO, MOBX, TURB - Charts - ...`). When a new ticker is entered in a chart tab, the overlay picks it up.

The app polls window titles every 1 second and detects when a ticker changes.

**ToS limitations**: Only *detached* chart windows are detected — charts embedded in the main ToS window (`Main@thinkorswim`) don't expose the active ticker in their window title. Switching between existing chart tabs also won't trigger a change since all tab tickers are always listed in the title. For best results with ToS, use detached chart windows and enter new tickers rather than clicking existing tabs.

## Getting Started (Recommended: Use an AI Coding Assistant)

If you're new to coding or "vibe coding," the easiest way to get this running is to let an AI assistant handle the setup for you. This avoids common pitfalls like installing Python wrong, messing up API keys in the `.env` file, or missing dependencies.

### Step 1: Install VS Code + Claude Code

1. Download and install [VS Code](https://code.visualstudio.com/)
2. Install the **Claude Code** extension from the VS Code marketplace

### Step 2: Ask Claude to clone and set up the project

Open Claude Code in VS Code and tell it:

> "I want to clone this GitHub repo and set it up: https://github.com/jasontange/Ask-Edgar-Dilution-Monitor-Public"

Claude will:
- Install **git** if you don't have it
- Clone the repo to your machine
- Install **Python** if needed
- Install all required packages (`pip install -r requirements.txt`)
- Create your `.env` file and walk you through adding your API keys
- Launch the app for you

### Step 3: Get your API keys

You'll need two API keys:

| Key | Where to get it |
|---|---|
| **Ask Edgar API** | Request a free trial at [askedgar.io/api-trial](https://www.askedgar.io/api-trial) — one key works for all endpoints |
| **Massive API** | Sign up at [massive.com](https://massive.com) for market data (top gainers) |

Claude will prompt you to paste these into your `.env` file during setup.

### Step 4: Customize it

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

### 3. Run the setup

Open the extracted folder and **double-click `setup.bat`**. This will:
- Install the required Python packages
- Create a `.env` file for your API keys

### 4. Add your API keys

Open the `.env` file (in the same folder) with Notepad and add your keys:

```
ASKEDGAR_API_KEY=paste_your_askedgar_key_here
POLYGON_API_KEY=paste_your_massive_key_here
```

**Don't have keys?**
- Ask Edgar: Request a free trial at [askedgar.io/api-trial](https://www.askedgar.io/api-trial)
- Massive: Sign up at [massive.com](https://massive.com)

### 5. Launch the app

**Double-click `run.bat`** to start the overlay.

Open DAS Trader Pro or thinkorswim alongside it. Click on a ticker and the data loads automatically.

To stop the app, just close the overlay window (click the X) or close the command prompt window that opened with it.

</details>

<details>
<summary><b>Alternative: Setup via command line</b></summary>

```bash
git clone https://github.com/jasontange/Ask-Edgar-Dilution-Monitor-Public.git
cd Ask-Edgar-Dilution-Monitor-Public
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
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
- **requests** for API calls
- **python-dotenv** for loading `.env` files

No frameworks, no build tools, no npm. Just one Python file.

## License

MIT – do whatever you want with it.
