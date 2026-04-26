"""
PunkTrader — Configuration

Loads credentials and settings from .env file.
"""

import os
import sys

import pytz
from dotenv import load_dotenv

if getattr(sys, 'frozen', False):
    _BASE = os.path.dirname(sys.executable)
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(_BASE, '.env'))

# Alpaca API
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.environ.get("ALPACA_API_SECRET", "")
BASE_URL = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

# Data feed: "iex" (free, ~15 min delay) or "sip" (paid, real-time)
DATA_FEED = os.environ.get("DATA_FEED", "iex")
WS_URL = f"wss://stream.data.alpaca.markets/v2/{DATA_FEED}"

# Timezone
TIMEZONE = os.environ.get("TIMEZONE", "America/Los_Angeles")

# Default ticker on load
DEFAULT_TICKER = os.environ.get("DEFAULT_TICKER", "SPY")
DEFAULT_TIMEFRAME = os.environ.get("DEFAULT_TIMEFRAME", "5Min")

# Watchlist for key levels
_DEFAULT_WATCHLIST = [
    "SPY", "QQQ", "AAPL", "TSLA", "AMD", "NVDA", "PLTR",
    "MSFT", "AMZN", "META", "GOOG",
]
_wl = os.environ.get("WATCHLIST", "")
WATCHLIST = [s.strip() for s in _wl.split(",") if s.strip()] if _wl else _DEFAULT_WATCHLIST
