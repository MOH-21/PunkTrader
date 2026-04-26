"""
Alert engine — adapted from key_levels_monitor.

Returns structured dicts instead of ANSI-formatted strings,
suitable for chart markers and browser notifications.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

WICK_THRESHOLD = 0.25
MAX_ALERTS_PER_LEVEL = 3


@dataclass
class AlertState:
    cross_count: int = 0
    side: Optional[str] = None
    has_broken: bool = False
    break_direction: Optional[str] = None
    proximity_fired: bool = False


def analyze_price_action(candle_open, candle_high, candle_low, candle_close):
    body = abs(candle_close - candle_open)
    total_range = candle_high - candle_low

    if total_range == 0 or body < total_range * 0.05:
        return "INDECISION", None

    upper_wick = candle_high - max(candle_open, candle_close)
    lower_wick = min(candle_open, candle_close) - candle_low

    is_green = candle_close > candle_open
    notable_lower = lower_wick >= total_range * WICK_THRESHOLD
    notable_upper = upper_wick >= total_range * WICK_THRESHOLD

    if is_green:
        detail = "buyer wick" if notable_lower else None
        return "STRONG", detail
    else:
        detail = "seller wick" if notable_upper else None
        return "WEAK", detail


def evaluate_bar(ticker, level_name, level_price, candle_open, candle_high,
                 candle_low, candle_close, alert_state, timestamp_epoch=None):
    """Evaluate a bar against a level.

    Returns a dict with alert info or None:
    {
        "ticker": str,
        "level": str,
        "level_price": float,
        "event": str,        # "BREAK ABOVE", "BREAK BELOW", "RECLAIM", "FADE"
        "kind": str,         # "break_above", "break_below", "reclaim", "fade"
        "close": float,
        "time": int,         # epoch
        "pa_label": str,     # "STRONG", "WEAK", "INDECISION"
        "pa_detail": str|None,
        "text": str,         # human-readable summary
    }
    """
    if level_price is None:
        return None

    if alert_state.cross_count >= MAX_ALERTS_PER_LEVEL:
        return None

    current_side = "above" if candle_close > level_price else "below"

    if alert_state.side is None:
        alert_state.side = current_side
        return None

    if current_side == alert_state.side:
        return None

    alert_state.side = current_side
    alert_state.cross_count += 1

    if not alert_state.has_broken:
        alert_state.has_broken = True
        alert_state.break_direction = "up" if current_side == "above" else "down"
        if current_side == "above":
            event, kind = "BREAK ABOVE", "break_above"
        else:
            event, kind = "BREAK BELOW", "break_below"
    else:
        if current_side == "above":
            event, kind = "RECLAIM", "reclaim"
        else:
            event, kind = "FADE", "fade"

    pa_label, pa_detail = analyze_price_action(
        candle_open, candle_high, candle_low, candle_close
    )

    text = f"{ticker} | {level_name} ({level_price:.2f}) | {event} | Close: {candle_close:.2f}"
    if pa_label:
        text += f" | {pa_label}"
        if pa_detail:
            text += f" ({pa_detail})"

    return {
        "ticker": ticker,
        "level": level_name,
        "level_price": level_price,
        "event": event,
        "kind": kind,
        "close": candle_close,
        "time": timestamp_epoch or int(datetime.now().timestamp()),
        "pa_label": pa_label,
        "pa_detail": pa_detail,
        "text": text,
    }


def check_proximity(ticker, level_name, level_price, candle_close, alert_state,
                    timestamp_epoch=None):
    """Check if price is approaching a level. Returns alert dict or None."""
    if level_price is None or alert_state.has_broken or alert_state.proximity_fired:
        return None
    if alert_state.side is None:
        return None

    distance_pct = abs(candle_close - level_price) / level_price * 100
    if distance_pct <= 0.15 and distance_pct > 0:
        alert_state.proximity_fired = True
        direction = "from below" if candle_close < level_price else "from above"
        text = f"{ticker} | {level_name} ({level_price:.2f}) | APPROACHING {direction} ({distance_pct:.2f}%)"
        return {
            "ticker": ticker,
            "level": level_name,
            "level_price": level_price,
            "event": "PROXIMITY",
            "kind": "proximity",
            "close": candle_close,
            "time": timestamp_epoch or int(datetime.now().timestamp()),
            "text": text,
        }

    return None
