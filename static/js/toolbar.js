/**
 * Toolbar — wires up ticker input, timeframe buttons, and layout buttons.
 */
function initToolbar(layoutManager) {
    const tickerInput = document.getElementById('ticker-input');
    const tfButtons = document.querySelectorAll('.tf-btn');
    const layoutButtons = document.querySelectorAll('.layout-btn');

    // --- Ticker input ---
    tickerInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const ticker = tickerInput.value.trim().toUpperCase();
            if (ticker) {
                layoutManager.setTicker(ticker);
                localStorage.setItem('pt_ticker', ticker);
            }
            tickerInput.blur();
        }
    });

    // Select all text on focus
    tickerInput.addEventListener('focus', () => tickerInput.select());

    // --- Timeframe buttons ---
    tfButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            // Update active state
            tfButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const tf = btn.dataset.tf;
            layoutManager.setTimeframe(tf);

            // Save preference
            localStorage.setItem('pt_timeframe', tf);
        });
    });

    // Restore saved timeframe
    const savedTf = localStorage.getItem('pt_timeframe');
    if (savedTf) {
        tfButtons.forEach(b => {
            b.classList.toggle('active', b.dataset.tf === savedTf);
        });
    }

    // --- Layout buttons ---
    layoutButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            layoutButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const layout = btn.dataset.layout;
            layoutManager.setLayout(layout);

            localStorage.setItem('pt_layout', layout);
        });
    });

    // Restore saved layout
    const savedLayout = localStorage.getItem('pt_layout');
    if (savedLayout) {
        layoutButtons.forEach(b => {
            b.classList.toggle('active', b.dataset.layout === savedLayout);
        });
    }

    return { savedTf, savedLayout };
}
