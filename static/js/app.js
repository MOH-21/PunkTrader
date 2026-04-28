/**
 * PunkTrader — App entry point
 *
 * Initializes layout manager and toolbar, loads chart data.
 */
(function () {
    const grid = document.getElementById('chart-grid');
    const tickerInput = document.getElementById('ticker-input');

    // Defaults from template (set by Flask)
    const defaultTicker = tickerInput.value || 'SPY';
    const defaultTimeframe = '5Min';

    // Initialize layout manager
    const layoutManager = new LayoutManager(grid);
    window.layoutManager = layoutManager;

    // Initialize toolbar and get saved preferences
    const { savedTf, savedLayout } = initToolbar(layoutManager);

    // Use saved preferences or defaults
    const ticker = localStorage.getItem('pt_ticker') || defaultTicker;
    const timeframe = savedTf || defaultTimeframe;
    const layout = savedLayout || '1x1';

    tickerInput.value = ticker;

    // Start with the saved/default layout
    layoutManager._defaultTicker = ticker;
    layoutManager._defaultTimeframe = timeframe;
    layoutManager.setLayout(layout);
})();
