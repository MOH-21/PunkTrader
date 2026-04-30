/**
 * Overlays — key level lines, VWAP, and alert markers on a ChartPanel.
 */

const LEVEL_COLORS = {
    PDH: '#FF00FF',      // Magenta
    PDL: '#6BA3FF',      // Lighter blue
    PMH: '#90EE90',      // Light green
    PML: '#FF6B6B',      // Light red
    ORH: '#CFFF04',      // Lime/accent
    ORL: '#FFB347',      // Light orange
};

// Human-readable short names for labels
const LEVEL_LABELS = {
    PDH: 'PDH', PDL: 'PDL',
    PMH: 'PMH', PML: 'PML',
    ORH: 'ORH', ORL: 'ORL',
};

function _clearLevelOverlays(panel) {
    if (panel._levelLines) {
        panel._levelLines.forEach(line => {
            try { panel.candleSeries.removePriceLine(line); } catch (e) {}
        });
    }
    panel._levelLines = [];

    if (panel._levelLabelEls) {
        panel._levelLabelEls.forEach(el => el.remove());
    }
    panel._levelLabelEls = [];
    panel._levelLabelPrices = [];

    if (panel._levelInterval) {
        clearInterval(panel._levelInterval);
        panel._levelInterval = null;
    }

    if (panel._levelUnsubscribers) {
        panel._levelUnsubscribers.forEach(fn => { try { fn(); } catch (e) {} });
    }
    panel._levelUnsubscribers = [];
}

function _positionLabels(panel) {
    if (!panel._levelLabelEls || !panel._levelLabelPrices) return;
    const containerH = panel.container.offsetHeight;
    panel._levelLabelEls.forEach((el, i) => {
        const price = panel._levelLabelPrices[i];
        const y = panel.candleSeries.priceToCoordinate(price);
        if (y === null || y === undefined || y < 0 || y > containerH) {
            el.style.display = 'none';
        } else {
            el.style.display = 'inline-flex';
            el.style.top = Math.round(y) + 'px';
        }
    });
}

function _makeLevelLabelEl(panel, name, price, color) {
    const el = document.createElement('div');
    el.className = 'level-label';
    el.style.color = color;

    const nameSpan = document.createElement('span');
    nameSpan.className = 'lv-name';
    nameSpan.textContent = LEVEL_LABELS[name] || name;

    const priceSpan = document.createElement('span');
    priceSpan.className = 'lv-price';
    priceSpan.textContent = price.toFixed(2);

    el.appendChild(nameSpan);
    el.appendChild(priceSpan);
    panel.container.appendChild(el);
    return el;
}

/**
 * Load and draw key levels on a chart panel.
 */
async function loadLevels(panel) {
    _clearLevelOverlays(panel);

    try {
        const resp = await fetch(`/api/levels/${panel.ticker}`);
        const levels = await resp.json();

        if (levels.error) return;

        for (const [name, price] of Object.entries(levels)) {
            if (price === null) continue;

            const color = LEVEL_COLORS[name] || '#71717a';

            const line = panel.candleSeries.createPriceLine({
                price,
                color,
                lineWidth: 2,
                lineStyle: 0,          // solid — no dashes
                axisLabelVisible: false,
                title: '',
            });
            panel._levelLines.push(line);

            const el = _makeLevelLabelEl(panel, name, price, color);
            panel._levelLabelEls.push(el);
            panel._levelLabelPrices.push(price);
        }

        panel._levels = levels;

        // Initial paint after chart has settled
        setTimeout(() => _positionLabels(panel), 80);

        // Reposition on horizontal scroll/zoom
        const tsHandler = () => _positionLabels(panel);
        panel.chart.timeScale().subscribeVisibleLogicalRangeChange(tsHandler);
        panel._levelUnsubscribers.push(() =>
            panel.chart.timeScale().unsubscribeVisibleLogicalRangeChange(tsHandler)
        );

        // Reposition on crosshair move (proxy for vertical price scale drag)
        const chHandler = () => _positionLabels(panel);
        panel.chart.subscribeCrosshairMove(chHandler);
        panel._levelUnsubscribers.push(() =>
            panel.chart.unsubscribeCrosshairMove(chHandler)
        );

        // Low-frequency interval catches wheel-scroll on price axis with no mouse move
        panel._levelInterval = setInterval(() => _positionLabels(panel), 150);

    } catch (err) {
        console.error('Failed to load levels:', err);
    }
}

/**
 * Load and draw VWAP on a chart panel.
 */
async function loadVWAP(panel) {
    if (panel._vwapSeries) {
        try { panel.chart.removeSeries(panel._vwapSeries); } catch (e) {}
    }

    try {
        const resp = await fetch(`/api/vwap/${panel.ticker}`);
        const data = await resp.json();

        if (!Array.isArray(data) || data.length === 0) return;

        panel._vwapSeries = panel.chart.addLineSeries({
            color: '#8b5cf6',
            lineWidth: 2,
            title: 'VWAP',
            priceLineVisible: false,
            lastValueVisible: true,
        });

        panel._vwapSeries.setData(data);
    } catch (err) {
        console.error('Failed to load VWAP:', err);
    }
}

/**
 * Add an alert marker to the chart.
 * kind: "break_above", "break_below", "proximity"
 */
function addAlertMarker(panel, time, kind, text) {
    if (!panel._markers) panel._markers = [];

    const marker = { time, text };

    if (kind === 'break_above') {
        marker.position = 'belowBar';
        marker.color = '#22c55e';
        marker.shape = 'arrowUp';
    } else if (kind === 'break_below') {
        marker.position = 'aboveBar';
        marker.color = '#ef4444';
        marker.shape = 'arrowDown';
    } else {
        marker.position = 'inBar';
        marker.color = '#eab308';
        marker.shape = 'circle';
    }

    panel._markers.push(marker);
    panel._markers.sort((a, b) => a.time - b.time);
    panel.candleSeries.setMarkers(panel._markers);
}
