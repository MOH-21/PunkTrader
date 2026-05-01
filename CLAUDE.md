# PunkTrader — Claude Code Guide

## Project Overview

Flask stock chart app. Real-time data: FMP batch polling + candlestick frontend. REST serves historical bars, key levels (PDH/PDL, PMH/PML, ORH/ORL), VWAP. Live trades via SSE. FMP WebSocket = Premium ($59/mo) — unused; 5s batch polling = live path.

## Project Structure

```
app.py                    # Flask app, StreamState (SSE lifecycle)
config.py                 # Loads .env, exposes constants
data/
  fmp_rest.py             # fetch_bars via FMP stable API (historical)
  fmp_poller.py           # FMPPoller — single-ticker polling (legacy/fallback)
  fmp_batch_poller.py     # FMPBatchPoller — polls /batch-quote for ALL tickers (primary)
  candle_builder.py       # Aggregates trades into OHLCV candles (per-minute buckets)
  vwap.py                 # compute_vwap
levels/
  compute.py              # get_levels — computes PDH/PDL, PMH/PML, ORH/ORL
  alerts.py               # AlertState, evaluate_bar, check_proximity
  cache.py                # LevelCache — per-day JSON cache (NEW, in-progress)
templates/
  index.html              # Main chart UI
  settings.html           # Config UI
static/
  css/app.css             # Punk Brutalist theme
  js/
    chart.js              # ChartPanel — lightweight-charts wrapper, candle countdown timer
    layout.js             # LayoutManager — 1x1/1x2/2x2 panel grid
    data-feed.js          # DataFeed — SSE client, buckets trades into panel timeframe
    toolbar.js            # Ticker input / timeframe buttons
    overlays.js           # VWAP + level lines on chart
    watchlist.js          # Watchlist sidebar (NEW, in-progress)
    keyboard.js           # Type-anywhere keyboard handler (NEW, in-progress)
    status-strip.js       # ET clock + session indicator (NEW, in-progress)
```

## Running the App

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py        # starts on http://localhost:5000
```

Creds at `/settings` or edit `.env` direct.

## Configuration (.env)

| Key | Default | Notes |
|-----|---------|-------|
| `FMP_API_KEY` | — | Required (Financial Modeling Prep) |
| `FMP_BASE_URL` | `https://financialmodelingprep.com/stable` | FMP stable API base |
| `TIMEZONE` | `America/Los_Angeles` | Display timezone |
| `DEFAULT_TICKER` | `SPY` | Ticker shown on load |
| `DEFAULT_TIMEFRAME` | `5Min` | Bar timeframe on load |
| `WATCHLIST` | SPY,QQQ,AAPL,... | Comma-separated; sidebar + level pre-loading |

## Key Architectural Points

- **FMPBatchPoller** polls `/batch-quote?symbols=A,B,...` every 5s, all subscribed tickers, one request. Calls `on_trade` per ticker → `StreamState.on_trade` feeds `CandleBuilder`.
- **CandleBuilder** buckets trades → per-minute OHLCV. Returns `(candle, is_new_bar)`. `is_new_bar=True` → `StreamState` broadcasts prev candle as finalized `bar` SSE event.
- **DataFeed** (frontend) buckets SSE `trade`/`bar` into panel timeframe. 3-way branch: forward / same / old (don't regress `_currentCandle`).
- **"Fake UTC" epoch**: `calendar.timegm(local_timetuple)` in `fmp_rest.py` + `fmp_batch_poller.py` — lightweight-charts shows local TZ timestamps without offset.
- **Candle countdown timer**: `chart.js` renders MM:SS until next candle close on price scale via `priceToCoordinate()`, updated every second. Hidden for 1Day/1Week.
- **AlertState** tracks edge-crossing per (ticker, level) — fires once per cross, not every tick.
- `.env` written at runtime via `python-dotenv`'s `set_key`.

## Data Flow (Live)

```
FMPBatchPoller._fetch_batch()
  → on_trade(ticker, price, 0, now_epoch)
    → StreamState.on_trade()
      → CandleBuilder.on_trade()   → returns (candle, is_new_bar)
      → if is_new_bar: broadcast prev_candle as {type:"bar"}
      → broadcast current candle as {type:"trade"}
        → SSE /stream/<ticker>
          → DataFeed._handleMessage()
            → panel.updateCandle()
              → chart.js candleSeries.update()
```

## Known Constraints

- FMP Starter: no WebSocket, no ETFs on some endpoints, 250 calls/day cap on some endpoints (historical bars cost calls; `/batch-quote` not capped in testing).
- FMP `extended=true` on intraday endpoints → 04:00–09:29 ET premarket bars.
- Level cache (`levels/cache.py`) in-progress — not wired into `app.py` yet.

## Dependencies

Python 3.12, managed in `venv/`. See `requirements.txt`. No test suite.