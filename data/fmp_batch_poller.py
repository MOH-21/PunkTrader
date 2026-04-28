"""
FMP batch polling — replaces fmp_poller.py.

Paid plan: no 250/day cap, no WebSocket. Uses /batch-quote?symbols=A,B,C
to fetch all subscribed tickers in a single request every POLL_INTERVAL seconds.
"""

import calendar
import threading
import time
from datetime import datetime

import pytz
import requests

import config

_TZ = pytz.timezone(config.TIMEZONE)
POLL_INTERVAL = 5


def _now_epoch():
    return int(calendar.timegm(datetime.now(_TZ).timetuple()))


class FMPBatchPoller:
    def __init__(self, on_trade=None, on_bar=None):
        """
        on_trade(ticker, price, size, timestamp_epoch)
        on_bar: unused — bar rollover is handled by StreamState.on_trade via CandleBuilder
        """
        self.on_trade = on_trade
        self._refcount = {}
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
            if tickers:
                self._fetch_batch(tickers)
            time.sleep(POLL_INTERVAL)

    def _fetch_batch(self, tickers):
        try:
            resp = requests.get(
                f"{config.FMP_BASE_URL}/batch-quote",
                params={"symbols": ",".join(tickers), "apikey": config.FMP_API_KEY},
                timeout=8,
            )
            if resp.status_code != 200:
                return
            data = resp.json()
            if not isinstance(data, list):
                return
        except Exception:
            return

        now_epoch = _now_epoch()

        for q in data:
            ticker = q.get("symbol", "").upper()
            if not ticker:
                continue
            price = q.get("price")
            if price is None:
                continue

            if self.on_trade:
                self.on_trade(ticker, float(price), 0, now_epoch)
