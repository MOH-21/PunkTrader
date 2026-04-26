/**
 * Overlays — key level lines, VWAP, and alert markers on a ChartPanel.
 */

// Level colors
const LEVEL_COLORS = {
    PDH: '#3b82f6', PDL: '#3b82f6',  // blue
    PMH: '#f59e0b', PML: '#f59e0b',  // orange
    ORH: '#06b6d4', ORL: '#06b6d4',  // cyan
};

const LEVEL_STYLES = {
    PDH: 0, PDL: 2,  // solid, dashed
    PMH: 0, PML: 2,
    ORH: 0, ORL: 2,
};

/**
 * Load and draw key levels on a chart panel.
 */
async function loadLevels(panel) {
    // Remove existing level lines
    if (panel._levelLines) {
        panel._levelLines.forEach(line => {
            try { panel.candleSeries.removePriceLine(line); } catch (e) {}
        });
    }
    panel._levelLines = [];

    try {
        const resp = await fetch(`/api/levels/${panel.ticker}`);
        const levels = await resp.json();

        if (levels.error) return;

        for (const [name, price] of Object.entries(levels)) {
            if (price === null) continue;

            const line = panel.candleSeries.createPriceLine({
                price: price,
                color: LEVEL_COLORS[name] || '#71717a',
                lineWidth: 1,
                lineStyle: LEVEL_STYLES[name] !== undefined ? LEVEL_STYLES[name] : 0,
                axisLabelVisible: true,
                title: name,
            });
            panel._levelLines.push(line);
        }

        panel._levels = levels;
    } catch (err) {
        console.error('Failed to load levels:', err);
    }
}

/**
 * Load and draw VWAP on a chart panel.
 */
async function loadVWAP(panel) {
    // Remove existing VWAP series
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

    const marker = { time: time, text: text };

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
    // Sort markers by time (required by lightweight-charts)
    panel._markers.sort((a, b) => a.time - b.time);
    panel.candleSeries.setMarkers(panel._markers);
}
