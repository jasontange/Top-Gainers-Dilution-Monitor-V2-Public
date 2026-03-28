"""
DAS Trader Montage Monitor + Ask Edgar Dilution Overlay
-------------------------------------------------------
Monitors the active DAS Trader montage window for ticker changes,
fetches dilution risk data from the Ask Edgar API, and displays
results in an always-on-top overlay panel.

Includes Top Gainers panel with real-time market data.
"""

import os
import threading
import time
import webbrowser
import requests
import tkinter as tk
import win32gui
import re
from concurrent.futures import ThreadPoolExecutor

# Load .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Config ──────────────────────────────────────────────────────────────────
# API keys – set these as environment variables or in a .env file
# See .env.example for details
ASKEDGAR_API_KEY = os.environ.get("ASKEDGAR_API_KEY", "")

if not ASKEDGAR_API_KEY:
    print("ERROR: Missing API key. Copy .env.example to .env and fill in your key.")
    print("  ASKEDGAR_API_KEY - request trial at askedgar.io")

DILUTION_API_URL = "https://eapi.askedgar.io/enterprise/v1/dilution-rating"
DILUTION_API_KEY = ASKEDGAR_API_KEY
FLOAT_API_URL = "https://eapi.askedgar.io/enterprise/v1/float-outstanding"
FLOAT_API_KEY = ASKEDGAR_API_KEY
NEWS_API_URL = "https://eapi.askedgar.io/enterprise/v1/news"
NEWS_API_KEY = ASKEDGAR_API_KEY
DILDATA_API_URL = "https://eapi.askedgar.io/enterprise/v1/dilution-data"
DILDATA_API_KEY = ASKEDGAR_API_KEY
SCREENER_API_URL = "https://eapi.askedgar.io/enterprise/v1/screener"
SCREENER_API_KEY = ASKEDGAR_API_KEY
CHART_ANALYSIS_URL = "https://eapi.askedgar.io/v1/ai-chart-analysis"
CHART_ANALYSIS_KEY = ASKEDGAR_API_KEY
GAP_STATS_URL = "https://eapi.askedgar.io/v1/gap-stats"
GAP_STATS_KEY = ASKEDGAR_API_KEY
OFFERINGS_API_URL = "https://eapi.askedgar.io/v1/offerings"
OFFERINGS_API_KEY = ASKEDGAR_API_KEY
POLL_INTERVAL = 1.0

# Polygon / Market Data API
POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY", "c2ylbMmZhpwnJlo_cRAcjpha5Nn_ahUm")
POLYGON_GAINERS_URL = "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/gainers"
POLYGON_TICKER_URL = "https://api.massive.com/v3/reference/tickers"
GAINERS_REFRESH_SECS = 60

# Ticker filter: 2-4 uppercase letters, no periods or special chars
TICKER_RE = re.compile(r'^[A-Z]{2,4}$')

# ── Visual Style ────────────────────────────────────────────────────────────
BG = "#0D1014"
BG_CARD = "#151A20"
BG_ROW = "#1B2128"
BG_ROW_ALT = "#181D24"
BG_SELECTED = "#1A2A3A"
BORDER = "#232A33"
BORDER_INNER = "#20262E"
BORDER_ACCENT = "#63D3FF"
FG = "#E6EAF0"
FG_DIM = "#8B949E"
FG_INFO = "#B7C0CC"
ACCENT = "#63D3FF"
GREEN = "#4CAF50"
RED = "#FF4444"

RISK_BG = {
    "High": "#A93232",
    "Medium": "#B96A16",
    "Low": "#2F7D57",
    "N/A": "#4A525C",
}

# Chart history rating: API color -> (label, badge color)
HISTORY_MAP = {
    "green":  ("Strong", "#2F7D57"),
    "yellow": ("Mixed",  "#B9A816"),
    "orange": ("Weak",   "#B96A16"),
    "red":    ("Fader",  "#A93232"),
}

# Fonts
FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI Semibold", 10)
FONT_HEADER = ("Segoe UI Semibold", 13)
FONT_TICKER = ("Segoe UI Semibold", 24)
FONT_MONO = ("Consolas", 9)
FONT_MONO_BOLD = ("Consolas", 9, "bold")
FONT_GAINER_TICKER = ("Segoe UI Semibold", 12)
FONT_GAINER_PCT = ("Consolas", 11, "bold")
FONT_GAINER_DETAIL = ("Consolas", 8)

LEFT_PANEL_WIDTH = 260


def risk_bg(level: str) -> str:
    return RISK_BG.get(level, "#555555")


def fmt_millions(val) -> str:
    if val is None:
        return "N/A"
    m = val / 1_000_000
    if m >= 1:
        return f"{m:.2f}M"
    return f"{val / 1000:.0f}K"


def fmt_volume(val) -> str:
    """Format volume with K/M suffix."""
    if val is None or val == 0:
        return "0"
    if val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"{val / 1_000:.0f}K"
    return str(int(val))


def fmt_price(val) -> str:
    """Format price with appropriate decimal places."""
    if val is None or val == 0:
        return "$0.00"
    if val >= 1:
        return f"${val:.2f}"
    return f"${val:.4f}"


# ── Window Monitor ──────────────────────────────────────────────────────────
def find_montage_windows() -> dict[int, str]:
    """Return {hwnd: ticker} for all visible DAS montage and chart windows."""
    windows = {}

    def enum_callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        # DAS montage: "TICKER     0 -- 0     Company Name..."
        if re.match(r'^[A-Z]{1,5}\s+\d', title):
            windows[hwnd] = title.split()[0]
        # DAS chart: "TICKER--5 Minute--"
        elif re.match(r'^[A-Z]{1,5}--', title):
            windows[hwnd] = title.split('--')[0]

    win32gui.EnumWindows(enum_callback, None)
    return windows


def find_tos_tickers() -> dict[int, list[str]]:
    """Return {hwnd: [tickers]} for thinkorswim chart windows."""
    windows = {}

    def enum_callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        # "PRSO, MOBX, TURB - Charts - 61612650SCHW Main@thinkorswim [build 1990]"
        if "thinkorswim" in title and " - Charts - " in title:
            ticker_part = title.split(" - Charts - ")[0]
            tickers = [t.strip() for t in ticker_part.split(",") if t.strip()]
            if tickers:
                windows[hwnd] = tickers

    win32gui.EnumWindows(enum_callback, None)
    return windows


