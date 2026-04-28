"""
Key level computation — PDH/PDL, PMH/PML, ORH/ORL.

Uses FMP historical bars. Trading calendar is holiday-aware via FMP API.
"""

from datetime import datetime, timedelta

import pytz

import config
from data.fmp_rest import fetch_bars, get_api

TZ = pytz.timezone(config.TIMEZONE)
ET = pytz.timezone("America/New_York")


def _et_to_local_hhmm(et_hour, et_minute):
    ref = ET.localize(datetime(2026, 4, 27, et_hour, et_minute))
    return ref.astimezone(TZ).hour * 100 + ref.astimezone(TZ).minute


def _hhmm(epoch):
    local = datetime.fromtimestamp(epoch, TZ)
    return local.hour * 100 + local.minute


# Time windows in local HHMM
_FULL_DAY_START  = _et_to_local_hhmm(4,  0)
_FULL_DAY_END    = _et_to_local_hhmm(19, 58)
_PREMARKET_START = _et_to_local_hhmm(4,  0)
_PREMARKET_END   = _et_to_local_hhmm(9,  29)
_OR_START        = _et_to_local_hhmm(9,  30)
_OR_END          = _et_to_local_hhmm(9,  34)


_calendar_cache = {}


def _previous_trading_day():
    """Return the most recent trading day before today (holiday-aware via FMP API).

    Calls FMP EOD endpoint to get actual trading days from the past ~10 days.
    Caches result per session day to avoid repeated API calls.
    Falls back to weekday logic if FMP call fails.
    """
    today = datetime.now(TZ).date()
    today_str = today.isoformat()

    # Check cache first
    if today_str in _calendar_cache:
        return _calendar_cache[today_str]

    try:
        api = get_api()
        from_date = (today - timedelta(days=10)).isoformat()
        to_date = today.isoformat()

        # Fetch ~10 days of EOD data to find the last trading day
        raw_data = api.get("/historical-price-eod/full", {
            "symbol": "SPY",
            "from": from_date,
            "to": to_date,
        })

        # Parse dates from response (FMP returns in descending order by default)
        if not isinstance(raw_data, list) or not raw_data:
            raise ValueError("No trading day data from FMP")

        trading_dates = []
        for item in raw_data:
            if "date" in item:
                try:
                    date_obj = datetime.strptime(item["date"], "%Y-%m-%d").date()
                    if date_obj < today:
                        trading_dates.append(date_obj)
                except ValueError:
                    continue

        if trading_dates:
            # Find the most recent trading day before today
            prev_day = max(trading_dates)
            _calendar_cache[today_str] = prev_day
            return prev_day
        else:
            raise ValueError("No trading dates found before today")

    except Exception as e:
        # Fail-soft: fall back to weekday logic
        print(f"Warning: FMP API call failed for trading calendar ({e}), falling back to weekday logic")
        candidate = today - timedelta(days=1)
        for _ in range(7):
            if candidate.weekday() < 5:
                _calendar_cache[today_str] = candidate
                return candidate
            candidate -= timedelta(days=1)
        return None


def get_levels(api, ticker):
    """Compute key levels for a ticker.

    Returns: {"PDH": float|None, "PDL": float|None, "PMH": float|None,
              "PML": float|None, "ORH": float|None, "ORL": float|None}
    """
    now    = datetime.now(TZ)
    today  = now.date()
    levels = {k: None for k in ("PDH", "PDL", "PMH", "PML", "ORH", "ORL")}

    # PDH/PDL — previous trading day full session
    prev = _previous_trading_day()
    if prev:
        pd_start = TZ.localize(datetime(prev.year, prev.month, prev.day, 1, 0))
        pd_end   = TZ.localize(datetime(prev.year, prev.month, prev.day, 23, 59))
        bars = fetch_bars(api, ticker, "1Min", start=pd_start, end=pd_end)
        day_bars = [b for b in bars if _FULL_DAY_START <= _hhmm(b["time"]) <= _FULL_DAY_END]
        if day_bars:
            levels["PDH"] = round(max(b["high"] for b in day_bars), 2)
            levels["PDL"] = round(min(b["low"]  for b in day_bars), 2)

    # PMH/PML — today's premarket
    pm_start = TZ.localize(datetime(today.year, today.month, today.day, 1, 0))
    pm_end   = TZ.localize(datetime(today.year, today.month, today.day,
                                     _PREMARKET_END // 100, _PREMARKET_END % 100))
    bars = fetch_bars(api, ticker, "1Min", start=pm_start, end=pm_end)
    pm_bars = [b for b in bars if _PREMARKET_START <= _hhmm(b["time"]) <= _PREMARKET_END]
    if pm_bars:
        levels["PMH"] = round(max(b["high"] for b in pm_bars), 2)
        levels["PML"] = round(min(b["low"]  for b in pm_bars), 2)

    # ORH/ORL — opening range 09:30–09:34 ET
    or_start = TZ.localize(datetime(today.year, today.month, today.day,
                                     _OR_START // 100, _OR_START % 100))
    or_end   = TZ.localize(datetime(today.year, today.month, today.day,
                                     _OR_END // 100, _OR_END % 100))
    bars = fetch_bars(api, ticker, "1Min", start=or_start, end=or_end)
    or_bars = [b for b in bars if _OR_START <= _hhmm(b["time"]) <= _OR_END]
    if or_bars:
        levels["ORH"] = round(max(b["high"] for b in or_bars), 2)
        levels["ORL"] = round(min(b["low"]  for b in or_bars), 2)

    return levels
