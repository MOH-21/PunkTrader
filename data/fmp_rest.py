"""
Fetch historical bar data from Financial Modeling Prep (FMP) stable API.

Free plan limits:
  - 250 API calls/day
  - No ETFs (e.g. QQQ) or some large-cap tickers (e.g. GOOG) — those need paid plan
  - Single-symbol queries only (multi-symbol = paid)
"""

import calendar
from datetime import datetime, timedelta, timezone

import pytz
import requests

import config

TZ = pytz.timezone(config.TIMEZONE)
ET = pytz.timezone("America/New_York")

_INTRADAY_RES = {"1Min", "5Min", "15Min", "1Hour", "4Hour"}

_FMP_RES = {
    "1Min":  "1min",
    "5Min":  "5min",
    "15Min": "15min",
    "1Hour": "1hour",
    "4Hour": "4hour",
}

_DEFAULT_LOOKBACK = {
    "1Min":  timedelta(days=7),
    "5Min":  timedelta(days=5),
    "15Min": timedelta(days=10),
    "1Hour": timedelta(days=30),
    "4Hour": timedelta(days=60),
    "1Day":  timedelta(days=365),
    "1Week": timedelta(days=365 * 2),
}


class FMPClient:
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url

    def get(self, path, params=None):
        p = dict(params or {})
        p["apikey"] = self.api_key
        resp = requests.get(f"{self.base_url}{path}", params=p, timeout=10)
        resp.raise_for_status()
        return resp.json()


def get_api():
    return FMPClient(config.FMP_API_KEY, config.FMP_BASE_URL)


def _parse_et_dt(date_str):
    """Parse FMP date string (Eastern Time) to tz-aware datetime."""
    fmt = "%Y-%m-%d %H:%M:%S" if " " in date_str else "%Y-%m-%d"
    return ET.localize(datetime.strptime(date_str, fmt))


def _to_local_epoch(dt_et):
    """Convert ET datetime to 'fake UTC' epoch for lightweight-charts local display."""
    local_dt = dt_et.astimezone(TZ)
    return int(calendar.timegm(local_dt.timetuple()))


def _aggregate_weekly(daily_bars):
    """Aggregate daily bars into ISO-week bars (keyed to Monday)."""
    weeks = {}
    for bar in daily_bars:
        dt = datetime.fromtimestamp(bar["time"], tz=timezone.utc)
        monday = dt - timedelta(days=dt.weekday())
        week_key = int(monday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

        if week_key not in weeks:
            weeks[week_key] = {**bar, "time": week_key}
        else:
            w = weeks[week_key]
            w["high"]   = max(w["high"], bar["high"])
            w["low"]    = min(w["low"],  bar["low"])
            w["close"]  = bar["close"]
            w["volume"] += bar["volume"]

    return sorted(weeks.values(), key=lambda x: x["time"])


def fetch_bars(api, ticker, timeframe="5Min", start=None, end=None):
    """Fetch historical bars from FMP stable API.

    Returns: [{"time": epoch, "open": f, "high": f, "low": f, "close": f, "volume": i}, ...]
    """
    now = datetime.now(TZ)
    if end is None:
        end = now
    if start is None:
        lookback = _DEFAULT_LOOKBACK.get(timeframe, timedelta(days=5))
        start = now - lookback

    start_str = start.strftime("%Y-%m-%d") if isinstance(start, datetime) else str(start)[:10]
    end_str   = end.strftime("%Y-%m-%d")   if isinstance(end,   datetime) else str(end)[:10]

    if timeframe in _INTRADAY_RES:
        res = _FMP_RES[timeframe]
        raw = api.get(f"/historical-chart/{res}", {
            "symbol":   ticker,
            "from":     start_str,
            "to":       end_str,
            "extended": "true",
        })
        raw = list(reversed(raw)) if isinstance(raw, list) else []
    else:
        # Daily EOD — new stable endpoint returns a flat list
        raw = api.get("/historical-price-eod/full", {
            "symbol": ticker,
            "from":   start_str,
            "to":     end_str,
        })
        raw = list(reversed(raw)) if isinstance(raw, list) else []

    result = []
    for bar in raw:
        try:
            epoch = _to_local_epoch(_parse_et_dt(bar["date"]))
            result.append({
                "time":   epoch,
                "open":   round(float(bar["open"]),  2),
                "high":   round(float(bar["high"]),  2),
                "low":    round(float(bar["low"]),   2),
                "close":  round(float(bar["close"]), 2),
                "volume": int(bar.get("volume", 0)),
            })
        except (KeyError, ValueError):
            continue

    if timeframe == "1Week":
        result = _aggregate_weekly(result)

    return result
