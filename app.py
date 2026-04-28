"""
PunkTrader — Flask Application

Serves the charting frontend and provides REST endpoints for historical
bar data, key levels, and VWAP. SSE endpoint for real-time streaming.
"""

import json
import os
import queue
import threading
import webbrowser

from flask import Flask, Response, jsonify, redirect, render_template, request

from dotenv import dotenv_values, set_key

import config
from data.fmp_rest import fetch_bars, get_api
from data.fmp_batch_poller import FMPBatchPoller
from data.candle_builder import CandleBuilder
from data.vwap import compute_vwap
from levels.alerts import AlertState, evaluate_bar, check_proximity
from levels.compute import get_levels
import levels.cache as level_cache

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Real-time streaming state
# ---------------------------------------------------------------------------

class StreamState:
    """Manages SSE subscribers and Alpaca WebSocket lifecycle."""

    def __init__(self):
        self._subscribers = {}     # {ticker: [queue, ...]}
        self._wl_queues = []       # queues for /stream/watchlist
        self._wl_last_tick = {}    # {ticker: (price, timestamp)} for coalescing
        self._lock = threading.Lock()
        self.candle_builder = CandleBuilder()
        self.stream = None
        self._levels = {}          # {ticker: {level_name: price}}
        self._alert_states = {}    # {(ticker, level_name): AlertState}

    def subscribe(self, ticker):
        """Subscribe a new SSE client to a ticker. Returns a queue."""
        ticker = ticker.upper()
        q = queue.Queue()
        with self._lock:
            if ticker not in self._subscribers:
                self._subscribers[ticker] = []
            self._subscribers[ticker].append(q)

        # Ensure WebSocket is subscribed to this ticker
        if self.stream:
            self.stream.subscribe(ticker)

        # Load levels for alert engine (background, non-blocking)
        threading.Thread(target=self.load_levels, args=(ticker,), daemon=True).start()

        return q

    def unsubscribe(self, ticker, q):
        ticker = ticker.upper()
        with self._lock:
            if ticker in self._subscribers:
                if q in self._subscribers[ticker]:
                    self._subscribers[ticker].remove(q)
                if not self._subscribers[ticker]:
                    del self._subscribers[ticker]

        # Only unsubscribe from poller if not a permanent watchlist ticker
        if self.stream and ticker not in [t.upper() for t in config.WATCHLIST]:
            self.stream.unsubscribe(ticker)

    def broadcast(self, ticker, data):
        """Send data to all SSE subscribers for a ticker."""
        ticker = ticker.upper()
        with self._lock:
            queues = list(self._subscribers.get(ticker, []))
        for q in queues:
            try:
                q.put_nowait(data)
            except queue.Full:
                pass

    def on_trade(self, ticker, price, size, timestamp_epoch):
        prev_candle = self.candle_builder.get_candle(ticker)
        candle, is_new = self.candle_builder.on_trade(ticker, price, size, timestamp_epoch)
        event = json.dumps({"type": "trade", "candle": candle})
        self.broadcast(ticker, event)
        if is_new and prev_candle:
            self.broadcast(ticker, json.dumps({"type": "bar", "candle": prev_candle}))
            self._run_alerts(ticker, prev_candle)
        self._broadcast_watchlist_tick(ticker, price)

    def on_bar(self, ticker, bar_data):
        self.candle_builder.on_bar(ticker, bar_data)
        event = json.dumps({"type": "bar", "candle": bar_data})
        self.broadcast(ticker, event)
        self._run_alerts(ticker, bar_data)

    def load_levels(self, ticker):
        """Load key levels for a ticker (called when a panel subscribes)."""
        if ticker in self._levels:
            return
        try:
            cached = level_cache.get(ticker)
            if cached and all(v is not None for v in cached.values()):
                levels = cached
            else:
                api = get_api()
                levels = get_levels(api, ticker)
                if levels:
                    level_cache.set(ticker, levels)
                if cached:
                    for k, v in cached.items():
                        if levels.get(k) is None and v is not None:
                            levels[k] = v
            self._levels[ticker] = levels or {}
            for level_name in self._levels[ticker]:
                key = (ticker, level_name)
                if key not in self._alert_states:
                    self._alert_states[key] = AlertState()
        except Exception:
            pass

    def _run_alerts(self, ticker, bar_data):
        """Run alert engine on a finalized bar."""
        levels = self._levels.get(ticker)
        if not levels:
            return

        for level_name, level_price in levels.items():
            if level_price is None:
                continue
            key = (ticker, level_name)
            alert_state = self._alert_states.get(key)
            if not alert_state:
                continue

            # Check proximity
            prox = check_proximity(ticker, level_name, level_price,
                                   bar_data["close"], alert_state,
                                   bar_data["time"])
            if prox:
                self.broadcast(ticker, json.dumps({"type": "alert", **prox}))

            # Evaluate bar
            alert = evaluate_bar(ticker, level_name, level_price,
                                 bar_data["open"], bar_data["high"],
                                 bar_data["low"], bar_data["close"],
                                 alert_state, bar_data["time"])
            if alert:
                self.broadcast(ticker, json.dumps({"type": "alert", **alert}))

    def _broadcast_watchlist_tick(self, ticker, price):
        """Fan out price tick to /stream/watchlist subscribers (500ms coalesce)."""
        import time as _time
        now = _time.time()
        last_price, last_ts = self._wl_last_tick.get(ticker, (None, 0))
        if now - last_ts < 0.5 and price == last_price:
            return
        self._wl_last_tick[ticker] = (price, now)
        payload = json.dumps({"type": "price", "ticker": ticker, "price": price})
        with self._lock:
            queues = list(self._wl_queues)
        for q in queues:
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass

    def subscribe_watchlist(self):
        """Subscribe a client to the watchlist SSE stream."""
        q = queue.Queue(maxsize=200)
        with self._lock:
            self._wl_queues.append(q)
        return q

    def unsubscribe_watchlist(self, q):
        with self._lock:
            if q in self._wl_queues:
                self._wl_queues.remove(q)

    def start_stream(self):
        if self.stream:
            return
        self.stream = FMPBatchPoller(
            on_trade=self.on_trade,
            on_bar=self.on_bar,
        )
        self.stream.start()
        # Permanently subscribe all watchlist tickers (baseline refcount)
        for ticker in config.WATCHLIST:
            self.stream.subscribe(ticker.upper())

    def stop_stream(self):
        if self.stream:
            self.stream.stop()
            self.stream = None


