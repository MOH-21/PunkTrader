# PunkTrader

A TradingView-like charting app built with Flask and [lightweight-charts](https://github.com/nicholasdehnen/lightweight-charts). Real-time candlestick charts with key level overlays, VWAP, alert markers, and multi-chart layouts — all running locally in your browser.

![Dark theme](https://img.shields.io/badge/theme-dark-0a0a0f) ![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Candlestick charts** — All timeframes: 1m, 5m, 15m, 1H, 4H, Daily, Weekly
- **Real-time updates** — Candles build live from Alpaca WebSocket trades and bars via SSE
- **Key level overlays** — PDH/PDL (blue), PMH/PML (orange), ORH/ORL (cyan) as horizontal price lines
- **VWAP** — Purple line overlay computed from session's 1-min bars
- **Alert markers** — Break above/below triangles, proximity circles on the chart + browser notifications
- **Multi-chart layouts** — Single, side-by-side, or 2x2 grid with independent ticker/timeframe per panel
- **Crosshair legend** — OHLCV values on hover
- **Settings UI** — Configure API keys, data feed, timezone, default ticker, and watchlist in the browser

## Setup

```bash
git clone https://github.com/MOH-21/PunkTrader.git
cd PunkTrader
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```
ALPACA_API_KEY=your_key
ALPACA_API_SECRET=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
DATA_FEED=iex
TIMEZONE=America/Los_Angeles
```

Or configure everything from the Settings page after launching.

## Usage

```bash
python app.py
```

Opens automatically at `http://localhost:5000`.

For auto-reload during development:

```bash
FLASK_DEBUG=1 python app.py
```

## Data

All market data comes from [Alpaca](https://alpaca.markets/). The free `iex` feed has ~15 minute delay. Fund a live account and switch to `sip` for real-time data.

| Feed | Latency | Cost |
|------|---------|------|
| `iex` | ~15 min delay | Free |
| `sip` | Real-time | Free with funded live account |

## Architecture

```
Browser (lightweight-charts v4)
  |
  |-- REST: /api/bars, /api/levels, /api/vwap
  |-- SSE:  /stream/<ticker>
  |
Flask (app.py)
  |
  |-- Alpaca REST API (historical bars, key levels, VWAP)
  |-- Alpaca WebSocket (real-time trades + bars)
       |
       --> CandleBuilder --> SSE fan-out per ticker
       --> Alert engine  --> SSE fan-out per ticker
```

## Project Structure

```
PunkTrader/
├── app.py                  # Flask app, REST + SSE endpoints
├── config.py               # Settings from .env
├── data/
│   ├── alpaca_rest.py      # Historical bar fetching
│   ├── alpaca_ws.py        # WebSocket client (trades + bars)
│   ├── candle_builder.py   # Trade aggregation into live candles
│   └── vwap.py             # VWAP computation
├── levels/
│   ├── compute.py          # Key level computation (PDH/PDL, PMH/PML, ORH/ORL)
│   └── alerts.py           # Alert engine (break/reclaim/fade detection)
├── static/
│   ├── css/app.css
│   └── js/
│       ├── app.js          # Entry point
│       ├── chart.js        # ChartPanel (lightweight-charts wrapper)
│       ├── data-feed.js    # SSE client
│       ├── layout.js       # Multi-chart grid manager
│       ├── overlays.js     # Key levels, VWAP, alert markers
│       ├── toolbar.js      # Ticker input, timeframe/layout buttons
│       └── notifications.js
└── templates/
    ├── index.html
    └── settings.html
```
