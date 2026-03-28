# Ask Edgar Dilution Monitor

A real-time desktop overlay that monitors your trading platform for ticker changes and instantly displays dilution risk data from [Ask Edgar](https://askedgar.io).

When you switch tickers in DAS Trader Pro or thinkorswim, the overlay automatically fetches and shows:

- **Dilution risk ratings** – Overall risk, offering ability, dilution level, frequency, cash need, warrants
- **Float & outstanding shares** – With market cap, sector, and country
- **Recent news & SEC filings** – 8-K, 6-K, and news headlines with clickable links
- **Grok AI summary** – Latest AI-generated analysis
- **Offering ability breakdown** – Shelf capacity, ATM capacity, pending S-1/F-1 registrations
- **In-play dilution** – Active warrants and convertibles near current price, color-coded by risk
- **JMT415 analyst notes** – Recent analyst commentary
- **Management commentary** – From Ask Edgar's dilution analysis

## What It Looks Like

The app runs as a dark-themed, always-on-top overlay panel. It sits alongside your trading platform and updates automatically as you click through tickers.

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
| **API Access** | [Ask Edgar](https://askedgar.io) API trial key |

### How Platform Detection Works

- **DAS Trader Pro**: Monitors montage windows (`TICKER     0 -- 0     Company Name...`) and chart windows (`TICKER--5 Minute--`). Any ticker change in any montage or chart window triggers the overlay.
- **thinkorswim**: Monitors detached chart windows (`PRSO, MOBX, TURB - Charts - ...`). When a new ticker is entered in a chart tab, the overlay picks it up.

The app polls window titles every 1 second and detects when a ticker changes.

**ToS limitations**: Only *detached* chart windows are detected — charts embedded in the main ToS window (`Main@thinkorswim`) don't expose the active ticker in their window title. Switching between existing chart tabs also won't trigger a change since all tab tickers are always listed in the title. For best results with ToS, use detached chart windows and enter new tickers rather than clicking existing tabs.

## Quick Start (No coding experience needed)

### 1. Install Python

Download Python from [python.org/downloads](https://www.python.org/downloads/) and install it.

**IMPORTANT:** During installation, check the box that says **"Add Python to PATH"** — this is required.

### 2. Download this app

Click the green **"Code"** button at the top of this page, then click **"Download ZIP"**.

Extract the ZIP file to a folder on your computer (e.g. your Desktop).

### 3. Run the setup

Open the extracted folder and **double-click `setup.bat`**. This will:
- Install the required Python packages
- Create a `.env` file for your API key

### 4. Add your API key

Open the `.env` file (in the same folder) with Notepad and replace `your_api_key_here` with your actual API key:

```
ASKEDGAR_API_KEY=paste_your_key_here
```

**Don't have a key?** Request a free trial at [askedgar.io](https://share-na2.hsforms.com/1mRWaNy8PRFuCZr5YJvjdQQqjkci). One key works for all endpoints.

### 5. Launch the app

**Double-click `run.bat`** to start the overlay.

Open DAS Trader Pro or thinkorswim alongside it. Click on a ticker and the data loads automatically.

To stop the app, just close the overlay window (click the X) or close the command prompt window that opened with it.

---

<details>
<summary><b>Alternative: Setup via command line</b></summary>

```bash
git clone https://github.com/jasontange/Ask-Edgar-Dilution-Monitor-Public.git
cd Ask-Edgar-Dilution-Monitor-Public
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API key
python das_monitor.py
```

</details>

## How to Customize (Vibe Coding)

This is a single Python file — no frameworks, no build tools. You can customize it with an AI coding assistant like **Claude Code**, **Cursor**, or **GitHub Copilot** in VS Code.

### Setting up your editor

1. Install [VS Code](https://code.visualstudio.com/) or [Cursor](https://cursor.com/)
2. Open the extracted folder: **File > Open Folder** and select the app folder
3. You should see `das_monitor.py` in the file list on the left — that's the entire app

### Example: Change the window size

Try asking your AI assistant:

> "Make the overlay window wider — change it from 480px to 600px"

It will find this line in `das_monitor.py` and update it:

```python
# Before
self.root.geometry("480x620+50+50")

# After
self.root.geometry("600x620+50+50")
```

To test your change, run the app from the terminal in VS Code (`` Ctrl+` `` to open it):

```bash
python das_monitor.py
```

Or just double-click `run.bat` again.

### Other things you can customize

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
