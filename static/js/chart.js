/**
 * ChartPanel — wraps a single lightweight-charts instance.
 *
 * Handles: chart creation, candlestick rendering, crosshair OHLCV legend,
 * historical data fetching, and resize.
 */
class ChartPanel {
    constructor(container, ticker, timeframe) {
        this.container = container;
        this.ticker = ticker;
        this.timeframe = timeframe;
        this.chart = null;
        this.candleSeries = null;
        this.resizeObserver = null;
        this._legendEl = null;
        this._lastData = [];

        this._createChart();
    }

    _createChart() {
        // Header overlay
        const header = document.createElement('div');
        header.className = 'panel-header';
        header.innerHTML = `
            <span class="panel-ticker">${this.ticker}</span>
            <span class="panel-tf">${this._tfLabel()}</span>
            <div class="ohlcv-legend" id="legend-${this.container.id}"></div>
        `;
        this.container.appendChild(header);
        this._legendEl = header.querySelector('.ohlcv-legend');

        // Loading indicator
        this._loadingEl = document.createElement('div');
        this._loadingEl.className = 'chart-loading';
        this._loadingEl.textContent = 'Loading...';
        this.container.appendChild(this._loadingEl);

        // Create chart
        this.chart = LightweightCharts.createChart(this.container, {
            layout: {
                background: { type: 'solid', color: '#0a0a0f' },
                textColor: '#71717a',
                fontSize: 11,
            },
            grid: {
                vertLines: { color: '#1a1a24' },
                horzLines: { color: '#1a1a24' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { color: '#3f3f46', width: 1, style: 2, labelBackgroundColor: '#27272a' },
                horzLine: { color: '#3f3f46', width: 1, style: 2, labelBackgroundColor: '#27272a' },
            },
            rightPriceScale: {
                borderColor: '#2a2a3a',
                scaleMargins: { top: 0.1, bottom: 0.08 },
            },
            timeScale: {
                borderColor: '#2a2a3a',
                timeVisible: true,
                secondsVisible: false,
                rightOffset: 5,
                barSpacing: 8,
            },
            handleScroll: { mouseWheel: true, pressedMouseMove: true },
            handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
        });

        // Candlestick series
        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: '#22c55e',
            downColor: '#ef4444',
            borderUpColor: '#22c55e',
            borderDownColor: '#ef4444',
            wickUpColor: '#22c55e',
            wickDownColor: '#ef4444',
        });

        // Crosshair OHLCV legend
        this.chart.subscribeCrosshairMove((param) => this._updateLegend(param));

        // Resize observer
        this.resizeObserver = new ResizeObserver(() => {
            const { width, height } = this.container.getBoundingClientRect();
            this.chart.resize(width, height);
        });
        this.resizeObserver.observe(this.container);
    }

    _tfLabel() {
        const map = {
            '1Min': '1m', '5Min': '5m', '15Min': '15m',
            '1Hour': '1H', '4Hour': '4H', '1Day': 'D', '1Week': 'W'
        };
        return map[this.timeframe] || this.timeframe;
    }

    _updateLegend(param) {
        if (!this._legendEl) return;

        if (!param || !param.time || !param.seriesData) {
            // Show last bar data when not hovering
            if (this._lastData.length > 0) {
                const bar = this._lastData[this._lastData.length - 1];
                this._renderLegendBar(bar);
            }
            return;
        }

        const data = param.seriesData.get(this.candleSeries);
        if (data) {
            this._renderLegendBar(data);
        }
    }

    _renderLegendBar(bar) {
        if (!bar || bar.open === undefined) return;
        const change = bar.close - bar.open;
        const colorClass = change >= 0 ? 'up' : 'down';
        this._legendEl.innerHTML = `
            <span><span class="label">O</span> <span class="value ${colorClass}">${bar.open.toFixed(2)}</span></span>
            <span><span class="label">H</span> <span class="value ${colorClass}">${bar.high.toFixed(2)}</span></span>
            <span><span class="label">L</span> <span class="value ${colorClass}">${bar.low.toFixed(2)}</span></span>
            <span><span class="label">C</span> <span class="value ${colorClass}">${bar.close.toFixed(2)}</span></span>
            ${bar.volume !== undefined ? `<span><span class="label">V</span> <span class="value">${this._formatVolume(bar.volume)}</span></span>` : ''}
        `;
    }

    _formatVolume(v) {
        if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
        if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
        return v.toString();
    }

    async loadData(ticker, timeframe) {
        this.ticker = ticker || this.ticker;
        this.timeframe = timeframe || this.timeframe;

        // Update header
        const tickerEl = this.container.querySelector('.panel-ticker');
        const tfEl = this.container.querySelector('.panel-tf');
        if (tickerEl) tickerEl.textContent = this.ticker;
        if (tfEl) tfEl.textContent = this._tfLabel();

        // Show loading
        if (this._loadingEl) this._loadingEl.style.display = 'block';

        // Disconnect old data feed before loading new data
        if (this._dataFeed) this._dataFeed.disconnect();

        // Clear old markers
        this._markers = [];
        try { this.candleSeries.setMarkers([]); } catch (e) {}

        try {
            const url = `/api/bars/${this.ticker}?timeframe=${this.timeframe}`;
            const resp = await fetch(url);
            const data = await resp.json();

            if (data.error) {
                console.error('API error:', data.error);
                return;
            }

            this._lastData = data;
            this.candleSeries.setData(data);
            this.chart.timeScale().fitContent();

            // Update legend with last bar
            if (data.length > 0) {
                this._renderLegendBar(data[data.length - 1]);
            }

            // Load overlays (key levels + VWAP)
            if (typeof loadLevels === 'function') loadLevels(this);
            if (typeof loadVWAP === 'function') loadVWAP(this);

            // Connect real-time data feed
            if (typeof DataFeed === 'function') {
                this._dataFeed = new DataFeed(this);
                this._dataFeed.connect();
            }
        } catch (err) {
            console.error('Failed to load bars:', err);
        } finally {
            if (this._loadingEl) this._loadingEl.style.display = 'none';
        }
    }

    updateCandle(candle) {
        // Update or append a candle: {time, open, high, low, close}
        this.candleSeries.update(candle);
        this._renderLegendBar(candle);

        // Keep _lastData in sync
        if (this._lastData.length > 0 && this._lastData[this._lastData.length - 1].time === candle.time) {
            this._lastData[this._lastData.length - 1] = candle;
        } else {
            this._lastData.push(candle);
        }
    }

    destroy() {
        if (this._dataFeed) {
            this._dataFeed.disconnect();
        }
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }
        if (this.chart) {
            this.chart.remove();
        }
        this.container.innerHTML = '';
    }
}
