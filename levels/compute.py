"""
Key level computation — adapted from key_levels_monitor.

Computes PDH/PDL, PMH/PML from Alpaca historical data.
ORH/ORL computed from the opening range (09:30-09:34 ET).
"""

from datetime import datetime, timedelta

import pytz
from alpaca_trade_api.rest import TimeFrame

import config

TZ = pytz.timezone(config.TIMEZONE)
ET = pytz.timezone("America/New_York")


def _hhmm(dt):
    return dt.hour * 100 + dt.minute


def _find_previous_trading_day(api):
    """Find the most recent completed trading day."""
    now = datetime.now(TZ)
    start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    calendar = api.get_calendar(start, end)

    today_date = now.date()
    prev_day = None
    for entry in calendar:
        entry_date = entry.date
        if hasattr(entry_date, "date"):
            entry_date = entry_date.date()
        if entry_date < today_date:
            prev_day = entry_date
    return prev_day


def _filter_bars_by_time(bars, start_hhmm, end_hhmm):
    """Filter bars DataFrame to a time window (in local timezone HHMM)."""
    if bars.empty:
        return bars
    idx = bars.index.tz_convert(TZ)
    mask = [(start_hhmm <= ts.hour * 100 + ts.minute <= end_hhmm) for ts in idx]
    return bars[mask]


def _et_to_local_hhmm(et_hour, et_minute):
    """Convert Eastern time to local HHMM."""
    ref = datetime(2026, 4, 27, et_hour, et_minute)
    et_time = ET.localize(ref)
    local_time = et_time.astimezone(TZ)
    return local_time.hour * 100 + local_time.minute


# Time boundaries in local timezone
_FULL_DAY_START = _et_to_local_hhmm(4, 0)
_FULL_DAY_END = _et_to_local_hhmm(19, 58)
_PREMARKET_START = _et_to_local_hhmm(4, 0)
_PREMARKET_END = _et_to_local_hhmm(9, 29)
_OR_START = _et_to_local_hhmm(9, 30)
_OR_END = _et_to_local_hhmm(9, 34)


def get_levels(api, ticker):
    """Compute key levels for a ticker.

    Returns: {"PDH": float|None, "PDL": float|None, "PMH": float|None,
              "PML": float|None, "ORH": float|None, "ORL": float|None}
    """
    now = datetime.now(TZ)
    levels = {"PDH": None, "PDL": None, "PMH": None, "PML": None,
              "ORH": None, "ORL": None}

    # PDH/PDL — previous trading day
    prev_day = _find_previous_trading_day(api)
    if prev_day:
        pd_start = TZ.localize(datetime(prev_day.year, prev_day.month, prev_day.day, 1, 0))
        pd_end = TZ.localize(datetime(prev_day.year, prev_day.month, prev_day.day, 16, 58))

        bars = api.get_bars(ticker, TimeFrame.Minute,
                            start=pd_start.isoformat(), end=pd_end.isoformat(),
                            feed=config.DATA_FEED).df
        filtered = _filter_bars_by_time(bars, _FULL_DAY_START, _FULL_DAY_END)
        if not filtered.empty:
            levels["PDH"] = round(float(filtered["high"].max()), 2)
            levels["PDL"] = round(float(filtered["low"].min()), 2)

    # PMH/PML — today's premarket
    today = now.date()
    pm_start = TZ.localize(datetime(today.year, today.month, today.day, 1, 0))
    pm_end = TZ.localize(datetime(today.year, today.month, today.day,
                                   _PREMARKET_END // 100, _PREMARKET_END % 100))

    bars = api.get_bars(ticker, TimeFrame.Minute,
                        start=pm_start.isoformat(), end=pm_end.isoformat(),
                        feed=config.DATA_FEED).df
    filtered = _filter_bars_by_time(bars, _PREMARKET_START, _PREMARKET_END)
    if not filtered.empty:
        levels["PMH"] = round(float(filtered["high"].max()), 2)
        levels["PML"] = round(float(filtered["low"].min()), 2)

    # ORH/ORL — opening range (09:30-09:34 ET)
    or_start_local = TZ.localize(datetime(today.year, today.month, today.day,
                                          _OR_START // 100, _OR_START % 100))
    or_end_local = TZ.localize(datetime(today.year, today.month, today.day,
                                        _OR_END // 100, _OR_END % 100))

    bars = api.get_bars(ticker, TimeFrame.Minute,
                        start=or_start_local.isoformat(),
                        end=or_end_local.isoformat(),
                        feed=config.DATA_FEED).df
    filtered = _filter_bars_by_time(bars, _OR_START, _OR_END)
    if not filtered.empty:
        levels["ORH"] = round(float(filtered["high"].max()), 2)
        levels["ORL"] = round(float(filtered["low"].min()), 2)

    return levels
