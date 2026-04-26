"""
VWAP (Volume-Weighted Average Price) computation.

Computes running VWAP from 1-min bars for the current session.
"""

import calendar
from datetime import datetime

import pytz
from alpaca_trade_api.rest import TimeFrame

import config

TZ = pytz.timezone(config.TIMEZONE)
ET = pytz.timezone("America/New_York")


def _et_to_local_hhmm(et_hour, et_minute):
    ref = datetime(2026, 4, 27, et_hour, et_minute)
    et_time = ET.localize(ref)
    local_time = et_time.astimezone(TZ)
    return local_time.hour * 100 + local_time.minute


_RTH_START = _et_to_local_hhmm(9, 30)
_RTH_END = _et_to_local_hhmm(16, 0)


def compute_vwap(api, ticker, date=None):
    """Compute VWAP for a trading session.

    Returns a list of dicts: [{"time": epoch, "value": float}, ...]
    """
    now = datetime.now(TZ)
    if date is None:
        date = now.date()

    # Fetch 1-min bars for the session
    start = TZ.localize(datetime(date.year, date.month, date.day,
                                  _RTH_START // 100, _RTH_START % 100))
    end = TZ.localize(datetime(date.year, date.month, date.day,
                                _RTH_END // 100, _RTH_END % 100))

    bars = api.get_bars(ticker, TimeFrame.Minute,
                        start=start.isoformat(), end=end.isoformat(),
                        feed=config.DATA_FEED).df

    if bars.empty:
        return []

    # Filter to RTH
    idx = bars.index.tz_convert(TZ)
    mask = [(_RTH_START <= ts.hour * 100 + ts.minute <= _RTH_END) for ts in idx]
    bars = bars[mask]

    if bars.empty:
        return []

    # Compute running VWAP: cumulative(typical_price * volume) / cumulative(volume)
    typical_price = (bars["high"] + bars["low"] + bars["close"]) / 3
    cum_tp_vol = (typical_price * bars["volume"]).cumsum()
    cum_vol = bars["volume"].cumsum()

    vwap_values = cum_tp_vol / cum_vol

    result = []
    for ts, val in zip(bars.index, vwap_values):
        if cum_vol[ts] > 0:
            local_dt = ts.tz_convert(TZ)
            epoch = int(calendar.timegm(local_dt.timetuple()))
            result.append({
                "time": epoch,
                "value": round(float(val), 2),
            })

    return result
