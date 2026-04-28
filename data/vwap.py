"""
VWAP (Volume-Weighted Average Price) computation.

Computes running VWAP from 1-min bars for the current RTH session.
"""

from datetime import datetime

import pytz

import config
from data.fmp_rest import fetch_bars

TZ = pytz.timezone(config.TIMEZONE)
ET = pytz.timezone("America/New_York")


def _et_to_local_hhmm(et_hour, et_minute):
    ref = ET.localize(datetime(2026, 4, 27, et_hour, et_minute))
    local = ref.astimezone(TZ)
    return local.hour * 100 + local.minute


_RTH_START = _et_to_local_hhmm(9, 30)
_RTH_END   = _et_to_local_hhmm(16, 0)


def _hhmm(epoch):
    local = datetime.fromtimestamp(epoch, TZ)
    return local.hour * 100 + local.minute


def compute_vwap(api, ticker, date=None):
    """Compute VWAP for a trading session.

    Returns: [{"time": epoch, "value": float}, ...]
    """
    now = datetime.now(TZ)
    if date is None:
        date = now.date()

    start = TZ.localize(datetime(date.year, date.month, date.day,
                                  _RTH_START // 100, _RTH_START % 100))
    end   = TZ.localize(datetime(date.year, date.month, date.day,
                                  _RTH_END // 100,   _RTH_END % 100))

    bars = fetch_bars(api, ticker, "1Min", start=start, end=end)
    rth  = [b for b in bars if _RTH_START <= _hhmm(b["time"]) <= _RTH_END]

    if not rth:
        return []

    result = []
    cum_tp_vol = 0.0
    cum_vol    = 0

    for bar in rth:
        typical = (bar["high"] + bar["low"] + bar["close"]) / 3
        cum_tp_vol += typical * bar["volume"]
        cum_vol    += bar["volume"]
        if cum_vol > 0:
            result.append({
                "time":  bar["time"],
                "value": round(cum_tp_vol / cum_vol, 2),
            })

    return result
