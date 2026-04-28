"""
FMP Paid Plan Verification — run after upgrading to Starter ($22/mo).

Tests all critical unknowns:
  1. Premarket 1min bars (PMH/PML depends on this)
  2. Afterhours 1min bars
  3. QQQ / GOOG ETF access
  4. WebSocket auth + live ticks
  5. Aftermarket quote/trade endpoints
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta

import pytz
import requests

try:
    import websockets
except ImportError:
    websockets = None

import config

BASE = config.FMP_BASE_URL
KEY = config.FMP_API_KEY
ET = pytz.timezone("America/New_York")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_premarket_bars():
    section("1. PREMARKET 1-MIN BARS")

    today = datetime.now(ET).strftime("%Y-%m-%d")
    tomorrow = (datetime.now(ET) + timedelta(days=1)).strftime("%Y-%m-%d")

    r = requests.get(f"{BASE}/historical-chart/1min",
                     params={"symbol": "SPY", "from": today, "to": tomorrow, "apikey": KEY},
                     timeout=10)
    print(f"Status: {r.status_code}")

    if r.status_code != 200:
        print(f"ERROR: {r.text[:300]}")
        return False

    bars = r.json()
    if not isinstance(bars, list) or not bars:
        print("No bars returned")
        return False

    print(f"Total bars: {len(bars)}")
    print(f"Earliest: {bars[-1]['date']}")
    print(f"Latest:   {bars[0]['date']}")

    pre = [b for b in bars if b["date"] < f"{today} 09:30"]
    post = [b for b in bars if b["date"] > f"{today} 16:00"]

    print(f"\nPremarket bars (before 09:30 ET): {len(pre)}")
    if pre:
        print(f"  Earliest: {pre[-1]['date']}")
        print(f"  Latest:   {pre[0]['date']}")
        print("  >>> PMH/PML WILL WORK <<<")
    else:
        print("  >>> NO PREMARKET DATA — PMH/PML BROKEN <<<")

    print(f"\nAfterhours bars (after 16:00 ET): {len(post)}")
    if post:
        print(f"  Latest: {post[0]['date']}")

    return len(pre) > 0


def test_etf_access():
    section("2. ETF ACCESS (QQQ, GOOG)")

    for ticker in ["QQQ", "GOOG", "GOOGL", "SPY", "IWM", "DIA"]:
        r = requests.get(f"{BASE}/quote",
                         params={"symbol": ticker, "apikey": KEY}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            price = data[0].get("price") if data else "?"
            print(f"  OK   {ticker:6} = ${price}")
        else:
            print(f"  FAIL {ticker:6} — {r.status_code}")


def test_aftermarket_endpoints():
    section("3. AFTERMARKET ENDPOINTS")

    for endpoint in ["aftermarket-trade", "aftermarket-quote"]:
        r = requests.get(f"{BASE}/{endpoint}",
                         params={"symbol": "AAPL", "apikey": KEY}, timeout=10)
        print(f"  /{endpoint}: status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"    sample: {json.dumps(data[0] if isinstance(data, list) and data else data)[:200]}")
        else:
            print(f"    {r.text[:150]}")


def test_websocket():
    section("4. WEBSOCKET LIVE TICKS")

    if websockets is None:
        print("  pip install websockets  — skipped")
        return

    async def _test():
        uri = "wss://websockets.financialmodelingprep.com"
        print(f"  Connecting to {uri} ...")
        async with websockets.connect(uri) as ws:
            # Login
            await ws.send(json.dumps({"event": "login", "data": {"apiKey": KEY}}))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            print(f"  Login: {resp}")

            if resp.get("status") != 200:
                print("  >>> LOGIN FAILED — WebSocket may need higher plan <<<")
                return

            # Subscribe
            await ws.send(json.dumps({"event": "subscribe", "data": {"ticker": ["AAPL", "SPY"]}}))
            print("  Subscribed to AAPL, SPY — waiting for ticks...")

            for i in range(8):
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                    print(f"  Tick {i}: {json.dumps(msg)[:200]}")
                except asyncio.TimeoutError:
                    print(f"  Tick {i}: timeout (market may be closed)")
                    break

    asyncio.run(_test())


def test_rate_limits():
    section("5. RATE LIMIT CHECK")

    import time
    count = 0
    start = time.time()
    for i in range(20):
        r = requests.get(f"{BASE}/quote",
                         params={"symbol": "AAPL", "apikey": KEY}, timeout=5)
        if r.status_code == 429:
            print(f"  Rate limited after {i} calls in {time.time()-start:.1f}s")
            return
        count += 1
    elapsed = time.time() - start
    print(f"  {count} calls in {elapsed:.1f}s — no rate limit hit")
    print(f"  ~{count/elapsed:.0f} calls/sec sustained")


if __name__ == "__main__":
    print(f"\nFMP Plan Test — {datetime.now(ET).strftime('%Y-%m-%d %H:%M ET')}")
    print(f"API Key: {'set' if KEY else 'MISSING'}")
    print(f"Base URL: {BASE}")

    test_premarket_bars()
    test_etf_access()
    test_aftermarket_endpoints()
    test_websocket()
    test_rate_limits()

    section("DONE")
    print("Review results above. Key decisions:")
    print("  - If premarket bars exist → PMH/PML good to go")
    print("  - If QQQ works → add back to watchlist")
    print("  - If WebSocket auth OK → swap FMPPoller for WS client")
    print("  - If WebSocket fails → keep poller, increase POLL_INTERVAL")
