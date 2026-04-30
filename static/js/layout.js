/**
 * LayoutManager — manages multi-chart grid layouts.
 *
 * Supports 1x1, 1x2, 2x2 layouts. Each cell is an independent ChartPanel.
 */
class LayoutManager {
    constructor(gridEl) {
        this.gridEl = gridEl;
        this.panels = [];
        this.activePanelIndex = 0;
        this.layout = '1x1';
    }

    /**
     * Initialize with a default layout and ticker/timeframe.
     */
    init(ticker, timeframe) {
        this._defaultTicker = ticker;
        this._defaultTimeframe = timeframe;
        this.setLayout('1x1');
    }

    /**
     * Set layout mode: "1x1", "1x2", or "2x2"
     */
    setLayout(mode) {
        var panelCount = { '1x1': 1, '1x2': 2, '2x2': 4 }[mode] || 1;
        this.layout = mode;

        // Save current panel states to persistent store (survives layout changes)
        if (!this._panelStates) this._panelStates = {};
        for (var i = 0; i < this.panels.length; i++) {
            var p = this.panels[i];
            this._panelStates[i] = {
                ticker: p.ticker || this._defaultTicker || 'SPY',
                timeframe: p.timeframe || this._defaultTimeframe || '5Min',
            };
            // Persist draw lines across layout changes
            if (typeof getDrawLineConfigs === 'function') {
                this._panelStates[i].drawLines = getDrawLineConfigs(p);
            }
        }

        // Destroy existing panels
        for (var j = 0; j < this.panels.length; j++) {
            this.panels[j].destroy();
        }
        this.panels = [];
        this.gridEl.innerHTML = '';

        // Set grid class
        this.gridEl.className = 'layout-' + mode;

        // Create new panels
        for (var k = 0; k < panelCount; k++) {
            var div = document.createElement('div');
            div.className = 'chart-panel';
            div.id = 'panel-' + k;
            this.gridEl.appendChild(div);

            // Restore from persistent state or use defaults
            var state = this._panelStates[k] || {
                ticker: this._defaultTicker,
                timeframe: this._defaultTimeframe,
            };
            // Belt-and-suspenders: guard against corrupted state
            if (!state.ticker) state.ticker = this._defaultTicker || 'SPY';
            if (!state.timeframe) state.timeframe = this._defaultTimeframe || '5Min';

            var panel = new ChartPanel(div, state.ticker, state.timeframe);
            // Stash draw line configs for restoration after loadData
            panel._drawLineConfigs = state.drawLines || [];
            this.panels.push(panel);

            // Click to activate
            (function (idx) {
                div.addEventListener('click', function () { this.setActivePanel(idx); }.bind(this));
            }.bind(this)(k));
        }

        // Set active panel
        this.activePanelIndex = Math.min(this.activePanelIndex, panelCount - 1);
        this._updateActiveVisual();

        // Load data for all panels
        for (var l = 0; l < this.panels.length; l++) {
            this.panels[l].loadData();
        }
    }

    setActivePanel(index) {
        this.activePanelIndex = index;
        this._updateActiveVisual();
        var panel = this.getActivePanel();
        if (panel) {
            var tickerInput = document.getElementById('ticker-input');
            if (tickerInput) tickerInput.value = panel.ticker;
            document.dispatchEvent(new CustomEvent('pt:active-panel-changed', {
                detail: { ticker: panel.ticker, timeframe: panel.timeframe }
            }));
        }
    }

    getActivePanel() {
        return this.panels[this.activePanelIndex] || null;
    }

    _updateActiveVisual() {
        var self = this;
        Array.prototype.forEach.call(this.panels, function(p, i) {
            p.container.classList.toggle('active', i === self.activePanelIndex);
        });
    }

    /**
     * Change ticker/timeframe on the active panel.
     */
    setTicker(ticker) {
        var panel = this.getActivePanel();
        if (panel) {
            return panel.loadData(ticker).then((function() {
                document.dispatchEvent(new CustomEvent('pt:active-panel-changed', {
                    detail: { ticker: panel.ticker, timeframe: panel.timeframe }
                }));
            }).bind(this));
        }
        return Promise.resolve();
    }

    setTimeframe(timeframe) {
        var panel = this.getActivePanel();
        if (panel) {
            return panel.loadData(null, timeframe).then((function() {
                document.dispatchEvent(new CustomEvent('pt:active-panel-changed', {
                    detail: { ticker: panel.ticker, timeframe: panel.timeframe }
                }));
            }).bind(this));
        }
        return Promise.resolve();
    }
}
