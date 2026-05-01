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
        this._countdownEl = null;
        this._countdownInterval = null;

        this._createChart();
    }

    _createChart() {
        // Header overlay
        const header = document.createElement('div');
        header.className = 'panel-header';

        const tickerSpan = document.createElement('span');
        tickerSpan.className = 'panel-ticker';
        tickerSpan.textContent = this.ticker;

        const tfSpan = document.createElement('span');
        tfSpan.className = 'panel-tf';
        tfSpan.textContent = this._tfLabel();

        const legendDiv = document.createElement('div');
        legendDiv.className = 'ohlcv-legend';
        legendDiv.id = 'legend-' + this.container.id;

        header.appendChild(tickerSpan);
        header.appendChild(tfSpan);
        header.appendChild(legendDiv);
        this.container.appendChild(header);
        this._legendEl = legendDiv;

        // Loading indicator
        this._loadingEl = document.createElement('div');
        this._loadingEl.className = 'chart-loading';
        this._loadingEl.textContent = 'Loading...';
        this.container.appendChild(this._loadingEl);

        // Create chart
        this.chart = LightweightCharts.createChart(this.container, {
            layout: {
                background: { type: 'solid', color: '#1C1C1C' },
                textColor: '#888880',
                fontSize: 11,
            },
            grid: {
                vertLines: { color: '#252525' },
                horzLines: { color: '#252525' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { color: '#444440', width: 1, style: 2, labelBackgroundColor: '#222220' },
                horzLine: { color: '#444440', width: 1, style: 2, labelBackgroundColor: '#222220' },
            },
            rightPriceScale: {
                borderColor: '#222220',
                scaleMargins: { top: 0.15, bottom: 0.15 },
            },
            timeScale: {
                borderColor: '#222220',
                timeVisible: true,
                secondsVisible: false,
                rightOffset: 5,
                barSpacing: 8,
            },
            handleScroll: { mouseWheel: true, pressedMouseMove: true },
            handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
        });

        // Candlestick series with clearly visible colors
        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: '#00FF41',
            downColor: '#FF2424',
            borderUpColor: '#00FF41',
            borderDownColor: '#FF2424',
            wickUpColor: '#00FF41',
            wickDownColor: '#FF2424',
            priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
        });

        // Crosshair OHLCV legend
        this.chart.subscribeCrosshairMove((param) => this._updateLegend(param));

        // Resize observer
        this.resizeObserver = new ResizeObserver(() => {
            if (this._destroyed) return;
            try {
                const { width, height } = this.container.getBoundingClientRect();
                if (width > 0 && height > 0) {
                    this.chart.resize(width, height);
                }
            } catch (e) {}
        });
        this.resizeObserver.observe(this.container);

        // Candle close countdown
        this._countdownEl = document.createElement('div');
        this._countdownEl.className = 'candle-countdown';
        this.container.appendChild(this._countdownEl);
        this._startCountdown();

        // Draw tool
        if (typeof initDrawTool === 'function') initDrawTool(this);

        // Session markers
        if (typeof initSessionMarkers === 'function') initSessionMarkers(this);
    }

    _startCountdown() {
        if (this._countdownInterval) clearInterval(this._countdownInterval);

        const TF_SECONDS = {
            '1Min': 60, '5Min': 300, '15Min': 900,
            '1Hour': 3600, '4Hour': 14400,
        };

        const tick = () => {
            if (this._destroyed) return;
            const tf = TF_SECONDS[this.timeframe];
            if (!tf || !this._countdownEl) {
                if (this._countdownEl) this._countdownEl.style.display = 'none';
                return;
            }

            const now = Math.floor(Date.now() / 1000);
            const remaining = tf - (now % tf);
            const m = Math.floor(remaining / 60);
            const s = remaining % 60;
            this._countdownEl.textContent =
                `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;

            if (this._lastData.length > 0 && this.candleSeries) {
                const lastClose = this._lastData[this._lastData.length - 1].close;
                const y = this.candleSeries.priceToCoordinate(lastClose);
                if (y !== null && y !== undefined) {
                    this._countdownEl.style.top = `${Math.round(y) + 20}px`;
                    this._countdownEl.style.display = 'block';
                }
            }
        };

        tick();
        this._countdownInterval = setInterval(tick, 1000);
    }

    _tfLabel() {
        const map = {
            '1Min': '1m', '5Min': '5m', '15Min': '15m',
            '1Hour': '1H', '4Hour': '4H', '1Day': 'D', '1Week': 'W'
        };
        return map[this.timeframe] || this.timeframe;
    }

    _updateLegend(param) {
        if (this._destroyed || !this._legendEl) return;

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
        } else if (this._lastData.length > 0) {
            this._renderLegendBar(this._lastData[this._lastData.length - 1]);
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

    _showError(msg) {
        // Clear any existing data so stale candles are removed
        try { this.candleSeries.setData([]); } catch (e) {}
        this._lastData = [];
        if (this._legendEl) {
            this._legendEl.innerHTML =
                '<span><span class="label" style="color:#FF2424;">' + msg + '</span></span>';
        }
    }

    _formatVolume(v) {
        if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
        if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
        return v.toString();
    }

    async loadData(ticker, timeframe) {
        this.ticker = ticker || this.ticker;
        this.timeframe = timeframe || this.timeframe;
        this._startCountdown();

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
                this._showError('ERR');
                return;
            }

            if (!data.length) {
                this._showError('NO DATA');
                return;
            }

            this.candleSeries.priceScale().applyOptions({ autoScale: true });
            this._lastData = data;
            this.candleSeries.setData(data);
            this.chart.timeScale().fitContent();

            // Update legend with last bar
            if (data.length > 0) {
                this._renderLegendBar(data[data.length - 1]);
            }

            // Load overlays (key levels)
            if (typeof loadLevels === 'function') loadLevels(this);

            // Restore draw lines persisted across layout changes
            if (this._drawLineConfigs && this._drawLineConfigs.length > 0 && typeof restoreDrawLines === 'function') {
                restoreDrawLines(this, this._drawLineConfigs);
                this._drawLineConfigs = [];
            }

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
        if (this._destroyed) return;
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
        this._destroyed = true;
        if (this._countdownInterval) clearInterval(this._countdownInterval);
        if (this._dataFeed) this._dataFeed.disconnect();
        if (this.resizeObserver) this.resizeObserver.disconnect();
        if (typeof _clearLevelOverlays === 'function') _clearLevelOverlays(this);
        if (typeof clearDrawTool === 'function') clearDrawTool(this);
        if (typeof clearSessionMarkers === 'function') clearSessionMarkers(this);
        if (this.chart) this.chart.remove();
        this.container.innerHTML = '';
    }
}