# ── Market Data APIs ────────────────────────────────────────────────────────
def fetch_top_gainers() -> list[dict]:
    """Fetch top gainers, filter by ticker pattern (2-4 caps) and CS type."""
    try:
        resp = requests.get(
            POLYGON_GAINERS_URL,
            params={"apiKey": POLYGON_API_KEY},
            timeout=15,
        )
        data = resp.json()
        tickers_data = data.get("tickers", [])
    except Exception as e:
        print(f"Gainers API error: {e}")
        return []

    # Filter by ticker pattern (2-4 uppercase letters, no periods/special chars)
    filtered = [t for t in tickers_data if TICKER_RE.match(t.get("ticker", ""))]

    # Check type == CS and fetch float data in parallel
    def check_cs_and_float(item):
        ticker = item["ticker"]
        try:
            resp = requests.get(
                f"{POLYGON_TICKER_URL}/{ticker}",
                params={"apiKey": POLYGON_API_KEY},
                timeout=10,
            )
            data = resp.json()
            if data.get("results", {}).get("type") != "CS":
                return None
        except Exception:
            return None
        # Fetch float/sector/country and dilution risk from Ask Edgar
        fdata = fetch_float_data(ticker)
        if fdata:
            item["_float"] = fdata.get("float")
            item["_mcap"] = fdata.get("market_cap_final")
            item["_sector"] = fdata.get("sector", "")
            item["_country"] = fdata.get("country", "")
        ddata = fetch_dilution_data(ticker)
        if ddata:
            item["_risk"] = ddata.get("overall_offering_risk", "")
        # Fetch chart analysis (gap history rating)
        try:
            cresp = requests.get(
                CHART_ANALYSIS_URL,
                headers={"API-KEY": CHART_ANALYSIS_KEY, "Content-Type": "application/json"},
                params={"ticker": ticker, "limit": 1},
                timeout=10,
            )
            cdata = cresp.json()
            if cdata.get("status") == "success" and cdata.get("results"):
                item["_history"] = cdata["results"][0].get("rating", "")
        except Exception:
            pass
        # Check for news/filings today (not grok)
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            nresp = requests.get(
                NEWS_API_URL,
                headers={"API-KEY": NEWS_API_KEY, "Content-Type": "application/json"},
                params={"ticker": ticker, "offset": 0, "limit": 10},
                timeout=10,
            )
            ndata = nresp.json()
            if ndata.get("status") == "success":
                for r in ndata.get("results", []):
                    ft = r.get("form_type")
                    if ft in ("news", "8-K", "6-K"):
                        d = (r.get("created_at") or r.get("filed_at", ""))[:10]
                        if d == today:
                            item["_news_today"] = True
                            break
        except Exception:
            pass
        return item

    cs_gainers = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_cs_and_float, item): item for item in filtered[:30]}
        for future in futures:
            result = future.result()
            if result is not None:
                cs_gainers.append(result)

    # Sort by change percentage descending
    cs_gainers.sort(key=lambda x: x.get("todaysChangePerc", 0), reverse=True)
    return cs_gainers


