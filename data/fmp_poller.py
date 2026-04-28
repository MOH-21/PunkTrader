"""
FMP polling-based live data — replaces Alpaca WebSocket.

FMP free plan has no WebSocket. Polls /quote?symbol=TICKER one ticker at
a time (multi-symbol = paid). Emits trade events; detects minute boundaries
to synthesize bar finalization for alert processing.

Free plan budget: 250 calls/day. At POLL_INTERVAL=30s with 1 active ticker
= 2880 calls/day — exceeds quota. Adjust POLL_INTERVAL up if watching
multiple tickers simultaneously.
"""

import calendar
import threading
import time
from datetime import datetime

import pytz
import requests

import config

_TZ = pytz.timezone(config.TIMEZONE)
POLL_INTERVAL = 30  # seconds per ticker — tune vs. daily API quota


def _now_epoch():
    return int(calendar.timegm(datetime.now(_TZ).timetuple()))


class FMPPoller:
    def __init__(self, on_trade=None, on_bar=None):
        """
        on_trade(ticker, price, size, timestamp_epoch)
        on_bar(ticker, bar_dict) — synthesized at minute boundaries
        """
        self.on_trade = on_trade
        self.on_bar = on_bar
        self._refcount = {}
        self._last_minute = {}  # ticker -> last bar_minute epoch
        self._lock = threading.Lock()
        self._running = False

    def subscribe(self, ticker):
        ticker = ticker.upper()
        with self._lock:
            self._refcount[ticker] = self._refcount.get(ticker, 0) + 1

    def unsubscribe(self, ticker):
        ticker = ticker.upper()
        with self._lock:
            count = self._refcount.get(ticker, 0) - 1
            if count <= 0:
                self._refcount.pop(ticker, None)
                self._last_minute.pop(ticker, None)
            else:
                self._refcount[ticker] = count

    def start(self):
        self._running = True
        thread = threading.Thread(target=self._poll_loop, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            with self._lock:
                tickers = list(self._refcount.keys())
            for ticker in tickers:
                if not self._running:
                    break
                self._fetch_quote(ticker)
            time.sleep(POLL_INTERVAL)

    def _fetch_quote(self, ticker):
        try:
            resp = requests.get(
                f"{config.FMP_BASE_URL}/quote",
                params={"symbol": ticker, "apikey": config.FMP_API_KEY},
                timeout=8,
            )
            if resp.status_code != 200:
                return
            data = resp.json()
            q = data[0] if isinstance(data, list) and data else None
            if not q:
                return
        except Exception:
            return

        price = q.get("price")
        if price is None:
            return

        price = float(price)
        now_epoch = _now_epoch()
        bar_minute = (now_epoch // 60) * 60

        if self.on_trade:
            self.on_trade(ticker, price, 0, now_epoch)

        last = self._last_minute.get(ticker)
        if last is not None and bar_minute > last and self.on_bar:
            self.on_bar(ticker, {
                "time":   last,
                "open":   price,
                "high":   price,
                "low":    price,
                "close":  price,
                "volume": int(q.get("volume", 0)),
            })

        self._last_minute[ticker] = bar_minute
