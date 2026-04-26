"""
Alpaca WebSocket client — subscribes to trades and bars for real-time data.

Single connection shared across all chart panels. Manages subscriptions
with reference counting.
"""

import calendar
import json
import threading
import time
from datetime import datetime

import pytz
import websocket

import config

_TZ = pytz.timezone(config.TIMEZONE)


def _local_epoch(dt):
    """Convert a UTC datetime to a 'fake UTC' epoch matching the configured timezone."""
    local_dt = dt.astimezone(_TZ)
    return int(calendar.timegm(local_dt.timetuple()))


class AlpacaStream:
    def __init__(self, on_trade=None, on_bar=None):
        """
        on_trade(ticker, price, size, timestamp_epoch): called on each trade
        on_bar(ticker, bar_dict): called on each finalized 1-min bar
        """
        self.on_trade = on_trade
        self.on_bar = on_bar

        self._ws = None
        self._running = False
        self._authenticated = False
        self._subscribed = set()  # currently subscribed tickers
        self._refcount = {}  # ticker -> int (how many panels watching)
        self._lock = threading.Lock()

    def subscribe(self, ticker):
        """Add a ticker subscription. Thread-safe, reference-counted."""
        ticker = ticker.upper()
        with self._lock:
            self._refcount[ticker] = self._refcount.get(ticker, 0) + 1
            if ticker not in self._subscribed and self._authenticated:
                self._send_subscribe([ticker])
                self._subscribed.add(ticker)

    def unsubscribe(self, ticker):
        """Remove a ticker subscription. Only actually unsubscribes when refcount hits 0."""
        ticker = ticker.upper()
        with self._lock:
            count = self._refcount.get(ticker, 0) - 1
            if count <= 0:
                self._refcount.pop(ticker, None)
                if ticker in self._subscribed and self._authenticated:
                    self._send_unsubscribe([ticker])
                    self._subscribed.discard(ticker)
            else:
                self._refcount[ticker] = count

    def _send_subscribe(self, tickers):
        if self._ws:
            msg = json.dumps({"action": "subscribe", "trades": tickers, "bars": tickers})
            try:
                self._ws.send(msg)
            except Exception:
                pass

    def _send_unsubscribe(self, tickers):
        if self._ws:
            msg = json.dumps({"action": "unsubscribe", "trades": tickers, "bars": tickers})
            try:
                self._ws.send(msg)
            except Exception:
                pass

    def start(self):
        """Start WebSocket connection in a daemon thread."""
        self._running = True
        thread = threading.Thread(target=self._connect, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def _connect(self):
        while self._running:
            self._authenticated = False
            self._ws = websocket.WebSocketApp(
                config.WS_URL,
                on_open=self._on_open,
                on_message=self._on_message,
                on_close=self._on_close,
                on_error=self._on_error,
            )
            self._ws.run_forever()
            if self._running:
                time.sleep(2)  # reconnect delay

    def _on_open(self, ws):
        auth_msg = json.dumps({
            "action": "auth",
            "key": config.ALPACA_API_KEY,
            "secret": config.ALPACA_API_SECRET,
        })
        ws.send(auth_msg)

    def _on_message(self, ws, message):
        try:
            msgs = json.loads(message)
        except json.JSONDecodeError:
            return

        for msg in msgs:
            msg_type = msg.get("T")

            if msg_type == "success" and msg.get("msg") == "authenticated":
                self._authenticated = True
                # Subscribe to all tickers with active refcounts
                with self._lock:
                    tickers = list(self._refcount.keys())
                    if tickers:
                        self._send_subscribe(tickers)
                        self._subscribed.update(tickers)

            elif msg_type == "t":  # Trade
                ticker = msg.get("S")
                price = msg.get("p")
                size = msg.get("s", 0)
                ts = msg.get("t", "")
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    epoch = _local_epoch(dt)
                except (ValueError, AttributeError):
                    continue
                if self.on_trade and ticker and price:
                    self.on_trade(ticker, float(price), int(size), epoch)

            elif msg_type == "b":  # Bar (finalized 1-min)
                ticker = msg.get("S")
                ts = msg.get("t", "")
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    epoch = _local_epoch(dt)
                except (ValueError, AttributeError):
                    continue
                if self.on_bar and ticker:
                    bar = {
                        "time": epoch,
                        "open": float(msg.get("o", 0)),
                        "high": float(msg.get("h", 0)),
                        "low": float(msg.get("l", 0)),
                        "close": float(msg.get("c", 0)),
                        "volume": int(msg.get("v", 0)),
                    }
                    self.on_bar(ticker, bar)

    def _on_close(self, ws, close_status_code=None, close_msg=None):
        self._authenticated = False
        self._subscribed.clear()

    def _on_error(self, ws, error):
        pass