# ── Ask Edgar APIs ──────────────────────────────────────────────────────────
def fetch_dilution_data(ticker: str) -> dict | None:
    try:
        resp = requests.get(
            DILUTION_API_URL,
            headers={"API-KEY": DILUTION_API_KEY, "Content-Type": "application/json"},
            params={"ticker": ticker, "offset": 0, "limit": 10},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") == "success" and data.get("results"):
            return data["results"][0]
    except Exception as e:
        print(f"Dilution API error for {ticker}: {e}")
    return None


def fetch_float_data(ticker: str) -> dict | None:
    try:
        resp = requests.get(
            FLOAT_API_URL,
            headers={"API-KEY": FLOAT_API_KEY, "Content-Type": "application/json"},
            params={"ticker": ticker, "offset": 0, "limit": 100},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") == "success" and data.get("results"):
            return data["results"][0]
    except Exception as e:
        print(f"Float API error for {ticker}: {e}")
    return None


def fetch_news_and_grok(ticker: str) -> tuple[list[dict], str | None, str | None, str | None, list[dict]]:
    """Fetch recent news/8-K/6-K (top 2), latest grok, and all jmt415 notes."""
    headlines = []
    grok_line = None
    grok_date = None
    grok_url = None
    jmt415_notes = []
    try:
        resp = requests.get(
            NEWS_API_URL,
            headers={"API-KEY": NEWS_API_KEY, "Content-Type": "application/json"},
            params={"ticker": ticker, "offset": 0, "limit": 100},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") == "success":
            for r in data.get("results", []):
                ft = r.get("form_type")
                if ft in ("news", "8-K", "6-K") and len(headlines) < 2:
                    headlines.append(r)
                if ft == "grok" and grok_line is None:
                    summary = r.get("summary", "")
                    for line in summary.split("\n"):
                        line = line.strip().lstrip("-").strip()
                        if line:
                            grok_line = line
                            break
                    # created_at includes time, fall back to filed_at
                    grok_date = r.get("created_at") or r.get("filed_at", "")
                    grok_url = r.get("url") or r.get("document_url")
                if ft == "jmt415" and len(jmt415_notes) < 3:
                    jmt415_notes.append(r)
    except Exception as e:
        print(f"News API error for {ticker}: {e}")
    return headlines, grok_line, grok_date, grok_url, jmt415_notes


def fetch_last_price(ticker: str) -> float | None:
    """Fetch last price via Ask Edgar screener endpoint."""
    try:
        resp = requests.get(
            SCREENER_API_URL,
            headers={"API-KEY": SCREENER_API_KEY, "Content-Type": "application/json"},
            params={"ticker": ticker},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") == "success" and data.get("results"):
            return data["results"][0].get("price")
    except Exception as e:
        print(f"Price API error for {ticker}: {e}")
    return None


def fetch_in_play_dilution(ticker: str) -> tuple[list[dict], list[dict], float]:
    """Fetch dilution-data and split into in-play warrants and convertibles.
    Returns (warrants, convertibles, stock_price) filtered by price proximity and registration."""
    price = fetch_last_price(ticker)
    if price is None or price <= 0:
        return [], [], 0.0

    max_price = price * 4

    try:
        resp = requests.get(
            DILDATA_API_URL,
            headers={"API-KEY": DILDATA_API_KEY, "Content-Type": "application/json"},
            params={"ticker": ticker, "offset": 0, "limit": 40},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") != "success":
            return [], [], price
    except Exception as e:
        print(f"Dilution-data API error for {ticker}: {e}")
        return [], [], price

    warrants = []
    convertibles = []
    from datetime import datetime, timedelta
    six_months_ago = datetime.now() - timedelta(days=180)

    for item in data.get("results", []):
        registered = item.get("registered") or ""
        details_lower = (item.get("details") or "").lower()
        is_warrant = "warrant" in details_lower or "option" in details_lower

        # Skip "Not Registered" items, but override for convertibles filed >6 months ago
        skip_not_registered = "Not Registered" in registered
        if skip_not_registered and not is_warrant:
            filed_at_str = (item.get("filed_at") or "")[:10]
            if filed_at_str:
                try:
                    if datetime.strptime(filed_at_str, "%Y-%m-%d") < six_months_ago:
                        skip_not_registered = False
                except ValueError:
                    pass
        if skip_not_registered:
            continue

        if is_warrant and item.get("warrants_exercise_price"):
            if item["warrants_exercise_price"] <= max_price:
                remaining = item.get("warrants_remaining", 0) or 0
                if remaining > 0:
                    warrants.append(item)
        elif not is_warrant and item.get("conversion_price"):
            if item["conversion_price"] <= max_price:
                remaining = item.get("underlying_shares_remaining", 0) or 0
                if remaining > 0:
                    convertibles.append(item)

    return warrants, convertibles, price


def fetch_gap_stats(ticker: str) -> list[dict]:
    """Fetch gap-up stats for a ticker. Returns list of gap entries (date descending)."""
    try:
        resp = requests.get(
            GAP_STATS_URL,
            headers={"API-KEY": GAP_STATS_KEY, "Content-Type": "application/json"},
            params={"ticker": ticker, "page": 1, "limit": 100},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") == "success":
            return data.get("results", [])
    except Exception as e:
        print(f"Gap stats API error for {ticker}: {e}")
    return []


def fetch_offerings(ticker: str) -> list[dict]:
    """Fetch recent offerings for the ticker (up to 5)."""
    try:
        resp = requests.get(
            OFFERINGS_API_URL,
            headers={"API-KEY": OFFERINGS_API_KEY, "Content-Type": "application/json"},
            params={"ticker": ticker, "limit": 5},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") == "success":
            return data.get("results", [])
    except Exception as e:
        print(f"Offerings API error for {ticker}: {e}")
    return []


def extract_headline(item: dict) -> str:
    if item.get("title"):
        return item["title"]
    summary = item.get("summary", "")
    if summary.startswith("HEADLINE:"):
        return summary.split("HEADLINE:")[1].split("\n")[0].strip()
    return f"{item.get('form_type', '')} Filing"


# ── Overlay UI ──────────────────────────────────────────────────────────────
class DilutionOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Ask Edgar - Dilution Monitor")
        self.root.attributes("-topmost", True)
        self.root.attributes("-toolwindow", False)
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.geometry("780x700+50+50")
        self.root.minsize(650, 400)

        self._drag_data = {"x": 0, "y": 0}
        self.current_ticker = None
        self._known_windows: dict[int, str] = {}   # DAS: hwnd -> ticker
        self._known_tos: dict[int, list[str]] = {}  # ToS: hwnd -> [tickers]
        self._gainers_data: list[dict] = []
        self._selected_gainer: str | None = None
        self._build_ui()
        self._start_monitor()
        self._schedule_gainers_refresh()

    def _build_ui(self):
        # ── Search bar (top, full width) ──
        search_frame = tk.Frame(self.root, bg=BG_CARD,
                                highlightbackground=BORDER, highlightthickness=1)
        search_frame.pack(fill="x", padx=8, pady=(8, 0))

        search_inner = tk.Frame(search_frame, bg=BG_CARD, padx=10, pady=8)
        search_inner.pack(fill="x")
        search_inner.bind("<Button-1>", self._start_drag)
        search_inner.bind("<B1-Motion>", self._on_drag)

        tk.Label(search_inner, text="TICKER:", fg=FG_DIM, bg=BG_CARD,
                 font=FONT_UI_BOLD).pack(side="left", padx=(0, 6))

        self.search_entry = tk.Entry(
            search_inner, bg=BG_ROW, fg=FG, insertbackground=FG,
            font=FONT_UI_BOLD, width=10, relief="flat",
            highlightbackground=BORDER, highlightthickness=1,
        )
        self.search_entry.pack(side="left", padx=(0, 6), ipady=3)
        self.search_entry.bind("<Return>", self._on_search)

        go_btn = tk.Label(
            search_inner, text="  GO  ", fg=BG, bg=ACCENT,
            font=FONT_UI_BOLD, padx=8, pady=2, cursor="hand2",
        )
        go_btn.pack(side="left")
        go_btn.bind("<Button-1>", self._on_search)

        title_lbl = tk.Label(search_inner, text="Ask Edgar Dilution Monitor",
                             fg=FG_DIM, bg=BG_CARD, font=FONT_UI)
        title_lbl.pack(side="right")
        title_lbl.bind("<Button-1>", self._start_drag)
        title_lbl.bind("<B1-Motion>", self._on_drag)

        # ── Main body (left + right) ──
        main_body = tk.Frame(self.root, bg=BG)
        main_body.pack(fill="both", expand=True)

        # ── Left panel (gainers) ──
        left_panel = tk.Frame(main_body, bg=BG, width=LEFT_PANEL_WIDTH)
        left_panel.pack(side="left", fill="y", padx=(8, 0), pady=(6, 8))
        left_panel.pack_propagate(False)

        # Gainers header
        gh_frame = tk.Frame(left_panel, bg=BG_CARD,
                            highlightbackground=BORDER, highlightthickness=1)
        gh_frame.pack(fill="x")

        gh_inner = tk.Frame(gh_frame, bg=BG_CARD, padx=10, pady=8)
        gh_inner.pack(fill="x")

        tk.Label(gh_inner, text="TOP GAINERS", fg=ACCENT, bg=BG_CARD,
                 font=FONT_HEADER).pack(side="left")

        self._gainers_status = tk.Label(gh_inner, text="", fg=FG_DIM, bg=BG_CARD,
                                        font=FONT_MONO)
        self._gainers_status.pack(side="right")

        refresh_btn = tk.Label(gh_inner, text=" \u21bb ", fg=ACCENT, bg=BG_CARD,
                               font=("Segoe UI", 14), cursor="hand2")
        refresh_btn.pack(side="right", padx=(0, 4))
        refresh_btn.bind("<Button-1>", lambda e: self._trigger_gainers_refresh())

        # Gainers scrollable list
        gainers_container = tk.Frame(left_panel, bg=BG)
        gainers_container.pack(fill="both", expand=True, pady=(2, 0))

        self._gainers_canvas = tk.Canvas(gainers_container, bg=BG,
                                         highlightthickness=0,
                                         width=LEFT_PANEL_WIDTH - 16)
        gainers_sb = tk.Scrollbar(gainers_container, orient="vertical",
                                  command=self._gainers_canvas.yview)
        self._gainers_frame = tk.Frame(self._gainers_canvas, bg=BG)

        self._gainers_frame.bind(
            "<Configure>",
            lambda e: self._gainers_canvas.configure(
                scrollregion=self._gainers_canvas.bbox("all")
            ),
        )
        self._gainers_canvas_window = self._gainers_canvas.create_window(
            (0, 0), window=self._gainers_frame, anchor="nw"
        )
        self._gainers_canvas.configure(yscrollcommand=gainers_sb.set)

        def _on_gainers_canvas_resize(event):
            self._gainers_canvas.itemconfig(self._gainers_canvas_window,
                                            width=event.width)
        self._gainers_canvas.bind("<Configure>", _on_gainers_canvas_resize)

        self._gainers_canvas.pack(side="left", fill="both", expand=True)
        gainers_sb.pack(side="right", fill="y")

        # ── Right panel (Ask Edgar content) ──
        right_panel = tk.Frame(main_body, bg=BG)
        right_panel.pack(side="left", fill="both", expand=True,
                         padx=(4, 8), pady=(6, 8))

        # Header card (draggable)
        header_card = tk.Frame(right_panel, bg=BG_CARD,
                               highlightbackground=BORDER, highlightthickness=1)
        header_card.pack(fill="x")
        header_card.bind("<Button-1>", self._start_drag)
        header_card.bind("<B1-Motion>", self._on_drag)

        header_inner = tk.Frame(header_card, bg=BG_CARD, padx=14, pady=12)
        header_inner.pack(fill="x")
        header_inner.bind("<Button-1>", self._start_drag)
        header_inner.bind("<B1-Motion>", self._on_drag)

        self.ticker_label = tk.Label(
            header_inner, text="Waiting...", fg=ACCENT,
            bg=BG_CARD, font=FONT_TICKER,
        )
        self.ticker_label.pack(side="left")

        self.overall_badge = tk.Label(
            header_inner, text="", fg="white", bg="#4A525C",
            font=FONT_UI_BOLD, padx=12, pady=6,
        )
        self.overall_badge.pack(side="right")

        self.history_badge = tk.Label(
            header_inner, text="", fg="white", bg="#4A525C",
            font=FONT_UI_BOLD, padx=12, pady=6,
        )
        self.history_badge.pack(side="right", padx=(0, 6))
        self.history_badge.pack_forget()  # hidden until data loaded

        self.info_label = tk.Label(
            header_card, text="", fg=FG_INFO, bg=BG_CARD,
            font=FONT_UI, anchor="w",
        )
        self.info_label.pack(fill="x", padx=14, pady=(0, 10))

        # Scrollable content area
        container = tk.Frame(right_panel, bg=BG)
        container.pack(fill="both", expand=True, pady=(4, 0))

        canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.content_frame = tk.Frame(canvas, bg=BG)

        self.content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        self._canvas_window = canvas.create_window(
            (0, 0), window=self.content_frame, anchor="nw"
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_canvas_resize(event):
            canvas.itemconfig(self._canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_resize)

        # Mouse wheel scrolling — route to correct panel based on cursor position
        def _on_mousewheel(event):
            x = event.x_root - self.root.winfo_rootx()
            if x < LEFT_PANEL_WIDTH + 12:
                self._gainers_canvas.yview_scroll(
                    int(-1 * (event.delta / 120)), "units"
                )
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas = canvas

        self._show_waiting()

    # ── Display states ──────────────────────────────────────────────────────
    def _clear(self):
        for w in self.content_frame.winfo_children():
            w.destroy()

    def _show_waiting(self):
        self._clear()
        tk.Label(
            self.content_frame,
            text="Load a ticker in DAS or thinkorswim,\n"
                 "click a top gainer, or search above.",
            fg="#4A525C", bg=BG, font=("Segoe UI", 12), justify="center",
        ).pack(pady=60)

    def _update_history_badge(self, rating: str, post_url: str = ""):
        """Update the history badge in the header."""
        if rating in HISTORY_MAP:
            label, color = HISTORY_MAP[rating]
            self.history_badge.config(text=f"HISTORY: {label}", bg=color)
            self.history_badge.pack(side="right", padx=(0, 6))
            if post_url:
                self.history_badge.config(cursor="hand2")
                self.history_badge.bind("<Button-1>", lambda e, u=post_url: webbrowser.open(u))
            else:
                self.history_badge.config(cursor="")
                self.history_badge.unbind("<Button-1>")
        else:
            self.history_badge.pack_forget()

    def _show_loading(self, ticker: str):
        self._clear()
        self.ticker_label.config(text=ticker)
        self.overall_badge.config(text="...", bg="#4A525C")
        self.history_badge.pack_forget()
        self.info_label.config(text="Loading...")
        tk.Label(
            self.content_frame,
            text=f"Fetching data for {ticker}...",
            fg=ACCENT, bg=BG, font=("Segoe UI", 12),
        ).pack(pady=60)
        self.root.update_idletasks()

    def _show_no_data(self, ticker: str):
        self._clear()
        self.overall_badge.config(text="NO DATA", bg="#4A525C")
        self.info_label.config(text="")
        tk.Label(
            self.content_frame,
            text=f"No dilution data available for {ticker}.",
            fg="#FF6666", bg=BG, font=("Segoe UI", 11), justify="center",
        ).pack(pady=60)

    def _make_card(self, parent, title: str = None) -> tk.Frame:
        """Create a bordered card frame, optionally with a section header."""
        card = tk.Frame(parent, bg=BG_CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", padx=8, pady=(6, 0))
        if title:
            hdr = tk.Label(card, text=title, fg=ACCENT, bg=BG_CARD,
                           font=FONT_HEADER, anchor="w", padx=14, pady=10)
            hdr.pack(fill="x")
            tk.Frame(card, bg=BORDER, height=1).pack(fill="x")
        return card

    def _show_data(self, ticker: str, dilution: dict, floatdata: dict | None,
                   news: list[dict] | None = None, grok_line: str | None = None,
                   grok_date: str | None = None, grok_url: str | None = None,
                   in_play_warrants: list[dict] | None = None,
                   in_play_converts: list[dict] | None = None,
                   stock_price: float = 0.0,
                   jmt415_notes: list[dict] | None = None,
                   gap_stats: list[dict] | None = None,
                   offerings: list[dict] | None = None):
        self._clear()

        risk = dilution.get("overall_offering_risk", "N/A")
        self.overall_badge.config(text=f"RISK: {risk}", bg=risk_bg(risk))

        # ── Info line from float data ──
        if floatdata:
            flt = fmt_millions(floatdata.get("float"))
            outs = fmt_millions(floatdata.get("outstanding"))
            mc = fmt_millions(floatdata.get("market_cap_final"))
            sector = floatdata.get("sector", "")
            country = floatdata.get("country", "")
            self.info_label.config(
                text=f"Float/OS: {flt}/{outs}  |  MC: {mc}  |  {sector}  |  {country}"
            )
        else:
            self.info_label.config(text="")

        # ── Feed card (news + grok) ──
        has_feed = news or grok_line
        if has_feed:
            feed_card = self._make_card(self.content_frame)
            feed_inner = tk.Frame(feed_card, bg=BG_CARD, padx=8, pady=8)
            feed_inner.pack(fill="x")

            if news:
                for item in news:
                    headline = extract_headline(item)
                    url = item.get("url") or item.get("document_url")
                    form = item.get("form_type", "")
                    raw_date = item.get("created_at") or item.get("filed_at", "")
                    date = raw_date[:16].replace("T", " ")
                    self._add_feed_item(feed_inner, form, headline, url, date)

            if grok_line:
                grok_date_str = ""
                if grok_date:
                    grok_date_str = grok_date[:16].replace("T", " ")
                self._add_feed_item(feed_inner, "grok", grok_line, grok_url, grok_date_str)

        # ── Risk badges card (grid: 3 columns, wraps to 2 rows) ──
        dilution_url = f"https://app.askedgar.io/ticker/{ticker}/dilution"
        badges_card = self._make_card(self.content_frame)
        badges_inner = tk.Frame(badges_card, bg=BG_CARD, padx=8, pady=8, cursor="hand2")
        badges_inner.pack(fill="x")
        badges_inner.bind("<Button-1>", lambda e, u=dilution_url: webbrowser.open(u))

        badge_items = [
            ("Overall Risk", risk),
            ("Offering", dilution.get("offering_ability", "N/A")),
            ("Dilution", dilution.get("dilution", "N/A")),
            ("Frequency", dilution.get("offering_frequency", "N/A")),
            ("Cash Need", dilution.get("cash_need", "N/A")),
            ("Warrants", dilution.get("warrant_exercise", "N/A")),
        ]
        for i, (label, level) in enumerate(badge_items):
            self._add_badge_grid(badges_inner, label, level, dilution_url,
                                 row=i // 3, col=i % 3)
        badges_inner.columnconfigure((0, 1, 2), weight=1)

        # ── Offering Ability card ──
        offering_desc = dilution.get("offering_ability_desc")
        if offering_desc:
            self._add_offering_ability_card(offering_desc, url=dilution_url)

        # ── In Play Dilution card ──
        if in_play_warrants or in_play_converts:
            self._add_in_play_section(in_play_warrants or [], in_play_converts or [], stock_price, dilution_url)

        # ── Recent Offerings card ──
        if offerings:
            self._add_offerings_card(offerings[:3], stock_price, url=dilution_url)

        # ── Gap Stats card ──
        if gap_stats:
            self._add_gap_stats_card(gap_stats)

        # ── JMT415 Previous Notes card ──
        if jmt415_notes:
            self._add_jmt415_card(jmt415_notes)

        # ── Management Commentary card ──
        commentary = dilution.get("mgmt_commentary")
        if commentary:
            self._add_section_card("Mgmt Commentary", commentary, url=dilution_url)

    def _add_badge_grid(self, parent, label: str, level: str,
                        url: str | None = None, row: int = 0, col: int = 0):
        """Place a badge in a grid layout (3 columns, rows wrap automatically)."""
        frame = tk.Frame(parent, bg=BG_CARD, padx=4, pady=4, cursor="hand2")
        frame.grid(row=row, column=col, padx=4, pady=2, sticky="ew")

        lbl = tk.Label(
            frame, text=label, fg=FG_DIM, bg=BG_CARD,
            font=FONT_MONO, cursor="hand2",
        )
        lbl.pack()

        badge = tk.Label(
            frame, text=f" {level} ", fg="white", bg=risk_bg(level),
            font=FONT_UI_BOLD, padx=8, pady=3, cursor="hand2",
        )
        badge.pack()

        if url:
            for w in (frame, lbl, badge):
                w.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

    def _add_feed_item(self, parent, form_type: str, headline: str,
                       url: str | None, date: str = ""):
        """Feed row with source stripe on the left. Entire row is clickable."""
        SOURCE_COLORS = {
            "news": "#1F8FB3",
            "8-K": "#A85C14",
            "6-K": "#A85C14",
            "grok": "#7B3FA0",
        }
        source_color = SOURCE_COLORS.get(form_type, "#555555")
        tag = form_type.upper() if form_type != "news" else "NEWS"

        # Truncate grok output to ~240 chars
        if form_type == "grok" and len(headline) > 240:
            headline = headline[:237] + "..."

        row = tk.Frame(parent, bg=BG_ROW,
                       highlightbackground=BORDER_INNER, highlightthickness=1)
        row.pack(fill="x", pady=2)

        # Source stripe (left column)
        stripe = tk.Label(
            row, text=tag, fg="white", bg=source_color,
            font=("Consolas", 8, "bold"), width=5, padx=4, pady=8,
        )
        stripe.pack(side="left", fill="y")

        # Content area — stacked vertically so text wraps downward
        content = tk.Frame(row, bg=BG_ROW, padx=10, pady=6)
        content.pack(side="left", fill="both", expand=True)

        if date:
            tk.Label(
                content, text=date, fg=FG_DIM, bg=BG_ROW,
                font=FONT_MONO, anchor="w",
            ).pack(fill="x")

        hl_label = tk.Label(
            content, text=headline, fg="white", bg=BG_ROW,
            font=FONT_UI_BOLD, anchor="w", wraplength=200,
            justify="left",
        )
        hl_label.pack(fill="x")

        def _rewrap_hl(event, lbl=hl_label):
            lbl.config(wraplength=max(event.width - 30, 100))
        content.bind("<Configure>", _rewrap_hl)

        # Make entire row clickable if there's a URL
        if url:
            row.config(cursor="hand2")
            def _bind_click(widget, target_url):
                widget.bind("<Button-1>", lambda e, u=target_url: webbrowser.open(u))
                widget.config(cursor="hand2")
            for w in (row, stripe, content, hl_label):
                _bind_click(w, url)
            for child in content.winfo_children():
                _bind_click(child, url)

    def _bind_card_click(self, card, url: str):
        """Make an entire card and all its descendants clickable."""
        def _bind(w, u=url):
            w.bind("<Button-1>", lambda e, u=u: webbrowser.open(u))
            w.config(cursor="hand2")
        def _bind_all(widget):
            _bind(widget)
            for child in widget.winfo_children():
                _bind_all(child)
        _bind_all(card)

    def _add_section_card(self, title: str, text: str, url: str = ""):
        """Section card with header + bottom border + wrapped text content."""
        card = self._make_card(self.content_frame, title=title)
        body = tk.Frame(card, bg=BG_CARD, padx=14, pady=14)
        body.pack(fill="x")
        text_label = tk.Label(
            body, text=text, fg=FG, bg=BG_CARD,
            font=FONT_UI, justify="left", anchor="w",
        )
        text_label.pack(fill="x")
        def _rewrap(event, lbl=text_label):
            lbl.config(wraplength=max(event.width - 4, 100))
        body.bind("<Configure>", _rewrap)
        if url:
            self._bind_card_click(card, url)

    def _add_offering_ability_card(self, desc: str, url: str = ""):
        """Offering Ability card with color-coded capacity values."""
        card = self._make_card(self.content_frame, title="Offering Ability")
        body = tk.Frame(card, bg=BG_CARD, padx=14, pady=14)
        body.pack(fill="x")

        # Parse and color individual segments — stacked vertically
        parts = [p.strip() for p in desc.split(",")]

        for part in parts:
            part_lower = part.lower()
            if "pending s-1" in part_lower or "pending f-1" in part_lower:
                color = "#4CAF50"
                bold = True
            elif ("shelf capacity" in part_lower or "atm capacity" in part_lower
                  or "equity line capacity" in part_lower):
                if "$0.00" in part:
                    color = "#FF4444"
                    bold = False
                else:
                    color = "#4CAF50"
                    bold = True
            else:
                color = FG
                bold = False

            font = ("Segoe UI Semibold", 10) if bold else FONT_UI
            tk.Label(
                body, text=part, fg=color, bg=BG_CARD,
                font=font, anchor="w",
            ).pack(fill="x")

        if url:
            self._bind_card_click(card, url)

    def _add_gap_stats_card(self, gaps: list[dict]):
        """Gap Stats summary card."""
        from datetime import datetime
        card = self._make_card(self.content_frame, title="Gap Stats")
        body = tk.Frame(card, bg=BG_CARD, padx=14, pady=10)
        body.pack(fill="x")

        n = len(gaps)
        last_date = gaps[0].get("date", "N/A") if gaps else "N/A"

        # Compute averages
        gap_pcts = [g["gap_percentage"] for g in gaps if g.get("gap_percentage") is not None]
        avg_gap = sum(gap_pcts) / len(gap_pcts) if gap_pcts else 0

        oh_spikes = []
        ol_drops = []
        for g in gaps:
            o = g.get("market_open")
            h = g.get("high_price")
            lo = g.get("low_price")
            if o and o > 0:
                if h is not None:
                    oh_spikes.append((h - o) / o * 100)
                if lo is not None:
                    ol_drops.append((lo - o) / o * 100)

        avg_oh = sum(oh_spikes) / len(oh_spikes) if oh_spikes else 0
        avg_ol = sum(ol_drops) / len(ol_drops) if ol_drops else 0

        # % new high after 11am EST (high_time is already EST, e.g. "2026-03-27T12:34:00")
        high_after_11 = 0
        for g in gaps:
            ht = g.get("high_time", "")
            if ht:
                try:
                    t = datetime.fromisoformat(ht)
                    if t.hour >= 11:
                        high_after_11 += 1
                except Exception:
                    pass
        pct_high_after_11 = (high_after_11 / n * 100) if n else 0

        # % closed below VWAP (API gives closed_over_vwap boolean)
        below_vwap = sum(1 for g in gaps if g.get("closed_over_vwap") is False)
        pct_below_vwap = (below_vwap / n * 100) if n else 0

        # % closed below open
        below_open = sum(1 for g in gaps if g.get("market_close") and g.get("market_open")
                         and g["market_close"] < g["market_open"])
        pct_below_open = (below_open / n * 100) if n else 0

        # Display stats as label-value rows
        stats = [
            ("Last Gap Date", last_date),
            ("Number of Gaps", str(n)),
            ("Avg Gap %", f"{avg_gap:.1f}%"),
            ("Avg Open→High", f"+{avg_oh:.1f}%"),
            ("Avg Open→Low", f"{avg_ol:.1f}%"),
            ("New High After 11am", f"{pct_high_after_11:.0f}%"),
            ("Closed Below VWAP", f"{pct_below_vwap:.0f}%"),
            ("Closed Below Open", f"{pct_below_open:.0f}%"),
        ]

        for label, value in stats:
            row = tk.Frame(body, bg=BG_CARD)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, fg=FG_DIM, bg=BG_CARD,
                     font=FONT_MONO, width=22, anchor="w").pack(side="left")
            # Color code certain values
            ORANGE = "#B96A16"
            val_color = FG
            if "Below VWAP" in label:
                try:
                    pv = float(value.rstrip("%"))
                    val_color = GREEN if pv <= 59 else (ORANGE if pv <= 84 else RED)
                except ValueError:
                    pass
            elif "Below Open" in label:
                try:
                    pv = float(value.rstrip("%"))
                    val_color = GREEN if pv <= 50 else (ORANGE if pv <= 74 else RED)
                except ValueError:
                    pass
            elif "After 11am" in label:
                try:
                    pv = float(value.rstrip("%"))
                    val_color = GREEN if pv >= 45 else (ORANGE if pv >= 21 else RED)
                except ValueError:
                    pass
            elif "Open→High" in label:
                val_color = GREEN
            elif "Open→Low" in label:
                val_color = RED
            tk.Label(row, text=value, fg=val_color, bg=BG_CARD,
                     font=FONT_MONO_BOLD, anchor="w").pack(side="left")


    def _add_offerings_card(self, offerings: list[dict], stock_price: float = 0.0,
                            url: str = ""):
        """Recent Offerings card with headline + data row per offering."""
        card = self._make_card(self.content_frame, title="Recent Offerings")
        body = tk.Frame(card, bg=BG_CARD, padx=14, pady=10)
        body.pack(fill="x")

        for i, o in enumerate(offerings):
            row_bg = BG_ROW if i % 2 == 0 else BG_ROW_ALT

            row = tk.Frame(body, bg=row_bg,
                           highlightbackground=BORDER_INNER, highlightthickness=1)
            row.pack(fill="x", pady=2)

            inner = tk.Frame(row, bg=row_bg, padx=10, pady=6)
            inner.pack(fill="x")

            headline = (o.get("headline") or "Offering").strip()
            tk.Label(inner, text=headline, fg="white", bg=row_bg,
                     font=FONT_UI, anchor="w").pack(fill="x")

            is_atm = "ATM USED" in headline.upper()

            data_row = tk.Frame(inner, bg=row_bg)
            data_row.pack(fill="x", pady=(2, 0))

            if is_atm:
                offering_amt = o.get("offering_amount")
                if offering_amt:
                    tk.Label(data_row, text=f"${fmt_millions(offering_amt)}", fg="#4CAF50", bg=row_bg,
                             font=FONT_MONO_BOLD).pack(side="left")
                filed = (o.get("filed_at") or "")[:10]
                if filed:
                    tk.Label(data_row, text="  |  ", fg=FG_DIM, bg=row_bg,
                             font=FONT_MONO).pack(side="left")
                    tk.Label(data_row, text=filed, fg=FG_DIM, bg=row_bg,
                             font=FONT_MONO).pack(side="left")
            else:
                offer_price = o.get("share_price") or 0
                in_money = stock_price > 0 and offer_price > 0 and offer_price <= stock_price
                highlight = "#4CAF50" if in_money else "#FF9800"

                shares = o.get("shares_amount")
                warrants = o.get("warrants_amount")
                filed = (o.get("filed_at") or "")[:10]

                parts_colored = []
                if shares:
                    parts_colored.append(f"Amt:{fmt_millions(shares)}")
                if offer_price:
                    parts_colored.append(f"${offer_price:.2f}")
                if warrants:
                    parts_colored.append(f"Wrrnts:{fmt_millions(warrants)}")

                for j, part in enumerate(parts_colored):
                    if j > 0:
                        tk.Label(data_row, text=" | ", fg=FG_DIM, bg=row_bg,
                                 font=FONT_MONO).pack(side="left")
                    tk.Label(data_row, text=part, fg=highlight, bg=row_bg,
                             font=FONT_MONO_BOLD).pack(side="left")

                if filed:
                    if parts_colored:
                        tk.Label(data_row, text="  |  ", fg=FG_DIM, bg=row_bg,
                                 font=FONT_MONO).pack(side="left")
                    tk.Label(data_row, text=filed, fg=FG_DIM, bg=row_bg,
                             font=FONT_MONO).pack(side="left")

        if url:
            self._bind_card_click(card, url)

    def _add_jmt415_card(self, notes: list[dict]):
        """JMT415 Previous Notes card with bordered panels per note."""
        card = self._make_card(self.content_frame, title="JMT415 Previous Notes")
        body = tk.Frame(card, bg=BG_CARD, padx=10, pady=10)
        body.pack(fill="x")

        for i, note in enumerate(notes):
            date = (note.get("filed_at") or "")[:10]
            text = (note.get("summary") or note.get("title") or "Note").strip()
            row_bg = BG_ROW if i % 2 == 0 else BG_ROW_ALT

            row = tk.Frame(body, bg=row_bg,
                           highlightbackground=BORDER_INNER, highlightthickness=1)
            row.pack(fill="x", pady=2)

            inner = tk.Frame(row, bg=row_bg, padx=10, pady=8)
            inner.pack(fill="x")

            tk.Label(inner, text=date, fg=FG_DIM, bg=row_bg,
                     font=FONT_MONO).pack(anchor="w")
            note_label = tk.Label(inner, text=text, fg=FG, bg=row_bg,
                                  font=FONT_UI, anchor="w",
                                  wraplength=350, justify="left")
            note_label.pack(fill="x", pady=(2, 0))

            def _rewrap(event, lbl=note_label):
                lbl.config(wraplength=max(event.width - 40, 100))
            row.bind("<Configure>", _rewrap)

    def _add_in_play_section(self, warrants: list[dict], convertibles: list[dict],
                             stock_price: float = 0.0, dilution_url: str = ""):
        card = self._make_card(self.content_frame, title="In Play Dilution")
        body = tk.Frame(card, bg=BG_CARD, padx=14, pady=10)
        body.pack(fill="x")

        if warrants:
            tk.Label(
                body, text="WARRANTS", fg="#FFD600", bg=BG_CARD,
                font=FONT_UI_BOLD, anchor="w",
            ).pack(fill="x", pady=(4, 4))
            for w in warrants:
                ex_price = w.get("warrants_exercise_price", 0) or 0
                in_money = stock_price > 0 and ex_price <= stock_price
                self._add_dilution_row(
                    body, w.get("details", ""),
                    f"Remaining: {fmt_millions(w.get('warrants_remaining'))}",
                    f"Strike: ${ex_price:.2f}",
                    (w.get("filed_at") or "")[:10],
                    in_money,
                )

        if convertibles:
            tk.Label(
                body, text="CONVERTIBLES", fg="#FFD600", bg=BG_CARD,
                font=FONT_UI_BOLD, anchor="w",
            ).pack(fill="x", pady=(8, 4))
            for c in convertibles:
                conv_price = c.get("conversion_price", 0) or 0
                in_money = stock_price > 0 and conv_price <= stock_price
                self._add_dilution_row(
                    body, c.get("details", ""),
                    f"Shares: {fmt_millions(c.get('underlying_shares_remaining'))}",
                    f"Conv: ${conv_price:.2f}",
                    (c.get("filed_at") or "")[:10],
                    in_money,
                )

        if dilution_url:
            self._bind_card_click(card, dilution_url)

    def _add_dilution_row(self, parent, details, remaining, price, filed,
                          price_above=False):
        # Green if strike/conv price <= stock price (in the money), orange otherwise
        highlight = "#4CAF50" if price_above else "#FF9800"

        row = tk.Frame(parent, bg=BG_ROW,
                       highlightbackground=BORDER_INNER, highlightthickness=1)
        row.pack(fill="x", pady=2)

        inner = tk.Frame(row, bg=BG_ROW, padx=10, pady=6)
        inner.pack(fill="x")

        # Line 1: details (truncated if long)
        detail_text = details if len(details) <= 60 else details[:57] + "..."
        tk.Label(inner, text=detail_text, fg="white", bg=BG_ROW,
                 font=FONT_UI, anchor="w").pack(fill="x")

        # Line 2: remaining | price | filed
        data_row = tk.Frame(inner, bg=BG_ROW)
        data_row.pack(fill="x", pady=(2, 0))
        tk.Label(data_row, text=remaining, fg=highlight, bg=BG_ROW,
                 font=FONT_MONO_BOLD).pack(side="left")
        tk.Label(data_row, text="  |  ", fg=FG_DIM, bg=BG_ROW,
                 font=FONT_MONO).pack(side="left")
        tk.Label(data_row, text=price, fg=highlight, bg=BG_ROW,
                 font=FONT_MONO_BOLD).pack(side="left")
        tk.Label(data_row, text=f"  |  Filed: {filed}", fg=FG_DIM, bg=BG_ROW,
                 font=FONT_MONO).pack(side="left")

    # ── Gainers panel ───────────────────────────────────────────────────────
    def _schedule_gainers_refresh(self):
        """Kick off the first gainers fetch."""
        self._trigger_gainers_refresh()

    def _trigger_gainers_refresh(self):
        """Fetch gainers in background thread."""
        self._gainers_status.config(text="loading...")

        def _fetch():
            gainers = fetch_top_gainers()
            self.root.after(0, self._update_gainers_ui, gainers)

        threading.Thread(target=_fetch, daemon=True).start()

    def _update_gainers_ui(self, gainers: list[dict]):
        """Rebuild the gainers list with fresh data."""
        self._gainers_data = gainers
        self._gainers_status.config(text=str(len(gainers)))

        # Clear existing rows
        for w in self._gainers_frame.winfo_children():
            w.destroy()

        if not gainers:
            tk.Label(self._gainers_frame, text="No gainers found",
                     fg=FG_DIM, bg=BG, font=FONT_UI).pack(pady=20)
        else:
            for item in gainers:
                self._build_gainer_row(item)

        # Schedule next refresh
        self.root.after(GAINERS_REFRESH_SECS * 1000, self._trigger_gainers_refresh)

    def _build_gainer_row(self, item: dict):
        """Build a single clickable gainer row."""
        ticker = item.get("ticker", "")
        change_pct = item.get("todaysChangePerc", 0)
        price = item.get("day", {}).get("c", 0) or 0
        volume = item.get("day", {}).get("v", 0) or 0

        is_selected = (ticker == self._selected_gainer)
        row_bg = BG_SELECTED if is_selected else BG_CARD
        border_color = BORDER_ACCENT if is_selected else BORDER

        row = tk.Frame(self._gainers_frame, bg=row_bg,
                       highlightbackground=border_color, highlightthickness=1,
                       cursor="hand2")
        row.pack(fill="x", padx=4, pady=2)

        inner = tk.Frame(row, bg=row_bg, padx=10, pady=6)
        inner.pack(fill="x")

        # Top line: ticker + risk badge + change %
        top = tk.Frame(inner, bg=row_bg)
        top.pack(fill="x")

        tk.Label(top, text=ticker, fg=ACCENT, bg=row_bg,
                 font=FONT_GAINER_TICKER, cursor="hand2").pack(side="left")

        risk_level = item.get("_risk", "")
        if risk_level:
            tk.Label(top, text=f" {risk_level} ", fg="white",
                     bg=risk_bg(risk_level), font=("Consolas", 7, "bold"),
                     padx=4, pady=1, cursor="hand2").pack(side="left", padx=(6, 0))
        if item.get("_news_today"):
            tk.Label(top, text=" News ", fg="white", bg="#1F8FB3",
                     font=("Consolas", 7, "bold"), padx=4, pady=1,
                     cursor="hand2").pack(side="left", padx=(4, 0))
        pct_text = f"+{change_pct:.1f}%" if change_pct >= 0 else f"{change_pct:.1f}%"
        pct_color = GREEN if change_pct >= 0 else RED
        tk.Label(top, text=pct_text, fg=pct_color, bg=row_bg,
                 font=FONT_GAINER_PCT, cursor="hand2").pack(side="right")

        # Middle line: price + volume
        mid = tk.Frame(inner, bg=row_bg)
        mid.pack(fill="x")

        tk.Label(mid, text=fmt_price(price), fg=FG, bg=row_bg,
                 font=FONT_GAINER_DETAIL, cursor="hand2").pack(side="left")
        tk.Label(mid, text=f"Vol {fmt_volume(volume)}", fg=FG_DIM, bg=row_bg,
                 font=FONT_GAINER_DETAIL, cursor="hand2").pack(side="right")

        # Bottom line: float / mcap / sector / country (condensed)
        flt = item.get("_float")
        mcap = item.get("_mcap")
        sector = item.get("_sector", "")
        country = item.get("_country", "")
        # Shorten long sector names
        sector_short = {
            "Healthcare": "Health", "Technology": "Tech",
            "Industrials": "Indust", "Consumer Cyclical": "Cons Cyc",
            "Consumer Defensive": "Cons Def", "Communication Services": "Comms",
            "Financial Services": "Financ", "Basic Materials": "Materials",
            "Real Estate": "RE",
        }.get(sector, sector)
        info_parts = []
        if flt:
            info_parts.append(fmt_millions(flt))
        if mcap:
            info_parts.append(fmt_millions(mcap))
        if sector_short:
            info_parts.append(sector_short)
        if country:
            info_parts.append(country)
        if info_parts:
            bot = tk.Frame(inner, bg=row_bg)
            bot.pack(fill="x")
            tk.Label(bot, text=" | ".join(info_parts), fg=FG_DIM, bg=row_bg,
                     font=FONT_GAINER_DETAIL, cursor="hand2").pack(side="left")
        else:
            bot = None

        # Bind click on all child widgets
        def on_click(e, t=ticker):
            self._on_gainer_click(t)

        click_targets = [row, inner, top, mid]
        if bot:
            click_targets.append(bot)
        for widget in click_targets:
            widget.bind("<Button-1>", on_click)
        for widget in (list(top.winfo_children()) + list(mid.winfo_children())
                       + (list(bot.winfo_children()) if bot else [])):
            widget.bind("<Button-1>", on_click)

    def _on_gainer_click(self, ticker: str):
        """Handle click on a gainer — select it and load Ask Edgar data."""
        self._selected_gainer = ticker
        # Rebuild gainers list to update selection highlight
        self._rebuild_gainers_list()
        # Load Ask Edgar data
        self._on_ticker_change(ticker)

    def _rebuild_gainers_list(self):
        """Rebuild gainer rows from cached data (updates selection state)."""
        for w in self._gainers_frame.winfo_children():
            w.destroy()
        for item in self._gainers_data:
            self._build_gainer_row(item)

    def _on_search(self, event=None):
        """Handle search box submit."""
        ticker = self.search_entry.get().strip().upper()
        if ticker:
            self.search_entry.delete(0, "end")
            self._selected_gainer = None
            self._rebuild_gainers_list()
            self._on_ticker_change(ticker)

    # ── Dragging ──
    def _start_drag(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")

    # ── Monitor thread ──
    def _start_monitor(self):
        def poll():
            while True:
                changed_ticker = None

                # ── DAS montage windows ──
                current = find_montage_windows()  # {hwnd: ticker}
                for hwnd, ticker in current.items():
                    old_ticker = self._known_windows.get(hwnd)
                    if old_ticker is not None and ticker != old_ticker:
                        changed_ticker = ticker
                        break
                if changed_ticker is None:
                    new_hwnds = set(current) - set(self._known_windows)
                    for hwnd in new_hwnds:
                        changed_ticker = current[hwnd]
                        break
                self._known_windows = current

                # ── thinkorswim chart windows ──
                if changed_ticker is None:
                    tos_current = find_tos_tickers()  # {hwnd: [tickers]}
                    for hwnd, tickers in tos_current.items():
                        old_tickers = self._known_tos.get(hwnd, [])
                        new_syms = [t for t in tickers if t not in old_tickers]
                        if new_syms:
                            changed_ticker = new_syms[0]
                            break
                    if changed_ticker is None:
                        new_hwnds = set(tos_current) - set(self._known_tos)
                        for hwnd in new_hwnds:
                            changed_ticker = tos_current[hwnd][0]
                            break
                    self._known_tos = tos_current

                if changed_ticker:
                    self.current_ticker = changed_ticker
                    self.root.after(0, self._on_ticker_change, changed_ticker)
                time.sleep(POLL_INTERVAL)

        threading.Thread(target=poll, daemon=True).start()

    def _on_ticker_change(self, ticker: str):
        self.current_ticker = ticker
        self._show_loading(ticker)

        def fetch():
            dilution = fetch_dilution_data(ticker)
            floatdata = fetch_float_data(ticker)
            news, grok_line, grok_date, grok_url, jmt415_notes = fetch_news_and_grok(ticker)
            warrants, converts, stock_price = fetch_in_play_dilution(ticker)
            gap_stats = fetch_gap_stats(ticker)
            recent_offerings = fetch_offerings(ticker)
            # Fetch chart analysis for history badge
            history_rating = ""
            history_url = ""
            try:
                cresp = requests.get(
                    CHART_ANALYSIS_URL,
                    headers={"API-KEY": CHART_ANALYSIS_KEY, "Content-Type": "application/json"},
                    params={"ticker": ticker, "limit": 1},
                    timeout=10,
                )
                cdata = cresp.json()
                if cdata.get("status") == "success" and cdata.get("results"):
                    history_rating = cdata["results"][0].get("rating", "")
                    history_url = cdata["results"][0].get("post_url", "")
            except Exception:
                pass
            self.root.after(0, self._update_history_badge, history_rating, history_url)
            if dilution:
                self.root.after(0, self._show_data, ticker, dilution, floatdata,
                                news, grok_line, grok_date, grok_url, warrants, converts, stock_price,
                                jmt415_notes, gap_stats, recent_offerings)
            else:
                self.root.after(0, self._show_no_data, ticker)

        threading.Thread(target=fetch, daemon=True).start()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = DilutionOverlay()
    app.run()
