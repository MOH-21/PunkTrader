"""
PunkTrader — Flask Application

Serves the charting frontend and provides REST endpoints for historical
bar data, key levels. SSE endpoint for real-time streaming.
"""

import json
import os
import queue
import re
import sys
import threading
import webbrowser

from flask import Flask, Response, jsonify, redirect, render_template, request

from dotenv import dotenv_values, set_key

import config
from data.fmp_rest import fetch_bars, get_api
from data.fmp_batch_poller import FMPBatchPoller
from data.candle_builder import CandleBuilder

from levels.alerts import AlertState, evaluate_bar, check_proximity
from levels.compute import get_levels
import levels.cache as level_cache


def _app_path():
    """Base path for templates/static — PyInstaller bundle vs dev."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


app = Flask(__name__,
    template_folder=os.path.join(_app_path(), 'templates'),
    static_folder=os.path.join(_app_path(), 'static'),
    static_url_path='/static')


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

_INVALID_TICKER_CHARS = re.compile(r'[^A-Z]')

def _sanitize_ticker(t):
    """Strip non-alpha, uppercase, max 10 chars. Raises ValueError if empty."""
    clean = _INVALID_TICKER_CHARS.sub('', t.upper())[:10]
    if not clean:
        raise ValueError(f"invalid ticker: {t!r}")
    return clean


# ---------------------------------------------------------------------------
# CSP security headers
# ---------------------------------------------------------------------------

@app.after_request
def _add_security_headers(resp):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    # Skip CSP for SSE (needs event-stream) and static fonts/images
    ct = resp.content_type or ''
    if ct != 'text/event-stream':
        resp.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
    return resp


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

_TIMEZONES = [
    "America/New_York", "America/Chicago",
    "America/Denver", "America/Los_Angeles",
]

_ENV_PATH = os.path.join(
    os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
    else os.path.dirname(os.path.abspath(__file__)),
    '.env'
)


@app.route("/")
def index():
    return render_template("index.html",
                           default_ticker=config.DEFAULT_TICKER,
                           default_timeframe=config.DEFAULT_TIMEFRAME,
                           watchlist=config.WATCHLIST,
                           timezone=config.TIMEZONE)


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
    set_key(_ENV_PATH, "TIMEZONE", request.form.get("timezone", "America/Los_Angeles"))
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
    try:
        ticker = _sanitize_ticker(ticker)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    timeframe = request.args.get("timeframe", "5Min")
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        api = get_api()
        bars = fetch_bars(api, ticker, timeframe=timeframe,
                          start=start, end=end)
        return jsonify(bars)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/levels/<ticker>")
def api_levels(ticker):
    """Compute key levels (PDH/PDL, PMH/PML, ORH/ORL) for a ticker."""
    try:
        ticker = _sanitize_ticker(ticker)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    try:
        api = get_api()
        levels = get_levels(api, ticker)
        return jsonify(levels)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/quote/<ticker>")
def api_quote(ticker):
    """Single quote passthrough — used by watchlist for initial render."""
    try:
        ticker = _sanitize_ticker(ticker)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    try:
        import requests as _req
        r = _req.get(f"{config.FMP_BASE_URL}/quote",
                     params={"symbol": ticker, "apikey": config.FMP_API_KEY},
                     timeout=8)
        r.raise_for_status()
        data = r.json()
        q = data[0] if isinstance(data, list) and data else {}
        return jsonify({"price": q.get("price"), "changePercentage": q.get("changePercentage")})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------------
# Watchlist management (dynamic add/remove, persists in batch poller)
# ---------------------------------------------------------------------------

@app.route("/api/watchlist/add/<ticker>")
def api_watchlist_add(ticker):
    """Subscribe a ticker to the batch poller and return initial quote."""
    try:
        ticker = _sanitize_ticker(ticker)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if state.stream:
        state.stream.subscribe(ticker)
    threading.Thread(target=state.load_levels, args=(ticker,), daemon=True).start()
    try:
        import requests as _req
        r = _req.get(f"{config.FMP_BASE_URL}/quote",
                     params={"symbol": ticker, "apikey": config.FMP_API_KEY},
                     timeout=8)
        r.raise_for_status()
        data = r.json()
        q = data[0] if isinstance(data, list) and data else {}
        return jsonify({"price": q.get("price"), "changePercentage": q.get("changePercentage")})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/watchlist/remove/<ticker>")
def api_watchlist_remove(ticker):
    """Unsubscribe a user-added ticker from the batch poller."""
    try:
        ticker = _sanitize_ticker(ticker)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if state.stream and ticker.upper() not in [t.upper() for t in config.WATCHLIST]:
        state.stream.unsubscribe(ticker)
    return jsonify({"ok": True})


@app.route("/api/watchlist/sync", methods=["POST"])
def api_watchlist_sync():
    """Resubscribe user-added tickers after page reload."""
    data = request.get_json(silent=True) or {}
    tickers = data.get("tickers", [])
    results = []
    for raw in tickers:
        try:
            t = _sanitize_ticker(raw)
            if state.stream and t not in [x.upper() for x in config.WATCHLIST]:
                state.stream.subscribe(t)
            results.append(t)
        except ValueError:
            pass
    return jsonify({"subscribed": results})


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
    try:
        ticker = _sanitize_ticker(ticker)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

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

def _free_port(port):
    """Kill any process already bound to port so restarts never hit EADDRINUSE."""
    import signal
    import subprocess
    result = subprocess.run(
        ["lsof", "-ti", f":{port}"], capture_output=True, text=True
    )
    for pid_str in result.stdout.split():
        try:
            os.kill(int(pid_str), signal.SIGTERM)
        except ProcessLookupError:
            pass


if __name__ == "__main__":
    import argparse
    _parser = argparse.ArgumentParser(description="PunkTrader")
    _parser.add_argument("--browser", "--no-window", action="store_true",
                         help="Open in browser instead of native window (frozen builds only)")
    _args, _ = _parser.parse_known_args()

    port = int(os.environ.get("PORT", 5000))
    is_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    # One-time setup (not Werkzeug reloader child)
    if not is_child:
        _free_port(port)

        if not getattr(sys, 'frozen', False):
            import subprocess as _sp
            result = _sp.run(
                ["venv/bin/pytest", "--tb=short", "-q"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )
            if result.returncode != 0:
                print("Tests failed — fix them before starting PunkTrader.")
                raise SystemExit(result.returncode)

        # Browser open only in dev mode (not frozen/native-window)
        if not getattr(sys, 'frozen', False):
            threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    # FMP batch poller (must run in serving process)
    state.start_stream()

    print(f"PunkTrader running at http://localhost:{port}")

    # Frozen exe → native window via pywebview (skip with --browser)
    if getattr(sys, 'frozen', False) and not _args.browser:
        try:
            import webview
            threading.Thread(
                target=lambda: app.run(host="127.0.0.1", port=port, debug=False, threaded=True),
                daemon=True,
            ).start()
            # Wait for server before opening window
            import time, urllib.request
            for _ in range(30):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}")
                    break
                except Exception:
                    time.sleep(0.3)
            webview.create_window("PunkTrader", f"http://localhost:{port}")
            webview.start()
            sys.exit(0)
        except ImportError:
            pass  # fall through to plain Flask

    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
