"""
Key level computation — PDH/PDL, PMH/PML, ORH/ORL.

Uses FMP historical bars. Trading calendar is holiday-aware via FMP API.
"""

from datetime import datetime, timedelta, timezone

import pytz

import config
from data.fmp_rest import fetch_bars, get_api

TZ = pytz.timezone(config.TIMEZONE)


def _hhmm(epoch):
    """Extract local HHMM from a 'fake UTC' epoch.

    Bars use calendar.timegm(local_timetuple) to store local time as if it were
    UTC (so lightweight-charts renders local-time labels without offset).
    Inverting with fromtimestamp(tz=UTC) gives back the original local time.
    """
    utc_dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return utc_dt.hour * 100 + utc_dt.minute


# Time windows in local HHMM (adapts to configured TIMEZONE).
# e.g. for America/Los_Angeles: 630 = 6:30 AM PDT, 1300 = 1:00 PM PDT.
_RTH_START = 630   # 6:30 AM  — regular trading hours open
_RTH_END   = 1300  # 1:00 PM  — regular trading hours close
_PREMARKET_START = 100  # 1:00 AM  — premarket open
_PREMARKET_END   = 629  # 6:29 AM  — premarket close
_OR_START = 630   # 6:30 AM  — opening range start
_OR_END   = 634   # 6:34 AM  — opening range end (first 5-min candle)


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

    # PDH/PDL — previous trading day, RTH only (6:30 AM–1:00 PM local)
    prev = _previous_trading_day()
    if prev:
        pd_start = TZ.localize(datetime(prev.year, prev.month, prev.day, 6, 30))
        pd_end   = TZ.localize(datetime(prev.year, prev.month, prev.day, 13, 0))
        bars = fetch_bars(api, ticker, "1Min", start=pd_start, end=pd_end)
        day_bars = [b for b in bars if _RTH_START <= _hhmm(b["time"]) <= _RTH_END]
        if day_bars:
            levels["PDH"] = round(max(b["high"] for b in day_bars), 2)
            levels["PDL"] = round(min(b["low"]  for b in day_bars), 2)

    # PMH/PML — today's premarket (1:00 AM–6:29 AM local)
    pm_start = TZ.localize(datetime(today.year, today.month, today.day, 1, 0))
    pm_end   = TZ.localize(datetime(today.year, today.month, today.day, 6, 29))
    bars = fetch_bars(api, ticker, "1Min", start=pm_start, end=pm_end)
    pm_bars = [b for b in bars if _PREMARKET_START <= _hhmm(b["time"]) <= _PREMARKET_END]
    if pm_bars:
        levels["PMH"] = round(max(b["high"] for b in pm_bars), 2)
        levels["PML"] = round(min(b["low"]  for b in pm_bars), 2)

    # ORH/ORL — opening range (6:30–6:34 AM local, first 5-min candle)
    or_start = TZ.localize(datetime(today.year, today.month, today.day, 6, 30))
    or_end   = TZ.localize(datetime(today.year, today.month, today.day, 6, 35))
    bars = fetch_bars(api, ticker, "5Min", start=or_start, end=or_end)
    or_bars = [b for b in bars if _OR_START <= _hhmm(b["time"]) <= _OR_END]
    if or_bars:
        levels["ORH"] = round(max(b["high"] for b in or_bars), 2)
        levels["ORL"] = round(min(b["low"]  for b in or_bars), 2)

    return levels
