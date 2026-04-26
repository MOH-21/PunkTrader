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
from data.alpaca_rest import fetch_bars, get_api
from data.alpaca_ws import AlpacaStream
from data.candle_builder import CandleBuilder
from data.vwap import compute_vwap
from levels.alerts import AlertState, evaluate_bar, check_proximity
from levels.compute import get_levels

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Real-time streaming state
# ---------------------------------------------------------------------------

class StreamState:
    """Manages SSE subscribers and Alpaca WebSocket lifecycle."""

    def __init__(self):
        self._subscribers = {}  # {ticker: [queue, ...]}
        self._lock = threading.Lock()
        self.candle_builder = CandleBuilder()
        self.stream = None
        self._levels = {}       # {ticker: {level_name: price}}
        self._alert_states = {} # {(ticker, level_name): AlertState}

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

        # Unsubscribe from WebSocket if no more listeners
        if self.stream:
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
        candle, is_new = self.candle_builder.on_trade(ticker, price, size, timestamp_epoch)
        event = json.dumps({"type": "trade", "candle": candle})
        self.broadcast(ticker, event)

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
            api = get_api()
            levels = get_levels(api, ticker)
            self._levels[ticker] = levels
            for level_name in levels:
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

    def start_stream(self):
        if self.stream:
            return
        self.stream = AlpacaStream(
            on_trade=self.on_trade,
            on_bar=self.on_bar,
        )
        self.stream.start()

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
                           default_timeframe=config.DEFAULT_TIMEFRAME)


@app.route("/settings")
def settings_page():
    env = dotenv_values(_ENV_PATH) if os.path.exists(_ENV_PATH) else {}
    return render_template("settings.html", env=env, timezones=_TIMEZONES)


@app.route("/settings", methods=["POST"])
def save_settings():
    if not os.path.exists(_ENV_PATH):
        with open(_ENV_PATH, "w") as f:
            f.write("")

    set_key(_ENV_PATH, "ALPACA_API_KEY", request.form.get("api_key", "").strip())
    set_key(_ENV_PATH, "ALPACA_API_SECRET", request.form.get("api_secret", "").strip())
    set_key(_ENV_PATH, "ALPACA_BASE_URL", request.form.get("base_url", "").strip())
    set_key(_ENV_PATH, "DATA_FEED", request.form.get("data_feed", "iex"))
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
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    # In debug mode Flask spawns a reloader child process — only start
    # the WebSocket stream and browser in the child (WERKZEUG_RUN_MAIN is set).
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        state.start_stream()
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    print(f"PunkTrader running at http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=debug)
