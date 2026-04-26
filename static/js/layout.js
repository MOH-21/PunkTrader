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
        const panelCount = { '1x1': 1, '1x2': 2, '2x2': 4 }[mode] || 1;
        this.layout = mode;

        // Save current panel states
        const savedStates = this.panels.map(p => ({
            ticker: p.ticker,
            timeframe: p.timeframe,
        }));

        // Destroy existing panels
        this.panels.forEach(p => p.destroy());
        this.panels = [];
        this.gridEl.innerHTML = '';

        // Set grid class
        this.gridEl.className = `layout-${mode}`;

        // Create new panels
        for (let i = 0; i < panelCount; i++) {
            const div = document.createElement('div');
            div.className = 'chart-panel';
            div.id = `panel-${i}`;
            this.gridEl.appendChild(div);

            // Restore state or use defaults
            const state = savedStates[i] || {
                ticker: this._defaultTicker,
                timeframe: this._defaultTimeframe,
            };

            const panel = new ChartPanel(div, state.ticker, state.timeframe);
            this.panels.push(panel);

            // Click to activate
            div.addEventListener('click', () => this.setActivePanel(i));
        }

        // Set active panel
        this.activePanelIndex = Math.min(this.activePanelIndex, panelCount - 1);
        this._updateActiveVisual();

        // Load data for all panels
        this.panels.forEach(p => p.loadData());
    }

    setActivePanel(index) {
        this.activePanelIndex = index;
        this._updateActiveVisual();
    }

    getActivePanel() {
        return this.panels[this.activePanelIndex] || null;
    }

    _updateActiveVisual() {
        this.panels.forEach((p, i) => {
            p.container.classList.toggle('active', i === this.activePanelIndex);
        });
    }

    /**
     * Change ticker/timeframe on the active panel.
     */
    async setTicker(ticker) {
        const panel = this.getActivePanel();
        if (panel) {
            await panel.loadData(ticker);
        }
    }

    async setTimeframe(timeframe) {
        const panel = this.getActivePanel();
        if (panel) {
            await panel.loadData(null, timeframe);
        }
    }
}
