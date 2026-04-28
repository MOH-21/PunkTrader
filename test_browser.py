"""
PunkTrader browser test — uses Playwright to open the app, capture console
errors, network failures, and chart load status.

Usage:
    python test_browser.py [--url http://localhost:5000] [--tickers SPY AAPL TSLA]
"""

import argparse
import json
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5000"
DEFAULT_TICKERS = ["SPY", "AAPL", "TSLA", "MSFT", "AMD"]
LOAD_TIMEOUT = 12_000  # ms to wait for chart data after ticker change


def _ts():
    return datetime.now().strftime("%H:%M:%S")


def run_tests(url, tickers):
    print(f"\n{'='*60}")
    print(f"  PunkTrader Browser Test")
    print(f"  {url}  —  {_ts()}")
    print(f"{'='*60}\n")

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        console_errors = []
        network_failures = []

        page.on("console", lambda msg: console_errors.append({
            "type": msg.type,
            "text": msg.text,
        }) if msg.type in ("error", "warning") else None)

        page.on("response", lambda resp: network_failures.append({
            "status": resp.status,
            "url":    resp.url,
        }) if resp.status >= 400 else None)

        # ── Load index ────────────────────────────────────────────
        print(f"[{_ts()}] Loading {url} ...")
        try:
            page.goto(url, timeout=10_000)
            page.wait_for_load_state("load", timeout=10_000)
            time.sleep(2)  # let JS init + SSE connect
            print(f"[{_ts()}] Page loaded OK\n")
        except Exception as e:
            print(f"[{_ts()}] FAILED to load page: {e}")
            browser.close()
            return

        # ── Test each ticker ──────────────────────────────────────
        for ticker in tickers:
            console_errors.clear()
            network_failures.clear()

            print(f"[{_ts()}] Testing {ticker} ...")

            # Type ticker and submit
            inp = page.locator("#ticker-input")
            inp.click(click_count=3)
            inp.fill(ticker)
            inp.press("Enter")

            # Wait for chart data (bars API call to resolve)
            try:
                page.wait_for_response(
                    lambda r, t=ticker: f"/api/bars/{t.upper()}" in r.url,
                    timeout=LOAD_TIMEOUT,
                )
            except Exception:
                pass  # timeout is fine — we'll report what we got

            time.sleep(1.5)  # let JS render

            # ── API spot check ────────────────────────────────────
            api_results = {}
            for endpoint in ("bars", "levels", "vwap"):
                path = f"/api/{endpoint}/{ticker.upper()}?timeframe=5Min"
                resp = page.request.get(f"{url}{path}")
                body = resp.json()
                if isinstance(body, dict) and "error" in body:
                    api_results[endpoint] = f"ERROR: {body['error']}"
                elif isinstance(body, list):
                    api_results[endpoint] = f"OK ({len(body)} items)"
                elif isinstance(body, dict):
                    api_results[endpoint] = f"OK ({list(body.keys())})"
                else:
                    api_results[endpoint] = f"status={resp.status}"

            results[ticker] = {
                "api":             api_results,
                "console_errors":  list(console_errors),
                "network_failures": list(network_failures),
            }

            status = "✓" if not any(
                "ERROR" in v for v in api_results.values()
            ) and not network_failures else "✗"

            print(f"  {status} bars:   {api_results.get('bars', '?')}")
            print(f"  {status} levels: {api_results.get('levels', '?')}")
            print(f"  {status} vwap:   {api_results.get('vwap', '?')}")

            if network_failures:
                for f in network_failures:
                    print(f"  ✗ {f['status']} {f['url']}")

            if console_errors:
                for e in console_errors:
                    print(f"  [{e['type'].upper()}] {e['text']}")

            print()

        browser.close()

    # ── Summary ───────────────────────────────────────────────────
    print(f"{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for ticker, r in results.items():
        ok = all("ERROR" not in v for v in r["api"].values()) and not r["network_failures"]
        print(f"  {'OK  ' if ok else 'FAIL'} {ticker}")
        if not ok:
            for k, v in r["api"].items():
                if "ERROR" in v:
                    print(f"       {k}: {v}")
            for f in r["network_failures"]:
                print(f"       {f['status']} {f['url']}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=BASE_URL)
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    args = parser.parse_args()
    run_tests(args.url, args.tickers)
