/**
 * DataFeed — SSE client for real-time chart updates.
 *
 * Connects to /stream/<ticker>, receives trades and bars,
 * buckets them into the panel's active timeframe, and calls
 * panel.updateCandle() to update the chart live.
 */
class DataFeed {
    constructor(panel) {
        this.panel = panel;
        this.eventSource = null;
        this._currentCandle = null;
    }

    /**
     * Connect to SSE stream for the panel's ticker.
     */
    connect() {
        this.disconnect();

        const url = `/stream/${this.panel.ticker}`;
        this.eventSource = new EventSource(url);

        this.eventSource.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data);
                this._handleMessage(msg);
            } catch (err) {
                // ignore parse errors
            }
        };

        this.eventSource.onerror = () => {
            // EventSource auto-reconnects
        };
    }

    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        this._currentCandle = null;
    }

    _handleMessage(msg) {
        if (msg.type === 'alert') {
            // Add marker on chart
            if (typeof addAlertMarker === 'function' && msg.time) {
                const label = msg.level || '';
                addAlertMarker(this.panel, msg.time, msg.kind || 'proximity', label);
            }
            // Browser notification
            if (typeof sendBrowserNotification === 'function' && msg.text) {
                sendBrowserNotification('PunkTrader Alert', msg.text);
            }
            return;
        }

        if (msg.type === 'trade' || msg.type === 'bar') {
            const candle = msg.candle;
            if (!candle) return;

            // Bucket the candle into the panel's active timeframe
            const tfSeconds = this._timeframeSeconds();
            const bucketTime = Math.floor(candle.time / tfSeconds) * tfSeconds;

            if (!this._currentCandle || this._currentCandle.time !== bucketTime) {
                // New bar in this timeframe
                this._currentCandle = {
                    time: bucketTime,
                    open: candle.open,
                    high: candle.high,
                    low: candle.low,
                    close: candle.close,
                    volume: candle.volume || 0,
                };
            } else {
                // Update existing bar
                this._currentCandle.high = Math.max(this._currentCandle.high, candle.high);
                this._currentCandle.low = Math.min(this._currentCandle.low, candle.low);
                this._currentCandle.close = candle.close;
                if (msg.type === 'bar') {
                    // Finalized bar — add volume
                    this._currentCandle.volume += candle.volume || 0;
                }
            }

            this.panel.updateCandle({ ...this._currentCandle });
        }
    }

    _timeframeSeconds() {
        const tf = this.panel.timeframe;
        const map = {
            '1Min': 60,
            '5Min': 300,
            '15Min': 900,
            '1Hour': 3600,
            '4Hour': 14400,
            '1Day': 86400,
            '1Week': 604800,
        };
        return map[tf] || 300;
    }
}