state = StreamState()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

_TIMEZONES = [
    "America/New_York", "America/Chicago",
    "America/Denver", "America/Los_Angeles",
]

_ENV_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '.env'
)


@app.route("/")
def index():
    return render_template("index.html",
                           default_ticker=config.DEFAULT_TICKER,
                           default_timeframe=config.DEFAULT_TIMEFRAME,
                           watchlist=config.WATCHLIST)


@app.route("/settings")
def settings_page():
    env = dotenv_values(_ENV_PATH) if os.path.exists(_ENV_PATH) else {}
    return render_template("settings.html", env=env, timezones=_TIMEZONES)


@app.route("/settings", methods=["POST"])
def save_settings():
    if not os.path.exists(_ENV_PATH):
        with open(_ENV_PATH, "w") as f:
            f.write("")

    set_key(_ENV_PATH, "FMP_API_KEY", request.form.get("fmp_api_key", "").strip())
    set_key(_ENV_PATH, "TIMEZONE", request.form.get("timezone", "America/New_York"))
    set_key(_ENV_PATH, "DEFAULT_TICKER", request.form.get("default_ticker", "SPY").strip().upper())

    wl = request.form.get("watchlist", "").strip()
    tickers = ",".join(s.strip().upper() for s in wl.replace("\n", ",").split(",") if s.strip())
    if tickers:
        set_key(_ENV_PATH, "WATCHLIST", tickers)

    return redirect("/settings?saved=1")


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.route("/api/bars/<ticker>")
def api_bars(ticker):
    """Fetch historical OHLCV bars."""
    timeframe = request.args.get("timeframe", "5Min")
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        api = get_api()
        bars = fetch_bars(api, ticker.upper(), timeframe=timeframe,
                          start=start, end=end)
        return jsonify(bars)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/levels/<ticker>")
def api_levels(ticker):
    """Compute key levels (PDH/PDL, PMH/PML, ORH/ORL) for a ticker."""
    try:
        api = get_api()
        levels = get_levels(api, ticker.upper())
        return jsonify(levels)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/quote/<ticker>")
def api_quote(ticker):
    """Single quote passthrough — used by watchlist for initial render."""
    try:
        import requests as _req
        r = _req.get(f"{config.FMP_BASE_URL}/quote",
                     params={"symbol": ticker.upper(), "apikey": config.FMP_API_KEY},
                     timeout=8)
        r.raise_for_status()
        data = r.json()
        q = data[0] if isinstance(data, list) and data else {}
        return jsonify({"price": q.get("price"), "changePercentage": q.get("changePercentage")})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/vwap/<ticker>")
def api_vwap(ticker):
    """Compute VWAP for today's session."""
    try:
        api = get_api()
        vwap_data = compute_vwap(api, ticker.upper())
        return jsonify(vwap_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------------
# SSE streaming
# ---------------------------------------------------------------------------

@app.route("/stream/watchlist")
def stream_watchlist():
    """SSE — price ticks for all watchlist tickers."""
    def event_stream():
        q = state.subscribe_watchlist()
        try:
            while True:
                try:
                    data = q.get(timeout=30)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            state.unsubscribe_watchlist(q)

    return Response(event_stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/stream/<ticker>")
def stream_ticker(ticker):
    """SSE endpoint — streams real-time trades and bars for a ticker."""
    ticker = ticker.upper()

    def event_stream():
        q = state.subscribe(ticker)
        try:
            while True:
                try:
                    data = q.get(timeout=30)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            state.unsubscribe(ticker, q)

    return Response(event_stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    # Start Alpaca WebSocket stream
    state.start_stream()

    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    print(f"PunkTrader running at http://localhost:{port}")

    try:
        from livereload import Server
        server = Server(app.wsgi_app)
        server.watch('app.py')
        server.watch('config.py')
        server.watch('data/')
        server.watch('levels/')
        server.watch('templates/')
        server.watch('static/')
        server.serve(host="127.0.0.1", port=port)
    except ImportError:
        app.run(host="127.0.0.1", port=port, debug=False)
