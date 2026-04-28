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

# FMP API
FMP_API_KEY  = os.environ.get("FMP_API_KEY", "")
FMP_BASE_URL = "https://financialmodelingprep.com/stable"

# Timezone
TIMEZONE = os.environ.get("TIMEZONE", "America/Los_Angeles")

# Default ticker / timeframe on load
DEFAULT_TICKER    = os.environ.get("DEFAULT_TICKER", "SPY")
DEFAULT_TIMEFRAME = os.environ.get("DEFAULT_TIMEFRAME", "5Min")

# Watchlist for key level pre-loading
# QQQ and GOOG require FMP paid plan — use GOOGL (Class A) instead
_DEFAULT_WATCHLIST = [
    "SPY", "AAPL", "TSLA", "AMD", "NVDA", "PLTR",
    "MSFT", "AMZN", "META", "GOOGL",
]
_wl = os.environ.get("WATCHLIST", "")
WATCHLIST = [s.strip() for s in _wl.split(",") if s.strip()] if _wl else _DEFAULT_WATCHLIST
