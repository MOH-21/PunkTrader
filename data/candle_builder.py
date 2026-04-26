"""
CandleBuilder — aggregates trades into in-progress candles.

Maintains current candle state per ticker. When a trade arrives,
updates the candle's OHLCV. When the time bucket rolls over,
the previous candle is finalized and a new one starts.
"""

import threading


class CandleBuilder:
    def __init__(self):
        # {ticker: {"time": int, "open": f, "high": f, "low": f, "close": f, "volume": int}}
        self._candles = {}
        self._lock = threading.Lock()

    def on_trade(self, ticker, price, size, timestamp_epoch):
        """Process a trade. Returns the updated candle dict for the current minute.

        timestamp_epoch: Unix timestamp (seconds) of the trade.
        Returns: (candle_dict, is_new_bar) — is_new_bar True if a new minute started.
        """
        # Bucket to the start of the minute
        bar_time = (timestamp_epoch // 60) * 60

        with self._lock:
            current = self._candles.get(ticker)
            is_new = False

            if current is None or current["time"] != bar_time:
                # New bar
                is_new = current is not None and current["time"] != bar_time
                self._candles[ticker] = {
                    "time": bar_time,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": size,
                }
            else:
                # Update existing bar
                current["high"] = max(current["high"], price)
                current["low"] = min(current["low"], price)
                current["close"] = price
                current["volume"] += size

            return dict(self._candles[ticker]), is_new

    def on_bar(self, ticker, bar_data):
        """Process a finalized 1-min bar from Alpaca.

        Replaces the in-progress candle with the authoritative bar data.
        bar_data: {"time": epoch, "open": f, "high": f, "low": f, "close": f, "volume": int}
        """
        with self._lock:
            self._candles[ticker] = dict(bar_data)

    def get_candle(self, ticker):
        """Get the current in-progress candle for a ticker."""
        with self._lock:
            c = self._candles.get(ticker)
            return dict(c) if c else None
