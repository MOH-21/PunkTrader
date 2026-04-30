/**
 * PunkTrader — App entry point
 *
 * Initializes layout manager and toolbar, loads chart data.
 *
 * Instance scoping via ?i=N query param:
 *   http://localhost:5000?i=1  →  window A (keys pt_ticker_1, …)
 *   http://localhost:5000?i=2  →  window B (keys pt_ticker_2, …)
 * Without ?i= the bare keys are used (backward compatible).
 */
(function () {
    try {
        const grid = document.getElementById('chart-grid');
        const tickerInput = document.getElementById('ticker-input');

        // Instance id from ?i=N query param — scopes localStorage keys
        const params = new URLSearchParams(window.location.search);
        const instanceId = params.get('i');
        const scope = instanceId ? '_' + instanceId : '';

        function ptKey(name) { return 'pt_' + name + scope; }

        window.ptKey = ptKey;

        // Defaults from template (set by Flask)
        const defaultTicker = tickerInput.value || 'SPY';
        const defaultTimeframe = '5Min';

        // Initialize layout manager
        const layoutManager = new LayoutManager(grid);
        window.layoutManager = layoutManager;

        // Initialize toolbar and get saved preferences
        const toolbar = initToolbar(layoutManager, ptKey);
        var savedTf = toolbar ? toolbar.savedTf : null;
        var savedLayout = toolbar ? toolbar.savedLayout : null;

        // Use saved preferences or defaults
        var ticker, timeframe, layout;
        try { ticker = localStorage.getItem(ptKey('ticker')) || defaultTicker; } catch (e) { ticker = defaultTicker; }
        try { timeframe = savedTf || defaultTimeframe; } catch (e) { timeframe = defaultTimeframe; }
        try { layout = savedLayout || '1x1'; } catch (e) { layout = '1x1'; }

        tickerInput.value = ticker;

        // Start with the saved/default layout
        try {
            layoutManager._defaultTicker = ticker;
            layoutManager._defaultTimeframe = timeframe;
            layoutManager.setLayout(layout);
        } catch (e) {
            console.error('Layout init failed:', e);
            var errEl = document.createElement('div');
            errEl.style.cssText = 'color:#FF2424;padding:40px;font-family:monospace;font-size:14px;';
            errEl.textContent = 'Chart init error: ' + (e.message || e);
            grid.appendChild(errEl);
        }
    } catch (e) {
        console.error('App init failed:', e);
        var err = document.getElementById('chart-grid');
        if (err) {
            err.innerHTML = '<div style="color:#FF2424;padding:40px;font-family:monospace;font-size:14px;">'
                + 'App init error: ' + (e.message || e) + '</div>';
        }
    }
})();
