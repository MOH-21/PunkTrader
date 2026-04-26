"""
Fetch historical bar data from Alpaca REST API.
"""

import calendar
from datetime import datetime, timedelta

import pytz
from alpaca_trade_api.rest import REST, TimeFrame, TimeFrameUnit

import config

TZ = pytz.timezone(config.TIMEZONE)


def _local_epoch(ts):
    """Convert a timezone-aware timestamp to a 'fake UTC' epoch for lightweight-charts.

    lightweight-charts displays Unix timestamps as UTC. To show local time,
    we convert to local wall clock time, then treat it as if it were UTC.
    """
    local_dt = ts.tz_convert(TZ)
    return int(calendar.timegm(local_dt.timetuple()))

# Map our timeframe strings to Alpaca TimeFrame objects
_TIMEFRAME_MAP = {
    "1Min": TimeFrame.Minute,
    "5Min": TimeFrame(5, TimeFrameUnit.Minute),
    "15Min": TimeFrame(15, TimeFrameUnit.Minute),
    "1Hour": TimeFrame.Hour,
    "4Hour": TimeFrame(4, TimeFrameUnit.Hour),
    "1Day": TimeFrame.Day,
    "1Week": TimeFrame.Week,
}

# How far back to fetch by default for each timeframe
_DEFAULT_LOOKBACK = {
    "1Min": timedelta(days=7),
    "5Min": timedelta(days=5),
    "15Min": timedelta(days=10),
    "1Hour": timedelta(days=30),
    "4Hour": timedelta(days=60),
    "1Day": timedelta(days=365),
    "1Week": timedelta(days=365 * 2),
}


def get_api():
    """Create and return an Alpaca REST client."""
    return REST(config.ALPACA_API_KEY, config.ALPACA_API_SECRET, config.BASE_URL)


def fetch_bars(api, ticker, timeframe="5Min", start=None, end=None):
    """Fetch historical bars from Alpaca.

    Returns a list of dicts: [{"time": epoch, "open": f, "high": f, "low": f, "close": f, "volume": i}, ...]
    Time is Unix timestamp (seconds) suitable for lightweight-charts.
    """
    tf = _TIMEFRAME_MAP.get(timeframe)
    if tf is None:
        raise ValueError(f"Unknown timeframe: {timeframe}")

    now = datetime.now(TZ)
    if end is None:
        end = now
    if start is None:
        lookback = _DEFAULT_LOOKBACK.get(timeframe, timedelta(days=5))
        start = now - lookback

    if isinstance(start, datetime):
        start = start.isoformat()
    if isinstance(end, datetime):
        end = end.isoformat()

    bars = api.get_bars(ticker, tf, start=start, end=end, feed=config.DATA_FEED).df

    if bars.empty:
        return []

    result = []
    for ts, row in bars.iterrows():
        epoch = _local_epoch(ts)
        result.append({
            "time": epoch,
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"]),
        })

    return result
